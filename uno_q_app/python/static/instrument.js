const $ = id => document.getElementById(id);
const STORAGE_KEY = 'acrylicPanInstrumentV1';
const DEFAULT_NOTES = ['C4','D4','E4','F4','G4','A4','B4','C5','D5','E5','F5','G5'];
const MARIO_NOTES = ['E4', 'G4', 'A4', 'A#4', 'B4', 'C5', 'E5', 'G5'].concat(['A5','B5','C6','E6']);
const DEFAULTS = {instrument:'steel_drum',masterVolume:.70,transpose:0,brightness:.65,attack:.005,decay:.35,sustain:.18,release:.90,echoMix:.18,echoDelay:.18,echoFeedback:.24,velocity:.70,retriggerGuardMs:80,notes:DEFAULT_NOTES};
const NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
let settings = loadSettings();
let lastPlayedSequence = null;
let performanceEnabled = false;
let pollBusy = false;
let inferenceLoopRunning = false;
let audio = null;
let audioPrimeTimer = null;
let hitClearTimer = null;
let cameraStream = null;
let panelClassCount = 8;
const CAMERA_STORAGE_KEY = 'acrylicPanUnoQCameraStreamUrl';
const DEFAULT_CAMERA_STREAM = `${window.location.protocol}//${window.location.hostname}:4912/embed`;

async function api(path, body) {
  const options = body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
  const response = await fetch(path, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const error = new Error(`${data.error || response.statusText} (${path})`);
    error.status = response.status;
    throw error;
  }
  if(path==='/api/status'&&data.panel){window.panelProfileUi?.sync(data);configurePanel(data.panel);}
  return data;
}

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    const legacyNotes=validNotes(saved.notes)?[...saved.notes]:[...DEFAULT_NOTES];
    const profiles=Array.isArray(saved.mappingProfiles)?saved.mappingProfiles.filter(profile=>profile&&typeof profile.id==='string'&&validNotes(profile.notes)).map(profile=>({id:profile.id,name:String(profile.name||'名称未設定').slice(0,40),notes:[...profile.notes]})):[];
    if(!profiles.length)profiles.push({id:'mapping-default',name:'標準プロファイル',notes:legacyNotes});
    if(!profiles.some(profile=>profile.id==='mapping-mario'||profile.name.toLowerCase()==='mario'))profiles.push({id:'mapping-mario',name:'mario',notes:[...MARIO_NOTES]});
    const activeId=profiles.some(profile=>profile.id===saved.activeMappingProfileId)?saved.activeMappingProfileId:profiles[0].id;
    const active=profiles.find(profile=>profile.id===activeId);
    return {...DEFAULTS,...saved,notes:[...active.notes],mappingProfiles:profiles,activeMappingProfileId:activeId};
  } catch (_) { return {...DEFAULTS,notes:[...DEFAULT_NOTES],mappingProfiles:[{id:'mapping-default',name:'標準プロファイル',notes:[...DEFAULT_NOTES]},{id:'mapping-mario',name:'mario',notes:[...MARIO_NOTES]}],activeMappingProfileId:'mapping-default'}; }
}
function validNotes(notes){return Array.isArray(notes)&&notes.length>=1&&notes.length<=12&&notes.every(note=>typeof note==='string');}
function notesForCount(notes){return Array.from({length:panelClassCount},(_,index)=>notes[index]||DEFAULT_NOTES[index]);}
function activeProfile(){return settings.mappingProfiles.find(profile=>profile.id===settings.activeMappingProfileId)||settings.mappingProfiles[0];}
function syncActiveProfile(){const profile=activeProfile();if(profile)profile.notes=[...settings.notes];}
function saveSettings() { syncActiveProfile();localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); }
function newProfileId(){return `mapping-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`;}
function noteOptions() {
  const notes=[];
  for(let octave=2;octave<=6;octave++) for(const name of NOTE_NAMES) notes.push(`${name}${octave}`);
  return notes;
}
class AudioEngine {
  constructor() {
    const AudioContext=window.AudioContext||window.webkitAudioContext;
    if(!AudioContext) throw new Error('このブラウザはWeb Audioに対応していません。');
    this.context=new AudioContext({latencyHint:'interactive'});
    this.master=this.context.createGain();
    this.compressor=this.context.createDynamicsCompressor();
    this.compressor.threshold.value=-14; this.compressor.knee.value=18; this.compressor.ratio.value=5;
    this.master.connect(this.compressor).connect(this.context.destination);
    this.buffers=new Map();
    this.loads=new Map();
    this.update();
  }
  async resume(){if(this.context.state!=='running') await this.context.resume();}
  update(){const t=this.context.currentTime;this.master.gain.setTargetAtTime(settings.masterVolume,t,.015);}
  url(note,area){const query=new URLSearchParams({note,area:String(area),instrument:settings.instrument,transpose:String(settings.transpose),velocity:'1',volume:'1',brightness:String(settings.brightness),attack:String(settings.attack),decay:String(settings.decay),sustain:String(settings.sustain),release:String(settings.release),echo_mix:String(settings.echoMix),echo_delay:String(settings.echoDelay),echo_feedback:String(settings.echoFeedback)});return `/api/audio/note.wav?${query}`;}
  async load(note,area){const url=this.url(note,area);if(this.buffers.has(url))return this.buffers.get(url);if(!this.loads.has(url))this.loads.set(url,fetch(url,{cache:'force-cache'}).then(response=>{if(!response.ok)throw new Error(`${response.status} ${response.statusText}`);return response.arrayBuffer();}).then(bytes=>this.context.decodeAudioData(bytes)).then(buffer=>{this.buffers.set(url,buffer);this.loads.delete(url);return buffer;}).catch(error=>{this.loads.delete(url);throw error;}));return this.loads.get(url);}
  async prime(notes){await Promise.all(notes.map((note,area)=>this.load(note,area)));}
  start(buffer,velocity){this.update();const source=this.context.createBufferSource(),gain=this.context.createGain();source.buffer=buffer;gain.gain.value=Math.min(.95,Math.max(.08,velocity));source.connect(gain).connect(this.master);source.start();return source;}
  play(note,velocity,area){const url=this.url(note,area),buffer=this.buffers.get(url);if(buffer)return this.start(buffer,velocity);this.load(note,area).then(value=>this.start(value,velocity)).catch(error=>$('error').textContent=`UNO Q音声: ${error.message}`);}
}

async function ensureAudio(){if(!audio)audio=new AudioEngine();await audio.resume();audio.update();await audio.prime(settings.notes.slice(0,panelClassCount));}
function scheduleAudioPrime(){if(!audio)return;if(audioPrimeTimer)clearTimeout(audioPrimeTimer);audioPrimeTimer=setTimeout(()=>audio.prime(settings.notes.slice(0,panelClassCount)).catch(error=>$('error').textContent=`UNO Q音声: ${error.message}`),180);}
function outputValue(id,value){const el=$(id);if(el)el.value=value;}
function renderSettings(){
  $('instrumentSelect').value=settings.instrument;
  for(const id of ['masterVolume','transpose','brightness','attack','decay','sustain','release','echoMix','echoDelay','echoFeedback','velocity','retriggerGuardMs']) $(id).value=settings[id];
  settings.notes.slice(0,panelClassCount).forEach((note,index)=>{if($(`areaNote${index}`))$(`areaNote${index}`).value=note;});
  renderProfileControls();updateLabels(); updateGridNotes(); if(audio)audio.update();
}
function renderProfileControls(){
  const profile=activeProfile();
  for(const id of ['mappingProfileSelect','mappingProfileEditSelect']){
    const select=$(id);
    select.replaceChildren(...settings.mappingProfiles.map(item=>{const option=document.createElement('option');option.value=item.id;option.textContent=item.name;return option;}));
    select.value=profile.id;
  }
  $('mappingProfileName').value=profile.name;$('mappingProfileDelete').disabled=settings.mappingProfiles.length===1;
  $('mappingSummary').textContent=settings.notes.map((note,index)=>`エリア${index+1}: ${note}`).join(' / ');
}
function updateLabels(){
  outputValue('masterVolumeValue',`${Math.round(settings.masterVolume*100)}%`);outputValue('transposeValue',settings.transpose>0?`+${settings.transpose}`:String(settings.transpose));outputValue('brightnessValue',`${Math.round(settings.brightness*100)}%`);
  outputValue('attackValue',`${Math.round(settings.attack*1000)} ms`);outputValue('decayValue',`${Math.round(settings.decay*1000)} ms`);outputValue('sustainValue',`${Math.round(settings.sustain*100)}%`);outputValue('releaseValue',`${Math.round(settings.release*1000)} ms`);
  outputValue('echoMixValue',`${Math.round(settings.echoMix*100)}%`);outputValue('echoDelayValue',`${Math.round(settings.echoDelay*1000)} ms`);outputValue('echoFeedbackValue',`${Math.round(settings.echoFeedback*100)}%`);outputValue('velocityValue',`${Math.round(settings.velocity*100)}%`);
  outputValue('retriggerGuardMsValue',`${Math.round(settings.retriggerGuardMs)} ms`);
}
function updateGridNotes(){document.querySelectorAll('#hitGrid [data-class]').forEach(cell=>cell.querySelector('span').textContent=settings.notes[Number(cell.dataset.class)]);}
function setupControls(){
  const options=noteOptions().map(note=>`<option value="${note}">${note}</option>`).join('');for(let i=0;i<panelClassCount;i++)$(`areaNote${i}`).innerHTML=options;
  $('instrumentSelect').onchange=e=>{settings.instrument=e.target.value;saveSettings();scheduleAudioPrime();};
  for(const id of ['masterVolume','transpose','brightness','attack','decay','sustain','release','echoMix','echoDelay','echoFeedback','velocity','retriggerGuardMs']) $(id).oninput=e=>{settings[id]=id==='transpose'?Number.parseInt(e.target.value,10):Number(e.target.value);updateLabels();saveSettings();if(audio)audio.update();if(id!=='masterVolume'&&id!=='velocity'&&id!=='retriggerGuardMs')scheduleAudioPrime();};
  $('retriggerGuardMs').onchange=()=>api('/api/inference/retrigger',{milliseconds:Number(settings.retriggerGuardMs)}).catch(error=>$('error').textContent=error.message);
  for(let i=0;i<panelClassCount;i++)$(`areaNote${i}`).onchange=e=>{settings.notes[i]=e.target.value;updateGridNotes();saveSettings();scheduleAudioPrime();};
  const selectProfile=e=>{syncActiveProfile();settings.activeMappingProfileId=e.target.value;settings.notes=[...activeProfile().notes];renderSettings();saveSettings();};
  $('mappingProfileSelect').onchange=selectProfile;
  $('mappingProfileEditSelect').onchange=selectProfile;
  $('mappingProfileName').oninput=e=>{const profile=activeProfile();profile.name=e.target.value.slice(0,40)||'名称未設定';for(const id of ['mappingProfileSelect','mappingProfileEditSelect'])$(id).selectedOptions[0].textContent=profile.name;saveSettings();};
  $('mappingProfileAdd').onclick=()=>{syncActiveProfile();const profile={id:newProfileId(),name:`プロファイル ${settings.mappingProfiles.length+1}`,notes:[...settings.notes]};settings.mappingProfiles.push(profile);settings.activeMappingProfileId=profile.id;settings.notes=[...profile.notes];renderSettings();saveSettings();};
  $('mappingProfileDelete').onclick=()=>{if(settings.mappingProfiles.length<=1)return;const index=settings.mappingProfiles.findIndex(profile=>profile.id===settings.activeMappingProfileId);settings.mappingProfiles.splice(index,1);const next=settings.mappingProfiles[Math.min(index,settings.mappingProfiles.length-1)];settings.activeMappingProfileId=next.id;settings.notes=[...next.notes];renderSettings();saveSettings();};
  document.querySelectorAll('#hitGrid [data-class]').forEach(cell=>cell.onclick=async()=>{await ensureAudio();playArea(Number(cell.dataset.class),.8,true);});
  $('ascendingPreset').onclick=()=>{settings.notes=[...DEFAULT_NOTES];renderSettings();saveSettings();};
  $('resetSettings').onclick=()=>{const profiles=settings.mappingProfiles,activeMappingProfileId=settings.activeMappingProfileId;settings={...DEFAULTS,notes:[...DEFAULT_NOTES],mappingProfiles:profiles,activeMappingProfileId};renderSettings();saveSettings();};
  $('soundSettingsOpen').onclick=()=>$('soundSettingsDialog').showModal();
  $('mappingSettingsOpen').onclick=()=>$('mappingSettingsDialog').showModal();
  renderSettings();
}

function configurePanel(panel){
  const count=Number(panel.class_count)||8;
  if(count===panelClassCount&&$('hitGrid').children.length===count){window.panelProfileUi?.applyPanel(panel);return;}
  panelClassCount=count;
  settings.mappingProfiles.forEach(profile=>profile.notes=notesForCount(profile.notes));
  settings.notes=notesForCount(settings.notes);
  $('hitGrid').innerHTML=Array.from({length:count},(_,i)=>`<button type="button" data-class="${i}"><b>エリア${i+1}</b><span>${settings.notes[i]}</span></button>`).join('');
  const mapping=document.querySelector('.mapping-grid');
  mapping.innerHTML=Array.from({length:count},(_,i)=>`<label>エリア${i+1}<select id="areaNote${i}"></select></label>`).join('');
  const options=noteOptions().map(note=>`<option value="${note}">${note}</option>`).join('');
  for(let i=0;i<count;i++){$(`areaNote${i}`).innerHTML=options;$(`areaNote${i}`).value=settings.notes[i];$(`areaNote${i}`).onchange=e=>{settings.notes[i]=e.target.value;updateGridNotes();saveSettings();scheduleAudioPrime();};}
  document.querySelectorAll('#hitGrid [data-class]').forEach(cell=>cell.onclick=async()=>{await ensureAudio();playArea(Number(cell.dataset.class),.8,true);});
  window.panelProfileUi?.applyPanel(panel);renderScores();saveSettings();
}

function releaseCamera(){
  cameraStream=null;$('usbCamera').removeAttribute('src');$('cameraPlaceholder').hidden=false;
  $('cameraStart').disabled=false;$('cameraStop').disabled=true;$('cameraState').classList.remove('is-running');
}
function stopCamera(){releaseCamera();$('cameraState').textContent='停止中';}
async function startCamera(){
  releaseCamera();$('cameraState').textContent='接続中…';
  try{
    const url=new URL($('cameraDevice').value.trim()||DEFAULT_CAMERA_STREAM);
    if(!['http:','https:'].includes(url.protocol))throw new Error('HTTPまたはHTTPSの配信URLを指定してください。');
    $('cameraDevice').value=url.href;localStorage.setItem(CAMERA_STORAGE_KEY,url.href);
    const frame=$('usbCamera');cameraStream=url.href;
    await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('UNO Qカメラ配信が応答しません。USBホスト接続を確認してください。')),10000);frame.onload=()=>{clearTimeout(timer);resolve();};frame.onerror=()=>{clearTimeout(timer);reject(new Error('UNO Qカメラ配信を読み込めません。'));};frame.src=url.href;});
    $('cameraPlaceholder').hidden=true;$('cameraStart').disabled=true;$('cameraStop').disabled=false;
    $('cameraState').textContent='映像表示中';$('cameraState').classList.add('is-running');
  }catch(error){releaseCamera();$('cameraState').textContent='開始できません';$('cameraPlaceholder').textContent=`カメラを開始できません: ${error&&error.message?error.message:String(error)}`;throw error;}
}
async function setupCamera(){
  $('cameraDevice').value=localStorage.getItem(CAMERA_STORAGE_KEY)||DEFAULT_CAMERA_STREAM;$('cameraState').textContent='開始待ち';
  $('cameraStart').onclick=()=>startCamera().catch(()=>{});
  $('cameraStop').onclick=stopCamera;
  $('cameraDevice').onchange=event=>localStorage.setItem(CAMERA_STORAGE_KEY,event.target.value.trim());
  await startCamera().catch(()=>{});
}
function renderScores(outputs=[]){$('scoreBars').innerHTML=Array.from({length:panelClassCount},(_,i)=>{const raw=Number(outputs[i]||0),height=Math.max(3,Math.min(100,raw*100));return `<div class="score-bar"><i style="height:${height}%"></i><span>${i+1}</span></div>`;}).join('');}
function displayArea(area){
  const note=settings.notes[area]||DEFAULT_NOTES[area],bits=area.toString(2).padStart(3,'0');
  $('lastNote').textContent=`A${area+1} ${note} · ${bits}`;
  document.querySelectorAll('#hitGrid [data-class]').forEach(cell=>cell.classList.toggle('active',Number(cell.dataset.class)===area));
  if(hitClearTimer)clearTimeout(hitClearTimer);
  hitClearTimer=setTimeout(()=>{const cell=document.querySelector(`#hitGrid [data-class="${area}"]`);if(cell)cell.classList.remove('active');},260);
}
function playArea(area,confidence=.8,isPreview=false){
  const note=settings.notes[area]||DEFAULT_NOTES[area],velocity=(1-settings.velocity)*.72+settings.velocity*Math.max(.15,Math.min(1,confidence));
  audio.play(note,velocity,area);displayArea(area);
  $('instrumentStatus').textContent=`${isPreview?'試聴':'演奏'}: エリア${area+1} / ${note} / ${$('instrumentSelect').selectedOptions[0].textContent}`;
}
async function ports(){const data=await api('/api/ports');$('port').innerHTML=data.ports.map(port=>`<option>${port}</option>`).join('');if(data.ports.includes('COM3'))$('port').value='COM3';}
function setButtonState(id,disabled,running=false){const button=$(id);button.disabled=disabled;button.classList.toggle('is-running',running);button.setAttribute('aria-pressed',running?'true':'false');}
function updateActionState(data){const connected=Boolean(data.connected),deviceRunning=Boolean(data.inference_active),playing=deviceRunning&&performanceEnabled;setButtonState('connect',connected,connected);setButtonState('disconnect',!connected);setButtonState('instrumentStart',!connected||playing,playing);setButtonState('instrumentStop',!connected||!deviceRunning);$('port').disabled=connected;}
async function refreshStatus(){
  if(pollBusy)return;pollBusy=true;
  try{const data=await api('/api/status');if(!data.inference_active)performanceEnabled=false;const audible=Boolean(data.inference_active&&performanceEnabled);$('connection').textContent=data.connected?`接続中 ${data.port}`:'未接続';$('connection').classList.toggle('online',data.connected);$('firmwareMode').textContent=data.device_mode==='instrument'?(audible?'高速演奏中':(data.inference_active?'演奏再開待ち':'楽器高速モード')):(data.device_mode==='inference'?'通常推論モード':(data.device_mode==='collection'?'データ採取モード':'モード不明'));$('firmwareMode').classList.toggle('online',audible);
    // latest_ai remains part of /api/status for the inference and collector pages.
    if(data.latest_ai&&!performanceEnabled&&data.latest_ai.sequence!==lastPlayedSequence){lastPlayedSequence=data.latest_ai.sequence;renderScores(data.latest_ai.outputs);displayArea(Number(data.latest_ai.predicted_class));}
    updateActionState(data);if(data.last_error)$('error').textContent=data.last_error;
  }catch(error){$('error').textContent=error.message;}finally{pollBusy=false;}
}
async function inferenceLoop(){
  if(inferenceLoopRunning)return;inferenceLoopRunning=true;
  while(inferenceLoopRunning){
    if(!performanceEnabled){await new Promise(resolve=>setTimeout(resolve,50));continue;}
    try{const after=lastPlayedSequence===null?'':String(lastPlayedSequence),result=await api(`/api/ai/wait?after=${encodeURIComponent(after)}&timeout=1.0`);if(result.sequence!==undefined&&result.sequence!==lastPlayedSequence){lastPlayedSequence=result.sequence;const area=Number(result.predicted_class),score=Math.max(...result.outputs.map(Number));renderScores(result.outputs);playArea(area,score,false);$('error').textContent='';}}
    catch(error){$('error').textContent=error.message;await new Promise(resolve=>setTimeout(resolve,50));}
  }
}
async function startPerformance(){try{await ensureAudio();const current=await api('/api/status');lastPlayedSequence=current.latest_ai?current.latest_ai.sequence:null;await api('/api/inference/retrigger',{milliseconds:Number(settings.retriggerGuardMs)});await api('/api/inference/start',{mode:'instrument'});performanceEnabled=true;$('instrumentStatus').textContent='高速演奏中です。アクリル板を連続してたたけます。';$('instrumentStatus').classList.add('playing');$('error').textContent='';await refreshStatus();}catch(error){$('error').textContent=error.message;}}
async function stopPerformance(){try{performanceEnabled=false;await api('/api/inference/stop',{});$('instrumentStatus').textContent='演奏を停止しました。';$('instrumentStatus').classList.remove('playing');await refreshStatus();}catch(error){$('error').textContent=error.message;}}
async function synchronizeStartupState(){try{const current=await api('/api/status');if(current.connected&&current.device_mode==='instrument'&&current.inference_active)await api('/api/inference/stop',{});await refreshStatus();}catch(error){$('error').textContent=error.message;}}

$('refresh').onclick=ports;$('connect').onclick=async()=>{try{await api('/api/connect',{port:$('port').value});await api('/api/device/mode',{mode:'instrument'});$('error').textContent='';await refreshStatus();}catch(error){$('error').textContent=error.message;}};$('disconnect').onclick=async()=>{try{performanceEnabled=false;await api('/api/disconnect',{});$('instrumentStatus').classList.remove('playing');$('error').textContent='';await refreshStatus();}catch(error){$('error').textContent=error.message;}};$('instrumentStart').onclick=startPerformance;$('instrumentStop').onclick=stopPerformance;
document.querySelectorAll('.app-tabs a').forEach(link=>link.addEventListener('click',async event=>{event.preventDefault();try{const current=await api('/api/status');if(!current.connected){window.location.href=link.href;return;}const href=link.getAttribute('href'),mode=href==='/collector.html'?'collection':(href==='/instrument.html'?'instrument':'inference');if(current.collection&&current.collection.active)throw new Error('データ採取中はタブを切り替えられません。先に採取を停止してください。');if(current.inference_active&&current.device_mode!==mode)await api('/api/inference/stop',{});if(current.device_mode!==mode)await api('/api/device/mode',{mode});window.location.href=link.href;}catch(error){$('error').textContent=error.message;}}));
setupControls();setupCamera();renderScores();ports().catch(error=>$('error').textContent=error.message);synchronizeStartupState();setInterval(refreshStatus,500);inferenceLoop();
