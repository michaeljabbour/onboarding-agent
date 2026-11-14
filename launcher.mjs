// Small local process manager. It never stops an unrecognized process.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import net from 'node:net';
import {spawn, execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const base = process.env.CLIMB_INSTALL_DIR || (process.platform === 'darwin' ? path.join(os.homedir(), 'Library/Application Support/The Climb') : path.join(process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local/share'), 'the-climb'));
const port = Number(process.env.CLIMB_PORT || 4747);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Use a port from 1024 to 65535.');
const url = `http://localhost:${port}/`;
const pidFile = path.join(base, `agent-${port}.json`);
const log = path.join(base, 'logs', `agent-${port}.log`);
const command = process.argv[2];
const source = path.dirname(fileURLToPath(import.meta.url));
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

async function health() {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/api/health`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Climb': '1'}, body: '{}', signal: AbortSignal.timeout(4000)});
    if (!r.ok) return null;
    const h = await r.json();
    return typeof h.agent === 'string' && typeof h.node === 'string' && Array.isArray(h.steps) && h.steps.includes('ask') && Array.isArray(h.checks) ? h : null;
  } catch { return null; }
}
function isListening() {
  return new Promise(resolve => {
    const socket = net.createConnection({host: '127.0.0.1', port});
    const done = value => { socket.destroy(); resolve(value); };
    socket.setTimeout(1000, () => done(false));
    socket.once('connect', () => done(true));
    socket.once('error', () => done(false));
  });
}
function identity(pid) {
  if (!Number.isInteger(pid) || pid < 2) return '';
  try { return execFileSync('/bin/ps', ['-p', String(pid), '-o', 'uid=', '-o', 'lstart=', '-o', 'command='], {encoding: 'utf8', timeout: 2000}).trim(); }
  catch { return ''; }
}
function openGuide() {
  console.log(`Your connected guide: ${url}`);
  if (process.env.CLIMB_NO_OPEN === '1') return;
  const opener = process.platform === 'darwin' ? 'open' : 'xdg-open';
  const p = spawn(opener, [url], {detached: true, stdio: 'ignore'});
  p.on('error', () => console.log('Open that address in your browser.'));
  p.unref();
}
function ownedRecord() {
  try {
    const r = JSON.parse(fs.readFileSync(pidFile, 'utf8'));
    const expected = path.join(base, 'app', 'climb-agent.mjs');
    const current = identity(r.pid);
    return r.identity && current === r.identity && r.script === expected && current.includes(expected) ? r : null;
  } catch { return null; }
}
function updatePending() {
  const installed = path.join(base, 'app');
  if (source === installed) return false;
  return ['climb-agent.mjs', 'the-climb.html', 'launcher.mjs', 'START.sh', 'START.command', 'STOP.command', 'README-start.txt'].some(file => {
    try { return !fs.readFileSync(path.join(source, file)).equals(fs.readFileSync(path.join(installed, file))); }
    catch { return fs.existsSync(path.join(source, file)); }
  });
}
async function existing(allowUpdate = false) {
  const h = await health();
  if (h) {
    if (allowUpdate && updatePending()) {
      const owned = ownedRecord();
      if (owned && h.activeRuns === 0) {
        console.log('Updating this installation. Your answers are kept.');
        process.kill(owned.pid, 'SIGTERM');
        for (let i = 0; i < 40; i++) {
          if (!identity(owned.pid) && !await isListening()) { fs.rmSync(pidFile, {force: true}); return null; }
          await pause(250);
        }
        throw new Error('The previous agent has not stopped yet. Try START.command again in a moment.');
      }
      console.log(owned ? 'Your agent has active work, or cannot yet report whether it is idle. Finish that work, use STOP.command, then run START.command to apply this update.' : 'An agent from another folder is already running. This launcher will keep it. Stop that copy when its work is finished, then run START.command to install this version.');
    }
    console.log('The Climb is already running.');
    return h;
  }
  if (await isListening()) throw new Error(`Port ${port} belongs to another program or an unresponsive agent. Nothing was stopped. Close that program, or run with CLIMB_PORT set to another port.`);
  return null;
}
async function start() {
  fs.mkdirSync(path.join(base, 'logs'), {recursive: true, mode: 0o700});
  const lock = path.join(base, `.launch-${port}`);
  try { fs.mkdirSync(lock, {mode: 0o700}); }
  catch {
    let stale = false;
    try {
      const owner = JSON.parse(fs.readFileSync(path.join(lock, 'owner.json'), 'utf8'));
      stale = !identity(owner.pid) || (owner.identity && owner.identity !== identity(owner.pid));
    } catch { stale = Date.now() - fs.statSync(lock).mtimeMs > 60000; }
    if (stale) {
      fs.rmSync(lock, {recursive: true, force: true});
      return start();
    }
    // A concurrent double-click may already be doing the work. Do not spawn twice.
    for (let i = 0; i < 30; i++) {
      const h = await health();
      if (h) {
        if (h.assistantReady === false) throw new Error('The agent is running, but Claude is not ready. Run START.command to finish sign-in.');
        openGuide(); return;
      }
      await pause(500);
    }
    throw new Error(`Another launch has not finished. If no launcher is open, remove ${lock} and try again.`);
  }
  fs.writeFileSync(path.join(lock, 'owner.json'), JSON.stringify({pid: process.pid, identity: identity(process.pid)}), {mode: 0o600});
  try {
    const running = await existing();
    if (running) {
      if (running.assistantReady === false) throw new Error('The agent is running, but Claude is not ready. Run START.command to finish sign-in.');
      openGuide(); return;
    }
    const script = path.join(base, 'app', 'climb-agent.mjs');
    const fd = fs.openSync(log, 'a', 0o600);
    let p;
    try { p = spawn(process.execPath, [script, '--no-open'], {cwd: path.dirname(script), detached: true, stdio: ['ignore', fd, fd], env: process.env}); }
    finally { fs.closeSync(fd); }
    await new Promise((resolve, reject) => { p.once('spawn', resolve); p.once('error', reject); });
    p.unref();
    if (!p.pid) throw new Error(`The agent could not launch. See ${log}`);
    const record = {pid: p.pid, identity: identity(p.pid), script, port};
    fs.writeFileSync(pidFile, JSON.stringify(record), {mode: 0o600});
    for (let i = 0; i < 40; i++) {
      const h = await health();
      if (h) {
        if (h.assistantReady === false) throw new Error(`The agent is running, but Claude is not ready. Run START.command to finish sign-in. See ${log}`);
        console.log('The Climb is ready.'); openGuide(); return;
      }
      if (!identity(p.pid)) throw new Error(`The agent stopped during startup. See ${log}`);
      await pause(250);
    }
    throw new Error(`The agent has not answered yet. See ${log}. Run START.command again to reconnect.`);
  } finally { fs.rmSync(lock, {recursive: true, force: true}); }
}
function stop() {
  let r;
  try { r = JSON.parse(fs.readFileSync(pidFile, 'utf8')); }
  catch { console.log('No agent launched by this installer is recorded. Nothing was stopped.'); return; }
  const current = identity(r.pid);
  if (!current) { fs.rmSync(pidFile, {force: true}); console.log('The Climb is already stopped.'); return; }
  const expectedScript = path.join(base, 'app', 'climb-agent.mjs');
  if (!r.identity || current !== r.identity || r.script !== expectedScript || !current.includes(expectedScript)) throw new Error('The recorded process no longer matches this installation. Nothing was stopped.');
  process.kill(r.pid, 'SIGTERM');
  fs.rmSync(pidFile, {force: true});
  console.log('The Climb is stopping. Your answers and files are kept.');
}
try {
  if (command === 'existing') {
    const h = await existing(true);
    if (!h) process.exitCode = 10;
    else if (h.assistantReady === false) { console.log('The agent is running; finishing Claude setup before opening it.'); process.exitCode = 11; }
    else openGuide();
  }
  else if (command === 'start') await start();
  else if (command === 'stop') stop();
  else throw new Error('Use existing, start, or stop.');
} catch (e) { console.error(e.message); process.exitCode = 1; }
