// WADR WhatsApp bridge: owns every WhatsApp session and speaks HTTP to WADR.
//
// One process, N sessions - one per linked number, keyed by the account's
// session_key. Every message forwarded to WADR carries that key, which is how
// the API attributes a document to the right user.
//
// Internally uses Baileys (WebSocket, no browser). open-wa and whatsapp-web.js
// were both tried and both broke on media download against current WhatsApp Web
// (they drive a real browser page and call WhatsApp internals that keep
// changing); Baileys speaks the protocol directly, decrypts media itself, and
// handles the newer @lid sender addressing.
//
//   POST   /sessions                     {session_key}   -> start a session
//   GET    /sessions/:key                                -> {status, qr, phone}
//   POST   /sessions/:key/pair           {phone}         -> {pairing_code}
//   DELETE /sessions/:key                                -> log out + forget
//   POST   /send                         {session_key, chat_id, text}
//   POST   /send-file                    {session_key, chat_id, filename, mime_type, data_base64}
//
// Every route requires the X-Bridge-Token shared secret.
const http = require('http');
const path = require('path');
const fs = require('fs/promises');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  DisconnectReason,
  Browsers,
} = require('baileys');
const QRCode = require('qrcode');

const WADR_API = process.env.WADR_API || 'http://127.0.0.1:8000';
const PORT = process.env.PORT || 8085;
const TOKEN = process.env.WADR_BRIDGE_TOKEN || '';
const AUTH_ROOT = path.join(__dirname, 'auth');

if (!TOKEN) {
  console.error('WADR_BRIDGE_TOKEN is not set. Set the same value here and for the API.');
  process.exit(1);
}

/** session_key -> {sock, qr, status, phone, key} */
const sessions = new Map();

async function postWadr(route, body) {
  const res = await fetch(WADR_API + route, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Bridge-Token': TOKEN },
    body: JSON.stringify(body),
  }).catch(() => {
    // ponytail: undici's raw ECONNREFUSED stack says nothing useful here
    throw new Error(`WADR API unreachable at ${WADR_API} — start it: uv run uvicorn wadr.api.app:app`);
  });
  if (!res.ok) console.error(`WADR ${route} -> ${res.status}: ${await res.text()}`);
  return res;
}

async function onMessage(sessionKey, m) {
  const chatId = m.key.remoteJid;
  if (!chatId || chatId === 'status@broadcast' || !m.message) return;
  const sender = m.key.participant || chatId;
  // captioned documents nest the real content one level down
  const msg = m.message.documentWithCaptionMessage?.message || m.message;
  const media = msg.documentMessage || msg.imageMessage || msg.audioMessage;
  const text = msg.conversation || msg.extendedTextMessage?.text || '';
  console.log(`[${sessionKey}] recv media=${media ? media.mimetype : 'none'} from=${chatId}`);
  try {
    if (media) {
      const data = await downloadMediaMessage(m, 'buffer', {});
      const ext = (media.mimetype || 'application/octet-stream').split('/')[1].split(';')[0];
      const filename = media.fileName || `wa-${m.messageTimestamp}.${ext}`;
      const res = await postWadr('/api/bridge/document', {
        session_key: sessionKey,
        chat_id: chatId,
        sender,
        timestamp: new Date(Number(m.messageTimestamp) * 1000).toISOString(),
        filename,
        mime_type: media.mimetype,
        data_base64: data.toString('base64'),
      });
      if (res.ok) {
        const { duplicate } = await res.json().catch(() => ({}));
        console.log(`  -> ${filename}: ${duplicate ? 'already had it' : 'saved'}`);
      }
    } else if (text.startsWith('/find ')) {
      await postWadr('/api/bridge/query', { session_key: sessionKey, chat_id: chatId, sender, text });
    } else if (text.startsWith('/get ')) {
      await postWadr('/api/bridge/get', { session_key: sessionKey, chat_id: chatId, sender, text });
    }
  } catch (e) {
    console.error(`[${sessionKey}] message handling failed:`, e.message);
  }
}

async function reportStatus(sessionKey, status, phone) {
  await postWadr('/api/bridge/status', { session_key: sessionKey, status, phone }).catch((e) =>
    console.error(`[${sessionKey}] status report failed:`, e.message),
  );
}

async function startSession(sessionKey) {
  const existing = sessions.get(sessionKey);
  if (existing && existing.sock) return existing;

  // Baileys ships a hardcoded WA Web protocol version that goes stale within
  // weeks; an outdated one makes WA reject the handshake before the QR stage
  // ("Connection Failure" forever) - always fetch the live one.
  const { version } = await fetchLatestBaileysVersion();
  const { state, saveCreds } = await useMultiFileAuthState(path.join(AUTH_ROOT, sessionKey));

  const session = sessions.get(sessionKey) || { key: sessionKey, status: 'starting', qr: null };
  sessions.set(sessionKey, session);

  // Browsers.ubuntu('Chrome') is the identity WA accepts for pairing-code
  // login; with the Baileys default the /pair request is rejected.
  const sock = makeWASocket({ auth: state, version, browser: Browsers.ubuntu('Chrome') });
  session.sock = sock;
  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (u) => {
    if (u.qr) {
      // Big, low-EC, thin-margin: iOS's scanner needs chunkier modules than
      // Android's, and 'L' drops the QR a couple of versions.
      session.qr = await QRCode.toDataURL(u.qr, {
        width: 400, margin: 2, errorCorrectionLevel: 'L',
      });
      session.status = 'scan';
    }
    if (u.connection === 'open') {
      session.qr = null;
      session.status = 'linked';
      session.phone = sock.user?.id?.split(':')[0] || null;
      console.log(`[${sessionKey}] linked as ${session.phone}`);
      reportStatus(sessionKey, 'linked', session.phone);
    }
    if (u.connection === 'close') {
      const loggedOut = u.lastDisconnect?.error?.output?.statusCode === DisconnectReason.loggedOut;
      session.sock = null;
      if (loggedOut) {
        session.status = 'logged_out';
        await fs.rm(path.join(AUTH_ROOT, sessionKey), { recursive: true, force: true });
        reportStatus(sessionKey, 'logged_out', session.phone);
        startSession(sessionKey);  // straight back to a fresh QR
      } else if (sessions.has(sessionKey)) {
        session.status = 'reconnecting';
        setTimeout(() => startSession(sessionKey), 2000);  // backoff, don't spin
      }
    }
  });

  sock.ev.on('messages.upsert', ({ messages, type }) => {
    if (type === 'notify') messages.forEach((m) => onMessage(sessionKey, m));
  });

  return session;
}

async function stopSession(sessionKey) {
  const session = sessions.get(sessionKey);
  sessions.delete(sessionKey);  // deleted first, so the close handler won't reconnect
  if (session?.sock) {
    await session.sock.logout().catch(() => session.sock.end());
  }
  await fs.rm(path.join(AUTH_ROOT, sessionKey), { recursive: true, force: true });
}

// Restart every session that still has credentials on disk, so a bridge
// restart does not force everyone to re-scan.
async function resumeSessions() {
  const keys = await fs.readdir(AUTH_ROOT).catch(() => []);
  for (const key of keys) {
    const creds = path.join(AUTH_ROOT, key, 'creds.json');
    if (await fs.access(creds).then(() => true).catch(() => false)) {
      console.log(`resuming session ${key}`);
      startSession(key).catch((e) => console.error(`[${key}] resume failed:`, e.message));
    }
  }
}

// ------------------------------------------------------------------ HTTP

async function readJson(req) {
  let body = '';
  for await (const chunk of req) body += chunk;
  return body ? JSON.parse(body) : {};
}

const json = (res, code, payload) => {
  res.writeHead(code, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(payload));
};

http.createServer(async (req, res) => {
  try {
    if (req.headers['x-bridge-token'] !== TOKEN) return json(res, 401, { error: 'bad token' });

    const url = new URL(req.url, 'http://localhost');
    const parts = url.pathname.split('/').filter(Boolean);

    if (req.method === 'POST' && url.pathname === '/sessions') {
      const { session_key } = await readJson(req);
      if (!session_key) return json(res, 400, { error: 'need session_key' });
      const session = await startSession(session_key);
      return json(res, 200, { status: session.status });
    }

    if (parts[0] === 'sessions' && parts[1]) {
      const key = decodeURIComponent(parts[1]);
      const session = sessions.get(key);

      if (req.method === 'GET' && parts.length === 2) {
        if (!session) return json(res, 200, { status: 'stopped', qr: null });
        return json(res, 200, {
          status: session.status, qr: session.qr, phone: session.phone || null,
        });
      }

      if (req.method === 'POST' && parts[2] === 'pair') {
        const { phone } = await readJson(req);
        const digits = String(phone || '').replace(/\D/g, '');
        if (!session?.sock || !digits) {
          return json(res, 400, { error: 'need a connecting session and a number with country code' });
        }
        const code = await session.sock.requestPairingCode(digits);
        session.status = 'pairing';
        return json(res, 200, { pairing_code: code });
      }

      if (req.method === 'DELETE' && parts.length === 2) {
        await stopSession(key);
        return json(res, 200, { ok: true });
      }
    }

    if (req.method === 'POST' && (url.pathname === '/send' || url.pathname === '/send-file')) {
      const body = await readJson(req);
      const session = sessions.get(body.session_key);
      if (!session?.sock) return json(res, 503, { error: 'that number is not connected' });
      if (url.pathname === '/send') {
        await session.sock.sendMessage(body.chat_id, { text: body.text });
      } else {
        await session.sock.sendMessage(body.chat_id, {
          document: Buffer.from(body.data_base64, 'base64'),
          fileName: body.filename,
          mimetype: body.mime_type,
        });
      }
      return json(res, 200, {});
    }

    return json(res, 404, { error: 'no such route' });
  } catch (e) {
    console.error(e);
    return json(res, 500, { error: String(e.message || e) });
  }
}).listen(PORT, () => {
  console.log(`bridge on http://127.0.0.1:${PORT} — ${sessions.size} sessions`);
  resumeSessions();
});
