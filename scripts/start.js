// `npm start` - runs the whole product: API + web app on :8000, WhatsApp
// bridge on :8085. Node builtins only, so the repo root needs no dependencies.
//
// The two processes share a secret. Rather than make the operator invent, export
// and re-export one, this writes a random token to .env (gitignored) on first
// run; both sides read that file themselves.
const { spawn, spawnSync } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const ENV_FILE = path.join(ROOT, '.env');
const WINDOWS = process.platform === 'win32';

if (!fs.existsSync(ENV_FILE) || !/^WADR_BRIDGE_TOKEN=.+/m.test(fs.readFileSync(ENV_FILE, 'utf8'))) {
  fs.appendFileSync(ENV_FILE, `WADR_BRIDGE_TOKEN=${crypto.randomBytes(16).toString('hex')}\n`);
  console.log('Generated a bridge token in .env');
}

if (!fs.existsSync(path.join(ROOT, 'bridge', 'node_modules'))) {
  console.error('Bridge dependencies missing. Run: npm run setup');
  process.exit(1);
}

const children = [
  // uv is uv.exe on Windows and spawn will not find it without a shell; passing
  // one string rather than an args array keeps that shell call unambiguous.
  ['api', 'uv run uvicorn wadr.api.app:app --port 8000', [], ROOT, true],
  ['bridge', process.execPath, ['--env-file-if-exists=../.env', 'index.js'], path.join(ROOT, 'bridge'), false],
].map(([name, command, args, cwd, shell]) => {
  const child = spawn(command, args, { cwd, shell });
  const tag = (stream) => (data) =>
    String(data).replace(/\n$/, '').split('\n').forEach((l) => stream(`[${name}] ${l}`));
  child.stdout.on('data', tag(console.log));
  child.stderr.on('data', tag(console.error));
  child.on('exit', (code) => {
    // One half of the product is no product. Take the other down so a crash is
    // obvious, instead of a half-running system that 500s every upload.
    console.error(`[${name}] exited (${code}) - stopping everything`);
    stop();
    process.exit(code ?? 1);
  });
  return child;
});

let stopping = false;
function stop() {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    // On Windows the API runs under a shell, so killing the child leaves uvicorn
    // holding :8000. /T kills the tree - synchronously, because the caller
    // exits the moment this returns.
    if (WINDOWS) spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    else child.kill();
  }
}

process.on('SIGINT', () => { stop(); process.exit(0); });
process.on('SIGTERM', () => { stop(); process.exit(0); });

console.log('WADR starting - web app on http://localhost:8000 (ctrl-c stops both)');
