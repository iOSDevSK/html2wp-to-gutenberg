#!/usr/bin/env node
// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Two gates Gutenberg itself decides, without a browser:
 *
 *   valid       every block's stored markup is what its save() produces
 *               (wp.blocks.validateBlock — the check behind "This block
 *               contains unexpected or invalid content")
 *   round trip  serialize(parse(x)) === x, byte for byte: the file is exactly
 *               what the editor would write back, so opening and saving a
 *               page changes nothing
 *
 *   node block-roundtrip.cjs file.html [more.html …]
 *   node block-roundtrip.cjs --canonical file.html      rewrite a file whose
 *        blocks are ALL valid into the serializer's own bytes (attribute
 *        order, whitespace between blocks). Never a repair: one invalid block
 *        and the file is left alone. Nothing here calls createBlock.
 *
 * The packages are the ones one WordPress release ships — every @wordpress/*
 * package in the tree pinned to its wp-X.Y dist-tag, or a second copy of
 * @wordpress/blocks registers the blocks where validateBlock does not look:
 *   bash block-node-setup.sh <dir> wp-7.0
 *   NODE_PATH=<dir>/node_modules node block-roundtrip.cjs …
 *
 * Exit 0 all valid and byte-stable; 1 an invalid block or a round-trip
 * difference; 2 usage.
 */
const fs = require('node:fs');
const { JSDOM, VirtualConsole } = require('jsdom');

const dom = new JSDOM('<!doctype html><html><body></body></html>', { virtualConsole: new VirtualConsole() });
for (const k of ['window', 'document', 'HTMLElement', 'Node', 'DOMParser', 'MutationObserver', 'getComputedStyle']) {
  globalThis[k] = k === 'window' ? dom.window : dom.window[k];
}
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);

const quiet = (fn) => {
  const saved = { log: console.log, info: console.info, warn: console.warn, error: console.error };
  console.log = console.info = console.warn = console.error = () => {};
  try { return fn(); } finally { Object.assign(console, saved); }
};
const { registerCoreBlocks } = require('@wordpress/block-library');
const { parse, serialize, validateBlock } = require('@wordpress/blocks');
quiet(() => registerCoreBlocks());

function walk(blocks, out, path = []) {
  blocks.forEach((b, i) => {
    if (!b.name) return;
    const where = [...path, i];
    const [ok, log] = quiet(() => validateBlock(b));
    if (!ok) out.push({ block: b.name, at: where.join('.'), why: (log || []).map((l) => String(l.args ? l.args.join(' ') : l)).join(' | ').slice(0, 300) });
    walk(b.innerBlocks || [], out, where);
  });
}

const args = process.argv.slice(2);
const canonical = args[0] === '--canonical';
const files = canonical ? args.slice(1) : args;
if (!files.length) {
  console.error('usage: node block-roundtrip.cjs [--canonical] file.html …');
  process.exit(2);
}
let failed = false;
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  const blocks = quiet(() => parse(text));
  const invalid = [];
  walk(blocks, invalid);
  const again = quiet(() => serialize(blocks));
  const same = again === text;
  if (canonical && !invalid.length && !same) {
    fs.writeFileSync(file, again);
  }
  const stable = canonical ? !invalid.length : same;
  console.log(`${file}: ${invalid.length ? invalid.length + ' invalid' : 'valid'}, round trip ${same ? 'byte-identical' : canonical && !invalid.length ? 'canonicalised' : 'DIFFERS'}`);
  for (const bad of invalid.slice(0, 8)) console.log(`  invalid ${bad.block} at ${bad.at}: ${bad.why}`);
  if (!same && !canonical) {
    let i = 0;
    while (i < text.length && text[i] === again[i]) i++;
    console.log(`  first difference at byte ${i}: stored ${JSON.stringify(text.slice(i, i + 80))} / serialized ${JSON.stringify(again.slice(i, i + 80))}`);
  }
  if (invalid.length || !stable) failed = true;
}
process.exit(failed ? 1 : 0);
