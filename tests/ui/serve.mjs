// Serve only public client modules and the fixture, never repository env/data.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, sep, extname } from 'node:path';
const root = process.cwd();
const client = resolve(root, 'client') + sep;
createServer(async (req, res) => {
    try {
        const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname).replace(/^\/+/, '');
        const path = resolve(root, name);
        if (!path.startsWith(client) && path !== resolve(root, 'tests/ui/agent-preview.html')) throw new Error('not public');
        res.setHeader('Content-Type', extname(path) === '.js' ? 'application/javascript' : extname(path) === '.json' ? 'application/json' : 'text/html; charset=utf-8');
        res.end(await readFile(path));
    } catch { res.writeHead(404); res.end('Not found'); }
}).listen(4178, '127.0.0.1');
