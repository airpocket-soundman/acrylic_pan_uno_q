const $ = id => document.getElementById(id);
const classNames = ['AREA 1','AREA 2','AREA 3','AREA 4','AREA 5','AREA 6','AREA 7','AREA 8'];
let timer = null;
let lastTimestamp = null;

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
}

function normalized(scores) {
  if (!scores || !scores.length) return Array(8).fill(0);
  const max = Math.max(...scores);
  const values = scores.map(value => Math.exp((value - max) * 3));
  const total = values.reduce((sum, value) => sum + value, 0) || 1;
  return values.map(value => value / total);
}

function formatTime(ns) {
  if (!ns) return '—';
  return new Date(Number(BigInt(ns) / 1000000n)).toLocaleTimeString('ja-JP', {hour12:false});
}

function drawPanel(latest) {
  const probabilities = normalized(latest && latest.scores);
  $('panel').innerHTML = classNames.map((name, index) => {
    const probability = probabilities[index];
    const active = latest && latest.predicted_class === index;
    const alpha = 0.08 + probability * 0.82;
    return `<div class="zone${active ? ' active' : ''}" style="--heat:${alpha.toFixed(3)}">` +
      `<span>${name}</span><b>${latest ? (probability * 100).toFixed(1) + '%' : '—'}</b><small>CLASS ${index}</small></div>`;
  }).join('') + '<i class="sensor"></i>';
}

function drawScores(latest) {
  const scores = latest && latest.scores ? latest.scores : Array(8).fill(0);
  const min = Math.min(0, ...scores), max = Math.max(1, ...scores), range = max - min || 1;
  $('scores').innerHTML = scores.map((value, index) => {
    const width = Math.max(1, (value - min) / range * 100);
    const active = latest && latest.predicted_class === index;
    return `<div class="score-row${active ? ' active' : ''}"><span>${String(index).padStart(2,'0')}</span>` +
      `<div><i style="width:${width.toFixed(2)}%"></i></div><b>${latest ? Number(value).toFixed(4) : '—'}</b></div>`;
  }).join('');
}

function drawHistory(history) {
  const rows = [...history].reverse().slice(0, 16);
  $('history').innerHTML = rows.length ? rows.map(item => `<tr>` +
    `<td>#${escapeHtml(item.case_id)}</td><td>${escapeHtml(item.expected_class)}</td>` +
    `<td><b class="class-chip">${escapeHtml(item.predicted_class)}</b></td>` +
    `<td><span class="table-result ${item.passed ? 'pass' : 'fail'}">${item.passed ? 'PASS' : 'FAIL'}</span></td>` +
    `<td>${(Number(item.inference_us) / 1000).toFixed(2)} ms</td><td>${formatTime(item.created_at_unix_ns)}</td></tr>`).join('') :
    '<tr><td colspan="6" class="empty">推論結果を待っています。</td></tr>';
}

function render(data) {
  const online = data.connected && data.app_running;
  $('pulse').classList.toggle('online', online);
  $('connectionLabel').textContent = online ? 'UNO Q ONLINE' : 'UNO Q OFFLINE';
  $('deviceLabel').textContent = data.device ? `${data.device} / USB ADB` : 'USB / ADB';
  $('heroText').textContent = online ? 'STM32からBridgeで届くダミーケースをQRB2210で推論しています。' : 'UNO Qの接続またはアプリ状態を確認してください。';
  $('sampleCount').textContent = data.sample_count || '0';
  $('accuracy').textContent = data.accuracy === null ? '—' : `${(data.accuracy * 100).toFixed(1)}%`;
  $('passCount').textContent = `${data.pass_count || 0} / ${data.sample_count || 0} PASS`;
  $('latency').textContent = data.latency_us.latest === null ? '—' : `${(data.latency_us.latest / 1000).toFixed(2)} ms`;
  $('latencyAverage').textContent = data.latency_us.average === null ? '平均 —' : `平均 ${(data.latency_us.average / 1000).toFixed(2)} ms`;
  const latest = data.latest;
  $('latestClass').textContent = latest ? `CLASS ${latest.predicted_class}` : '—';
  $('latestExpected').textContent = latest ? `期待値 CLASS ${latest.expected_class}` : '期待値 —';
  $('modelLabel').textContent = data.model;
  $('updatedAt').textContent = latest ? formatTime(latest.created_at_unix_ns) : '—';
  const badge = $('resultBadge');
  badge.className = `result ${latest ? (latest.passed ? 'pass' : 'fail') : 'neutral'}`;
  badge.textContent = latest ? (latest.passed ? 'PASS' : 'FAIL') : 'WAITING';
  drawPanel(latest); drawScores(latest); drawHistory(data.history || []);
  $('error').hidden = !data.error;
  $('error').textContent = data.error || '';
  if (latest && latest.created_at_unix_ns !== lastTimestamp) {
    lastTimestamp = latest.created_at_unix_ns;
    document.body.classList.remove('tick');
    requestAnimationFrame(() => document.body.classList.add('tick'));
  }
}

async function refresh() {
  try {
    const response = await fetch('/api/status', {cache:'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    render({connected:false,app_running:false,device:null,sample_count:0,pass_count:0,accuracy:null,latency_us:{latest:null,average:null},latest:null,history:[],model:'apan_dummy_128x32x8',error:error.message});
  }
}

function schedule() {
  clearInterval(timer);
  if ($('autoRefresh').checked) timer = setInterval(refresh, 1000);
}

$('refreshButton').addEventListener('click', refresh);
$('autoRefresh').addEventListener('change', schedule);
drawPanel(null); drawScores(null); drawHistory([]); refresh(); schedule();
