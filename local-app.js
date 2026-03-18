const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT_DIR = __dirname;
const ENTRY_FILE = 'storyboard.html';
const HOST = '127.0.0.1';
const USER_DATA_DIR = path.join(ROOT_DIR, '.storyframe-profile');

const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.webm': 'video/webm'
};

const entryPath = path.join(ROOT_DIR, ENTRY_FILE);
if (!fs.existsSync(entryPath)) {
  throw new Error(`Entry file not found: ${ENTRY_FILE}`);
}

const browserCandidates = [
  path.join(process.env['ProgramFiles'] || '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  path.join(process.env['ProgramFiles(x86)'] || '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  path.join(process.env.LOCALAPPDATA || '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  path.join(process.env['ProgramFiles'] || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
  path.join(process.env['ProgramFiles(x86)'] || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
  path.join(process.env.LOCALAPPDATA || '', 'Google', 'Chrome', 'Application', 'chrome.exe')
].filter(Boolean);

function showHelp() {
  console.log('StoryFrame local launcher');
  console.log('');
  console.log('Usage:');
  console.log('  node local-app.js');
  console.log('  node local-app.js --print-url');
}

function findBrowserExecutable() {
  return browserCandidates.find(candidate => fs.existsSync(candidate)) || null;
}

function safeResolveRequest(urlPath) {
  const decoded = decodeURIComponent((urlPath || '/').split('?')[0]);
  const relative = decoded === '/' ? ENTRY_FILE : decoded.replace(/^\/+/, '');
  const resolved = path.resolve(ROOT_DIR, relative);
  if (!resolved.startsWith(ROOT_DIR)) return null;
  return resolved;
}

function sendFile(response, filePath) {
  fs.readFile(filePath, (error, buffer) => {
    if (error) {
      response.writeHead(error.code === 'ENOENT' ? 404 : 500, { 'Content-Type': 'text/plain; charset=utf-8' });
      response.end(error.code === 'ENOENT' ? 'Not found' : 'Internal server error');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    response.writeHead(200, {
      'Content-Type': MIME_TYPES[ext] || 'application/octet-stream',
      'Cache-Control': 'no-store'
    });
    response.end(buffer);
  });
}

function openBrowserApp(url) {
  const browserPath = findBrowserExecutable();
  if (!browserPath) return null;

  fs.mkdirSync(USER_DATA_DIR, { recursive: true });

  const args = [
    `--user-data-dir=${USER_DATA_DIR}`,
    `--app=${url}`,
    '--window-size=1600,1000',
    '--disable-session-crashed-bubble',
    '--disable-features=TranslateUI'
  ];

  return spawn(browserPath, args, {
    cwd: ROOT_DIR,
    stdio: 'ignore'
  });
}

function openDefaultBrowser(url) {
  const child = spawn('cmd', ['/c', 'start', '""', url], {
    cwd: ROOT_DIR,
    stdio: 'ignore',
    windowsHide: true
  });
  child.unref();
}

function main() {
  if (process.argv.includes('--help')) {
    showHelp();
    return;
  }

  let server;
  let shuttingDown = false;

  const shutdown = () => {
    if (shuttingDown) return;
    shuttingDown = true;
    if (server) {
      server.close(() => process.exit(0));
      setTimeout(() => process.exit(0), 2000).unref();
    } else {
      process.exit(0);
    }
  };

  server = http.createServer((request, response) => {
    const filePath = safeResolveRequest(request.url);
    if (!filePath) {
      response.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      response.end('Forbidden');
      return;
    }
    sendFile(response, filePath);
  });

  server.listen(0, HOST, () => {
    const address = server.address();
    const url = `http://${HOST}:${address.port}/`;

    if (process.argv.includes('--print-url')) {
      console.log(url);
      shutdown();
      return;
    }

    const browserProcess = openBrowserApp(url);
    if (browserProcess) {
      console.log(`StoryFrame local app started: ${url}`);
      console.log('Close the app window to stop the local server.');
      browserProcess.on('exit', shutdown);
      return;
    }

    openDefaultBrowser(url);
    console.log(`Browser app mode was not found. Opened the default browser instead: ${url}`);
    console.log('Press Ctrl+C to stop the server.');
  });

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
  process.on('uncaughtException', error => {
    console.error(error);
    shutdown();
  });
}

main();
