import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../dist/', import.meta.url));
const headers = JSON.parse(await readFile(path.join(root, 'headers.json')));
const types = { '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.mjs':'text/javascript; charset=utf-8', '.svg':'image/svg+xml', '.png':'image/png', '.jpg':'image/jpeg', '.webp':'image/webp', '.ico':'image/x-icon', '.ttf':'font/ttf', '.vcf':'text/vcard; charset=utf-8', '.webmanifest':'application/manifest+json', '.json':'application/json', '.txt':'text/plain; charset=utf-8', '.xml':'application/xml' };
const port = Number(process.env.PORT || 8767);
http.createServer(async (request,response) => {
  if (!['GET','HEAD'].includes(request.method)) { response.writeHead(405); response.end(); return; }
  try {
    const pathname = decodeURIComponent(new URL(request.url,'http://localhost').pathname);
    const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
    let file = path.resolve(root, relative);
    if (!file.startsWith(root)) { response.writeHead(403); response.end(); return; }
    let code = 200;
    try { if (!(await stat(file)).isFile()) throw new Error('Not a file'); }
    catch { file=path.join(root,'404.html'); code=404; }
    const data = await readFile(file);
    const extension = path.extname(file);
    const extra = extension === '.vcf' ? { 'Content-Disposition':'inline; filename="romeo-health-heaven.vcf"' } : {};
    response.writeHead(code,{...headers,...extra,'Content-Type':types[extension] || 'application/octet-stream','Content-Length':data.length});
    response.end(request.method === 'HEAD' ? undefined : data);
  } catch { response.writeHead(400); response.end('Bad request'); }
}).listen(port,'127.0.0.1',() => console.log(`Romeo’s card: http://127.0.0.1:${port}`));
