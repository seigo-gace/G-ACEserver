// Browser-independent behavior tests; not a replacement for real browser E2E.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/ui.js', 'utf8');

function environment() {
  const elements = new Map();
  function element() {
    return {textContent: '', value: '', disabled: false, children: [], handlers: {},
      addEventListener(name, fn) {this.handlers[name] = fn;},
      replaceChildren(...children) {this.children = children;},
      append(child) {this.children.push(child);}, click() {},
      set innerHTML(value) {throw new Error('unsafe HTML insertion');}};
  }
  function get(id) {if (!elements.has(id)) elements.set(id, element()); return elements.get(id);}
  const context = vm.createContext({document: {getElementById: get, createElement: element},
    URLSearchParams, AbortController, Blob, URL, setTimeout, window: {},
    fetch: async () => {throw new Error('unexpected network');}});
  vm.runInContext(source, context);
  vm.runInContext("credential='synthetic-fixture';", context);
  return {context, get, run: code => vm.runInContext(code, context)};
}

async function main() {
  {
    const e = environment();
    e.context.fetch = async () => ({ok: true, json: async () => ({entries: [{name: '<img onerror=alert(1)>', kind: 'file', size: 1}], next: 'cursor'})});
    await e.run('listFiles()');
    assert.equal(e.get('file-list').children[0].children[0].textContent, '<img onerror=alert(1)> (1 bytes) 保存');
    assert.equal(e.get('files-next').disabled, false);
  }
  {
    const e = environment();
    let resolve;
    e.context.fetch = () => new Promise(r => {resolve = r;});
    const refreshing = e.run('refresh()');
    e.get('logout').handlers.click();
    resolve({ok: true, json: async () => ({uptime_seconds: 1, storage_ready: true})});
    await refreshing;
    assert.equal(e.get('status').textContent, '未確認');
    assert.equal(e.get('message').textContent, '接続を解除しました。');
  }
  {
    const e = environment();
    let cancelled = false;
    e.context.fetch = async () => ({ok: true, body: {getReader: () => ({
      read: async () => ({done: false, value: new Uint8Array(17 * 1024 * 1024)}),
      cancel: async () => {cancelled = true;}})}});
    await e.run("downloadFile({name:'growing-file',size:1})");
    assert.equal(cancelled, true);
    assert.match(e.get('file-message').textContent, /保存できません/);
  }
  {
    const e = environment();
    let signal;
    e.context.fetch = (url, options) => new Promise((resolve, reject) => {
      signal = options.signal;
      signal.addEventListener('abort', () => reject(Object.assign(new Error(), {name: 'AbortError'})));
    });
    const downloading = e.run("downloadFile({name:'sample',size:1})");
    e.get('logout').handlers.click();
    await downloading;
    assert.equal(signal.aborted, true);
    assert.equal(e.get('file-message').textContent, '未確認');
  }
  console.log('UI_BEHAVIOR_TESTS=4_PASS;BROWSER_E2E=NOT_VERIFIED');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
