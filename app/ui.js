let credential = '';
let generation = 0;
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
element('logout').addEventListener('click', () => {generation++; credential = ''; element('credential').value = ''; element('status').textContent = '未確認'; element('storage').textContent = '未確認'; element('message').textContent = '接続を解除しました。';});
