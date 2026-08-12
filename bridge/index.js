// WADR WhatsApp bridge: owns the WhatsApp session and speaks HTTP to WADR.
// Contract lives in src/wadr/adapters/openwa.py. Run: npm start (in bridge/).
//
// Internally uses Baileys (WebSocket, no browser). open-wa and whatsapp-web.js
// were both tried and both broke on media download against current WhatsApp Web
// (they drive a real browser page and call WhatsApp internals that keep
// changing); Baileys speaks the protocol directly and decrypts media itself, and
// handles the newer @lid sender addressing. The adapter/route names keep
// "openwa" from the original assignment; the HTTP contract is unchanged.
//
//   inbound   document/image/voice  -> POST {WADR_API}/webhook/openwa
//   inbound   "/find <query>"       -> POST {WADR_API}/webhook/openwa/query
//   inbound   "/get <n>"            -> POST {WADR_API}/webhook/openwa/get
//   outbound  POST :8085/send {chat_id, text}                        -> WhatsApp message
//   outbound  POST :8085/send-file {chat_id, filename, mime_type, data_base64} -> WhatsApp file
//   browser   http://localhost:8085/  -> QR connect page (or pairing code, for iPhones)
const http = require('http');
const path = require('path');
const fs = require('fs/promises');
const { spawn } = require('child_process');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  DisconnectReason,
  Browsers,
} = require('baileys');
const QRCode = require('qrcode');

const WADR_API = process.env.WADR_API || 'http://localhost:8000';
const PORT = process.env.PORT || 8085;

let sock = null;
let pending = null; // the not-yet-logged-in socket, for pairing-code requests
let latestQr = null; // data-URL PNG of the current login QR
let status = 'starting';

async function postWadr(route, body) {
  const res = await fetch(WADR_API + route, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).catch(() => {
    // ponytail: undici's raw ECONNREFUSED stack says nothing useful here
    throw new Error(`WADR API unreachable at ${WADR_API} — start it: uv run uvicorn wadr.api.app:app`);
  });
  if (!res.ok) console.error(`WADR ${route} -> ${res.status}: ${await res.text()}`);
  return res;
}

async function onMessage(m) {
  const chatId = m.key.remoteJid;
  if (!chatId || chatId === 'status@broadcast' || !m.message) return;
  const sender = m.key.participant || chatId;
  // captioned documents nest the real content one level down
  const msg = m.message.documentWithCaptionMessage?.message || m.message;
  const media = msg.documentMessage || msg.imageMessage || msg.audioMessage;
  const text = msg.conversation || msg.extendedTextMessage?.text || '';
  console.log(`recv media=${media ? media.mimetype : 'none'} from=${chatId}`);
  try {
    if (media) {
      const data = await downloadMediaMessage(m, 'buffer', {});
      const ext = (media.mimetype || 'application/octet-stream').split('/')[1].split(';')[0];
      const filename = media.fileName || `wa-${m.messageTimestamp}.${ext}`;
      const res = await postWadr('/webhook/openwa', {
        chat_id: chatId,
        sender,
        timestamp: new Date(Number(m.messageTimestamp) * 1000).toISOString(),
        filename,
        mime_type: media.mimetype,
        data_base64: data.toString('base64'),
      });
      if (res.ok) {
        const { duplicate } = await res.json().catch(() => ({}));
        console.log(`  -> ingest ${filename}: ${duplicate ? 'duplicate' : 'new'} (HTTP ${res.status})`);
      } else {
        console.log(`  -> ingest ${filename}: FAILED (HTTP ${res.status})`);
      }
    } else if (text.startsWith('/find ')) {
      await postWadr('/webhook/openwa/query', { chat_id: chatId, sender, text });
      console.log(`  -> query: ${text}`);
    } else if (text.startsWith('/get ')) {
      await postWadr('/webhook/openwa/get', { chat_id: chatId, sender, text });
      console.log(`  -> get: ${text}`);
    } else {
      console.log('  ignored (no media, not "/find"/"/get")');
    }
  } catch (e) {
    console.error('message handling failed:', e.message);
  }
}

const AUTH_DIR = path.join(__dirname, 'auth');

async function startWA() {
  // Baileys ships a hardcoded WA Web protocol version that goes stale within
  // weeks; an outdated one makes WA reject the handshake before the QR stage
  // ("Connection Failure" on every attempt, forever) - always fetch the live one.
  const { version } = await fetchLatestBaileysVersion();
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  // Browsers.ubuntu('Chrome') is the identity WA accepts for pairing-code login;
  // with the Baileys default the /pair request is rejected.
  const s = makeWASocket({ auth: state, version, browser: Browsers.ubuntu('Chrome') });
  pending = s;
  s.ev.on('creds.update', saveCreds);
  s.ev.on('connection.update', async (u) => {
    if (u.qr) {
      // Big, low-EC, thin-margin: iOS's scanner needs chunkier modules than
      // Android's. 'L' drops the QR a couple of versions (fewer, bigger
      // modules) and the screen doesn't need damage tolerance.
      latestQr = await QRCode.toDataURL(u.qr, { width: 400, margin: 2, errorCorrectionLevel: 'L' });
      status = 'scan the QR';
    }
    if (u.connection === 'open') {
      sock = s;
      latestQr = null;
      status = 'connected';
      console.log('WhatsApp session ready');
    }
    if (u.connection === 'close') {
      sock = null;
      if (u.lastDisconnect?.error?.output?.statusCode === DisconnectReason.loggedOut) {
        status = 'logged out - generating a new QR';
        console.log(status);
        await fs.rm(AUTH_DIR, { recursive: true, force: true });
        startWA();
      } else {
        status = 'reconnecting';
        setTimeout(startWA, 2000); // backoff so a bad network doesn't spin-loop
      }
    }
  });
  s.ev.on('messages.upsert', ({ messages, type }) => {
    if (type === 'notify') messages.forEach(onMessage);
  });
}

// `npm start` also brings up the WADR API, since the bridge is useless without
// it. Skipped if something already answers on WADR_API, so running uvicorn
// yourself (e.g. with --reload) still works.
async function startApi() {
  const alreadyUp = await fetch(WADR_API + '/search?q=ping').then(() => true).catch(() => false);
  if (alreadyUp) return console.log(`WADR API already running at ${WADR_API}`);
  // ponytail: dies with the terminal, not with this process, on Windows —
  // swap in a tree-kill if orphaned uvicorns become a nuisance.
  const api = spawn('uv', ['run', 'uvicorn', 'wadr.api.app:app'], {
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit',
    shell: true, // Windows needs the shell to resolve uv.cmd
  });
  api.on('error', (e) => console.error(`could not start the WADR API: ${e.message}`));
  process.on('exit', () => api.kill());
}

startApi();
startWA().catch((e) => { status = `failed: ${e.message}`; console.error(e); });

const PAGE = `<!doctype html><meta charset="utf-8"><title>WADR — connect WhatsApp</title>
<style>
  body{font-family:system-ui;display:grid;place-items:center;min-height:100vh;margin:0;background:#111;color:#eee}
  main{text-align:center}
  /* 1:1 with the rendered PNG - rescaling softens the modules and iPhones stop reading it */
  img{width:400px;height:400px;max-width:86vw;background:#fff;padding:16px;border-radius:12px}
  .ok{color:#4ade80;font-size:1.4rem}
  .alt{color:#888;font-size:.85rem}
</style>
<main>
  <h1>WADR bridge</h1>
  <div id="box">loading…</div>
  <p>Open WhatsApp → Linked devices → Link a device, then scan.</p>
  <p class="alt">Scanner won't lock on? Fall back to a pairing code:
    <input id="num" placeholder="919876543210" size="14"> <button onclick="pair()">get code</button></p>
</main>
<script>
  async function tick(){
    const s = await (await fetch('/status')).json();
    document.getElementById('box').innerHTML =
      s.status === 'connected' ? '<p class="ok">✓ connected</p>' :
      s.status.startsWith('pairing code') ? '<h2>'+s.status.slice(14)+'</h2>' :
      s.qr ? '<img src="'+s.qr+'">' : '<p>'+s.status+'</p>';
  }
  async function pair(){
    const r = await fetch('/pair', {method:'POST', body: JSON.stringify({number: num.value})});
    if (!r.ok) alert(await r.text()); else tick();
  }
  tick(); setInterval(tick, 2000);
</script>`;

http.createServer(async (req, res) => {
  try {
    if (req.method === 'POST' && req.url === '/send') {
      if (!sock) { res.writeHead(503); return res.end('not connected'); }
      let body = '';
      for await (const chunk of req) body += chunk;
      const { chat_id, text } = JSON.parse(body);
      await sock.sendMessage(chat_id, { text });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end('{}');
    }
    if (req.method === 'POST' && req.url === '/send-file') {
      if (!sock) { res.writeHead(503); return res.end('not connected'); }
      let body = '';
      for await (const chunk of req) body += chunk;
      const { chat_id, filename, mime_type, data_base64 } = JSON.parse(body);
      await sock.sendMessage(chat_id, {
        document: Buffer.from(data_base64, 'base64'),
        fileName: filename,
        mimetype: mime_type,
      });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end('{}');
    }
    if (req.method === 'POST' && req.url === '/pair') {
      // iPhones scan a screen QR badly; pairing by number is the reliable path.
      let body = '';
      for await (const chunk of req) body += chunk;
      const number = String(JSON.parse(body).number || '').replace(/\D/g, '');
      if (!pending || !number) { res.writeHead(400); return res.end('need a number with country code'); }
      const code = await pending.requestPairingCode(number);
      latestQr = null;
      status = `pairing code: ${code}`;
      console.log(status);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ code }));
    }
    if (req.url === '/status') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ status, qr: latestQr }));
    }
    res.writeHead(200, { 'Content-Type': 'text/html' });
    return res.end(PAGE);
  } catch (e) {
    console.error(e);
    res.writeHead(500);
    res.end(String(e));
  }
}).listen(PORT, () => console.log(`bridge on http://localhost:${PORT} — open it to link WhatsApp`));
