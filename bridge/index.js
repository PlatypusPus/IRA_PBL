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
//   outbound  POST :8085/send {chat_id, text} -> WhatsApp message
//   browser   http://localhost:8085/  -> QR connect page
const http = require('http');
const path = require('path');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  downloadMediaMessage,
  DisconnectReason,
} = require('baileys');
const QRCode = require('qrcode');

const WADR_API = process.env.WADR_API || 'http://localhost:8000';
const PORT = process.env.PORT || 8085;

let sock = null;
let latestQr = null; // data-URL PNG of the current login QR
let status = 'starting';

async function postWadr(route, body) {
  const res = await fetch(WADR_API + route, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
      // ponytail: media without a filename (photos, voice notes) gets one from
      // the mime subtype - matches the extensions wadr's EXTRACTORS routes on.
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
      console.log(`  -> ingest ${filename} (${media.mimetype}): HTTP ${res.status}`);
    } else if (text.startsWith('/find ')) {
      await postWadr('/webhook/openwa/query', { chat_id: chatId, sender, text });
      console.log(`  -> query: ${text}`);
    } else {
      console.log('  ignored (no media, not "/find ...")');
    }
  } catch (e) {
    console.error('message handling failed:', e);
  }
}

async function startWA() {
  const { state, saveCreds } = await useMultiFileAuthState(path.join(__dirname, 'auth'));
  const s = makeWASocket({ auth: state });
  s.ev.on('creds.update', saveCreds);
  s.ev.on('connection.update', async (u) => {
    if (u.qr) {
      latestQr = await QRCode.toDataURL(u.qr);
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
        status = 'logged out - delete bridge/auth and restart';
        console.error(status);
      } else {
        status = 'reconnecting';
        startWA();
      }
    }
  });
  s.ev.on('messages.upsert', ({ messages, type }) => {
    if (type === 'notify') messages.forEach(onMessage);
  });
}

startWA().catch((e) => { status = `failed: ${e.message}`; console.error(e); });

const PAGE = `<!doctype html><meta charset="utf-8"><title>WADR — connect WhatsApp</title>
<style>
  body{font-family:system-ui;display:grid;place-items:center;min-height:100vh;margin:0;background:#111;color:#eee}
  main{text-align:center}img{width:280px;height:280px;background:#fff;padding:12px;border-radius:12px}
  .ok{color:#4ade80;font-size:1.4rem}
</style>
<main>
  <h1>WADR bridge</h1>
  <div id="box">loading…</div>
  <p>Open WhatsApp → Linked devices → Link a device, then scan.</p>
</main>
<script>
  async function tick(){
    const s = await (await fetch('/status')).json();
    document.getElementById('box').innerHTML =
      s.qr ? '<img src="'+s.qr+'">' :
      s.status === 'connected' ? '<p class="ok">✓ connected</p>' : '<p>'+s.status+'</p>';
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
