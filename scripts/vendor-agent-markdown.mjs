// Native ES modules: ship local copies so rendering needs no runtime CDN.
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
const root = new URL('../', import.meta.url);
const dest = new URL('client/vendor/markdown/', root);
await mkdir(dest, { recursive: true });
for (const [source, target] of [
    ['marked/lib/marked.esm.js', 'marked.js'], ['marked/LICENSE', 'marked.LICENSE'],
    ['dompurify/dist/purify.es.mjs', 'purify.js'], ['dompurify/LICENSE', 'dompurify.LICENSE'],
    ['dompurify/LICENSE-MPL', 'dompurify.LICENSE-MPL'],
]) await copyFile(new URL(`node_modules/${source}`, root), new URL(target, dest));
for (const name of ['marked.js', 'purify.js']) {
    const path = new URL(name, dest);
    await writeFile(path, (await readFile(path, 'utf8')).replace(/^\/\/# sourceMappingURL=.*$/gm, ''));
}
const versions = {};
for (const pkg of ['marked', 'dompurify']) versions[pkg] = JSON.parse(await readFile(new URL(`node_modules/${pkg}/package.json`, root), 'utf8')).version;
await writeFile(new URL('versions.json', dest), JSON.stringify(versions, null, 2) + '\n');
