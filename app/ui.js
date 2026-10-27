let credential = '';
let generation = 0;
let fileGeneration = 0;
let directory = '';
let nextPage = null;
const downloads = new Set();
const element = id => document.getElementById(id);
async function read(path) {
  const response = await fetch(path, {headers: {Authorization: 'Bearer ' + credential}, cache: 'no-store'});
  if (response.status === 401) throw new Error('認証できません。認証値を確認して接続し直してください。');
  if (!response.ok) throw new Error('保存領域を利用できません。接続を確認して再確認してください。');
  return response.json();
}
async function refresh() {
  const requestGeneration = ++generation;
  element('status').textContent = '確認中';
  element('storage').textContent = '未確認';
  try {
    const status = await read('/status');
    if (requestGeneration !== generation) return;
    element('status').textContent = `Web API: 稼働中\n稼働時間: ${status.uptime_seconds}秒\n保存領域: ${status.storage_ready ? '接続済み' : '未接続'}\nKB / TGS: 未統合`;
    element('message').textContent = '接続済み。認証値はこの画面を閉じると消去されます。';
    try {
      const storage = await read('/storage');
      if (requestGeneration !== generation) return;
      element('storage').textContent = `空き: ${storage.summary.free_gib} GiB / 全体: ${storage.summary.total_gib} GiB`;
    } catch (error) { if (requestGeneration === generation) element('storage').textContent = error.message; }
  } catch (error) { if (requestGeneration === generation) { element('status').textContent = '未確認'; element('message').textContent = '接続できません。認証値とサービスの状態を確認してください。'; } }
}
element('connect').addEventListener('submit', event => {event.preventDefault(); credential = element('credential').value; element('credential').value = ''; refresh();});
element('refresh').addEventListener('click', refresh);
element('logout').addEventListener('click', () => {generation++; fileGeneration++; for (const transfer of downloads) transfer.abort(); credential = ''; directory = ''; nextPage = null; element('credential').value = ''; element('status').textContent = '未確認'; element('storage').textContent = '未確認'; element('file-list').replaceChildren(); element('file-path').textContent = '/'; element('files-next').disabled = true; element('file-message').textContent = '未確認'; element('message').textContent = '接続を解除しました。';});

async function listFiles(after = '') {
  const requestGeneration = ++fileGeneration;
  element('file-message').textContent = '確認中';
  element('file-list').replaceChildren();
  element('files-next').disabled = true;
  element('file-path').textContent = '/' + directory;
  try {
    const query = new URLSearchParams({path: directory, after, limit: '100'});
    const page = await read('/files?' + query);
    if (requestGeneration !== fileGeneration) return;
    for (const entry of page.entries) {
      const row = document.createElement('li');
      const button = document.createElement('button');
      button.textContent = entry.name + (entry.kind === 'directory' ? ' /' : ` (${entry.size} bytes) 保存`);
      button.onclick = () => {
        if (entry.kind === 'directory') { directory = [directory, entry.name].filter(Boolean).join('/'); listFiles(); }
        else downloadFile(entry);
      };
      row.append(button);
      element('file-list').append(row);
    }
    nextPage = page.next;
    element('files-next').disabled = !nextPage;
    element('file-message').textContent = page.entries.length ? `${page.entries.length}件を表示しました。` : 'このフォルダーに表示できるファイルはありません。';
  } catch (error) { if (requestGeneration === fileGeneration) element('file-message').textContent = '一覧を取得できません。認証と保存領域の接続を確認して再試行してください。'; }
}

async function downloadFile(entry) {
  const requestGeneration = fileGeneration;
  const filePath = [directory, entry.name].filter(Boolean).join('/');
  let writer;
  const transfer = new AbortController();
  downloads.add(transfer);
  try {
    if ('showSaveFilePicker' in window) {
      const handle = await window.showSaveFilePicker({suggestedName: entry.name});
      if (requestGeneration !== fileGeneration || !credential) return;
      writer = await handle.createWritable();
    } else if (entry.size > 16 * 1024 * 1024) {
      element('file-message').textContent = 'この大きさの保存には、ファイル保存に対応したブラウザ（Edgeなど）を使用してください。';
      return;
    }
    const response = await fetch('/download?' + new URLSearchParams({path: filePath}), {headers: {Authorization: 'Bearer ' + credential}, cache: 'no-store', signal: transfer.signal});
    if (!response.ok || requestGeneration !== fileGeneration) throw new Error('download failed');
    if (writer) { await response.body.pipeTo(writer); writer = null; }
    else {
      const chunks = [];
      const reader = response.body.getReader();
      let bytes = 0;
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        bytes += value.byteLength;
        if (bytes > 16 * 1024 * 1024) { await reader.cancel(); throw new Error('download too large'); }
        chunks.push(value);
      }
      const blob = new Blob(chunks);
      if (blob.size > 16 * 1024 * 1024 || requestGeneration !== fileGeneration) throw new Error('download changed');
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = entry.name; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    }
    if (requestGeneration === fileGeneration) element('file-message').textContent = 'ダウンロードが完了しました。';
  } catch (error) {
    if (writer) await writer.abort().catch(() => {});
    if (requestGeneration === fileGeneration) element('file-message').textContent = error.name === 'AbortError' ? '保存を中止しました。' : '保存できませんでした。接続を確認して再試行してください。';
  } finally { downloads.delete(transfer); }
}
element('files-refresh').addEventListener('click', () => listFiles());
element('files-back').addEventListener('click', () => {directory = directory.split('/').slice(0, -1).join('/'); listFiles();});
element('files-next').addEventListener('click', () => {if (nextPage) listFiles(nextPage);});
