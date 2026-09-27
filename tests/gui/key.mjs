// Presses a key with Control held, in the page of the headless Chrome on
// 127.0.0.1:$CDP_PORT (Broadway turns the modifiers of key events into
// GDK's): node key.mjs z   presses Ctrl+Z. gimp-devtools'
// cdp.mjs has no modifier keys.
//
// Copyright 2026 David
// SPDX-License-Identifier: GPL-3.0-or-later
const port = Number(process.env.CDP_PORT || 9333);
const key = process.argv[2];
if (!key || key.length !== 1) {
  console.error('usage: node key.mjs <letter>');
  process.exit(1);
}
const tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = tabs.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
let id = 0;
const pending = {};
ws.onmessage = e => { const m = JSON.parse(e.data); if (pending[m.id]) pending[m.id](m); };
const send = (method, params) => new Promise(r => {
  pending[++id] = r;
  ws.send(JSON.stringify({ id, method, params }));
});
const CTRL = 2;
const vk = key.toUpperCase().charCodeAt(0);
const ctrl = { key: 'Control', code: 'ControlLeft', windowsVirtualKeyCode: 17, nativeVirtualKeyCode: 17 };
const k = { key, code: 'Key' + key.toUpperCase(), windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk };
// as a hand would: Control held a moment before the key and after it
const pause = ms => new Promise(r => setTimeout(r, ms));
await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', modifiers: CTRL, ...ctrl });
await pause(150);
await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', modifiers: CTRL, ...k });
await pause(100);
await send('Input.dispatchKeyEvent', { type: 'keyUp', modifiers: CTRL, ...k });
await pause(150);
await send('Input.dispatchKeyEvent', { type: 'keyUp', modifiers: 0, ...ctrl });
ws.close();
process.exit(0);
