const $ = id => document.getElementById(id);
const SETTINGS_KEY = 'acrylicPanInstrumentV1';
const CAMERA_KEY = 'acrylicPanUnoQCameraStreamUrl';
const PC_CAMERA_KEY = 'acrylicPanPcCameraDeviceId';
const CAMERA_SOURCE_KEY = 'acrylicPanProbabilityCameraSource';
const DEFAULT_CAMERA_STREAM = `${window.location.protocol}//${window.location.hostname}:4912/embed`;
const CAMERA_CALIBRATION_KEY = 'acrylicPanCameraPanelCornersV1';
const CAMERA_ROW_DIVIDERS_KEY = 'acrylicPanCameraRowDividerRatiosV1';
const DISPLAY_MODE_KEY = 'acrylicPanProbabilityDisplayMode';
const HEATMAP_VISIBLE_KEY = 'acrylicPanProbabilityHeatmapVisible';
const PANEL_AREA_VISIBLE_KEY = 'acrylicPanProbabilityPanelAreaVisible';
const LANGUAGE_KEY = 'acrylicPanProbabilityLanguageV1';
const FREE_PLAY_NOTES = ['C4','C#4','D4','D#4','E4','F4','F#4','G4','G#4','A4','A#4','B4'];
const DEFAULT_NOTES = [...FREE_PLAY_NOTES];
const SONG_KEY = 'acrylicPanAssistSongV1';
const NOTE_LENGTH_KEY = 'acrylicPanNoteLengthV1';
const repeatValues=(values,times=2)=>Array.from({length:times},()=>values).flat();
const FUR_ELISE_8=['E5','D#5','E5','D#5','E5','B4','D5','C5','A4','C4','E4','A4','B4','E4','G#4','B4','C5','E4','E5','D#5','E5','D#5','E5','B4','D5','C5','A4','C4','E4','A4','B4','E4','C5','B4','A4'];
const ODE_TO_JOY_8=['E4','E4','F4','G4','G4','F4','E4','D4','C4','C4','D4','E4','E4','D4','D4','E4','E4','F4','G4','G4','F4','E4','D4','C4','C4','D4','E4','D4','C4','C4'];
const FRERE_JACQUES_8=['C4','D4','E4','C4','C4','D4','E4','C4','E4','F4','G4','E4','F4','G4','G4','A4','G4','F4','E4','C4','G4','A4','G4','F4','E4','C4','C4','G3','C4','C4','G3','C4'];
const KOROBEINIKI_8=['E5','B4','C5','D5','C5','B4','A4','A4','C5','E5','D5','C5','B4','C5','D5','E5','C5','A4','A4','D5','F5','A5','G5','F5','E5','C5','E5','D5','C5','B4','B4','C5','D5','E5','C5','A4','A4'];
const SONGS = {
  fur_elise:{name:'エリーゼのために',nameEn:'Für Elise',notes:repeatValues(FUR_ELISE_8)},
  ode_to_joy:{name:'歓喜の歌',nameEn:'Ode to Joy',notes:repeatValues(ODE_TO_JOY_8)},
  minuet_g:{name:'ペツォールト「メヌエット ト長調」',nameEn:'Petzold Minuet in G Major',notes:[
    'D5','G4','A4','B4','C5','D5','G4','G4','E5','C5','D5','E5','F#5','G5','G4','G4',
    'C5','D5','C5','B4','A4','B4','C5','B4','A4','G4','F#4','G4','A4','B4','G4','A4',
    'D5','G4','A4','B4','C5','D5','G4','G4','E5','C5','D5','E5','F#5','G5','G4','G4',
    'C5','D5','C5','B4','A4','B4','C5','B4','A4','G4','A4','B4','A4','G4','F#4','G4']},
  brahms_lullaby:{name:'ブラームスの子守歌',nameEn:'Brahms Lullaby',notes:[
    'B4','B4','D5','B4','B4','D5','B4','D5','G5','F#5','E5','E5','D5','A4','B4','C5','A4','A4','B4','C5',
    'A4','C5','F#5','E5','D5','F#5','G5','G4','G4','G5','E5','C5','D5','B4','G4','C5','D5','E5',
    'B4','D5','G4','G4','G5','E5','C5','D5','B4','G4','C5','D5','C5','B4','A4','G4']},
  amazing_grace:{name:'アメイジング・グレイス',nameEn:'Amazing Grace',notes:[
    'D4','G4','B4','A4','G4','B4','A4','G4','E4','D4','D4','G4','B4','A4','G4','B4','A4','B4','D5','B4','D5',
    'D5','B4','A4','G4','B4','A4','G4','E4','D4','D4','G4','B4','A4','G4','B4','A4','B4','D5']},
  auld_lang_syne:{name:'オールド・ラング・サイン',nameEn:'Auld Lang Syne',notes:[
    'C4','F4','E4','F4','A4','G4','F4','G4','A4','G4','F4','F4','A4','C5','D5','D5','C5','A4','A4','F4',
    'G4','F4','G4','A4','G4','F4','D4','D4','C4','F4','D5','C5','A4','A4','F4','G4','F4','G4','D5',
    'C5','A4','A4','C5','D5','D5','C5','A4','A4','F4','G4','F4','G4','A4','G4','F4','D4','D4','C4','F4']},
  frere_jacques:{name:'フレール・ジャック',nameEn:'Frère Jacques',notes:repeatValues(FRERE_JACQUES_8)},
  korobeiniki:{name:'コロベイニキ',nameEn:'Korobeiniki',notes:repeatValues(KOROBEINIKI_8)}
};
const RHYTHM_BEATS={s:.25,u:1/3,e:.5,t:.75,q:1,d:1.5,h:2,x:2.5,m:3,w:4,f:5};
const SONG_GUIDE={
  // Source: Mutopia Project, Bagatelle No. 25 (WoO 59), written 8-bar repeat.
  fur_elise:{bpm:72,bars:16,expectedBeats:25,rhythm:'sssssssstssstssstssssssssstssstsssd'.repeat(2)},
  ode_to_joy:{bpm:108,bars:16,expectedBeats:64,rhythm:'qqqqqqqqqqqqdehqqqqqqqqqqqqdeh'.repeat(2)},
  // Source: Mutopia Project BWV Anh. 114, treble voice, first 16 bars.
  minuet_g:{bpm:100,bars:16,expectedBeats:48,rhythm:'qeeee qqq qeeee qqq qeeee qeeee qeeee m qeeee qqq qeeee qqq qeeee qeeee qeeee m'},
  // Source: Mutopia Project Brahms Op. 49 No. 4 arrangement, melody, 16 bars plus pickup.
  brahms_lullaby:{bpm:80,bars:16,expectedBeats:48,rhythm:'ee deq hee qde qqee qqee hee eeqq hee hee hee qqq edee hee hee essqq h'},
  // Source: ABC collection, Amazing Grace in G, 16-bar melody. Ties are one sustained onset.
  amazing_grace:{bpm:72,bars:16,expectedBeats:48,rhythm:'qhuuu hq hq hq huuu hee fee huuu hq hq hq huuu hee f'},
  // Source: John Chambers ABC collection, verse and chorus (16 bars).
  auld_lang_syne:{bpm:84,bars:16,expectedBeats:64,rhythm:'q deqq deqee deqq mq deqq deqee deqq mq deqq deqq deqq mq deqq deqee deqq m'},
  // Source: ABC Frère Jacques in F, transposed to C; its written 8 bars repeat once.
  frere_jacques:{bpm:110,bars:16,expectedBeats:64,rhythm:'qqqqqqqqqqhqqheeeeqqeeeeqqqqhqqh'.repeat(2)},
  // Source: mfiles Korobeiniki score and Whitmore High KS3 score; familiar 8-bar A melody repeats once.
  korobeiniki:{bpm:128,bars:16,expectedBeats:64,rhythm:'qeeqeeqeeqeedeqqqqhqeeqeeqeeqdeeqqqqx'.repeat(2)}
};
let activePanel = {id:'400x300x5',width_mm:400,height_mm:300,columns:4,rows:3,class_count:12,clamp:{x_min:200,x_max:300,y_min:0,y_max:20}};
let settings = loadSettings();
let audioContext = null;
let masterGain = null;
let mediaPrimed = false;
const unoQAudioBuffers = new Map();
const unoQAudioLoads = new Map();
let unoQPrimeTimer = null;
let performanceEnabled = false;
let lastSequence = null;
let loopRunning = true;
let cameraStream = null;
let cameraSource = localStorage.getItem(CAMERA_SOURCE_KEY)==='unoq'?'unoq':'pc';
const MIN_HEATMAP_DISPLAY_MS = 450;
let lastHeatmapRenderedAt = -Infinity;
let pendingHeatmapPosition = null;
let heatmapTimer = null;
let lastRenderedPosition = null;
let calibrationPoints = loadCalibration();
let rowDividerRatios = loadRowDividerRatios();
let calibrating = false;
let dividerCalibrationStep = 0;
let draggingCalibrationPoint = -1;
let heatmapVisible = localStorage.getItem(HEATMAP_VISIBLE_KEY)!=='false';
let panelAreaVisible = localStorage.getItem(PANEL_AREA_VISIBLE_KEY)!=='false';
let activeSongId = '';
let songStep = 0;
let songPanelNotes = Array(12).fill(null);
let guidePlaying = false;
let guideTimer = null;
let guideToken = 0;
const guideOscillators = new Set();
let noteLengthScale = Math.max(.25,Math.min(2.5,Number(localStorage.getItem(NOTE_LENGTH_KEY))||1));
let language = localStorage.getItem(LANGUAGE_KEY)==='en'?'en':'ja';
let latestStatus = null;
let performanceMessage = {kind:'ready'};
let cameraStateKey = 'preparing';
let calibrationStatusText = null;
let cameraPlaceholderText = ['カメラ入力を選択して「カメラ開始」を押してください','Select a camera input and press Start camera.'];
const L=(ja,en)=>language==='en'?en:ja;

function loadSettings(){
  try{
    const saved=JSON.parse(localStorage.getItem(SETTINGS_KEY)||'{}');
    const profiles=Array.isArray(saved.mappingProfiles)?saved.mappingProfiles:[];
    const active=profiles.find(profile=>profile.id===saved.activeMappingProfileId)||profiles[0];
    const notes=Array.isArray(active?.notes)?active.notes:(Array.isArray(saved.notes)?saved.notes:DEFAULT_NOTES);
    const storedVolume=Number(saved.masterVolume);
    return {instrument:saved.instrument||'steel_drum',masterVolume:Number.isFinite(storedVolume)&&storedVolume>0?Math.min(1,storedVolume):.7,notes:Array.from({length:12},(_,i)=>notes[i]||DEFAULT_NOTES[i])};
  }catch(_){return {instrument:'steel_drum',masterVolume:.7,notes:[...DEFAULT_NOTES]};}
}
function saveInstrument(){
  try{const saved=JSON.parse(localStorage.getItem(SETTINGS_KEY)||'{}');saved.instrument=settings.instrument;saved.masterVolume=settings.masterVolume;localStorage.setItem(SETTINGS_KEY,JSON.stringify(saved));}catch(_){}
}
function setLabelText(id,value){const label=$(id),node=label?.firstChild;if(node)node.nodeValue=value+' ';}
function setOptionText(selectId,value,text){const option=Array.from($(selectId).options).find(item=>item.value===value);if(option)option.textContent=text;}
function songName(song){return language==='en'?(song.nameEn||song.name):song.name;}
function populateSongOptions(){const selected=activeSongId||$('songSelect').value;$('songSelect').replaceChildren(new Option(L('自由演奏','Free play'),''),...Object.entries(SONGS).map(([id,song])=>new Option(songName(song)+(id==='korobeiniki'?L('（16小節・テトリスで知られる曲）',' (16 bars; known from Tetris)'):L('（16小節）',' (16 bars)')),id)));$('songSelect').value=SONGS[selected]?selected:'';}
function renderPerformanceStatus(){const message=performanceMessage;if(message.kind==='note')$('performanceStatus').textContent=L('演奏: エリア'+(message.area+1)+' / '+message.note+' / エリア確率 '+message.percent+'%','Playing: Area '+(message.area+1)+' / '+message.note+' / Area probability '+message.percent+'%');else if(message.kind==='running')$('performanceStatus').textContent=L('確率分布演奏中です。最尤エリアを発音します。','Probability performance is active. The most likely area will sound.');else if(message.kind==='stopped')$('performanceStatus').textContent=L('演奏を停止しました。','Performance stopped.');else $('performanceStatus').textContent=L('「演奏開始」を押すと音声と確率推論が有効になります。','Press Start performance to enable audio and probability inference.');}
function setCameraState(key){cameraStateKey=key;const labels={preparing:['準備中','Preparing'],waiting:['開始待ち','Ready'],connecting:['接続中…','Connecting…'],running:['映像表示中','Video active'],stopped:['停止中','Stopped'],missing:['未検出','Not detected'],failed:['開始できません','Could not start']};$('cameraState').textContent=L(...(labels[key]||labels.preparing));}
function setCameraPlaceholder(ja,en){cameraPlaceholderText=[ja,en];$('cameraPlaceholder').textContent=L(ja,en);}
function localizePanelProfile(){Array.from($('panelProfile').options).forEach(option=>{option.textContent=language==='en'?option.textContent.replace(/（(\d+)クラス）/,'($1 classes)'):option.textContent.replace(/\((\d+) classes\)/,'（$1クラス）');});$('positionPanel').setAttribute('aria-label',language==='en'?(activePanel.width_mm+' × '+activePanel.height_mm+' × '+(activePanel.thickness_mm||5)+' mm acrylic panel'):(activePanel.width_mm+' × '+activePanel.height_mm+' × '+(activePanel.thickness_mm||5)+' mm アクリル板'));}
function applyLanguage(){
  document.documentElement.lang=language;document.title=L('Acrylic Pan 確率分布演奏','Acrylic Pan Probability Instrument');$('languageToggle').textContent=L('English','日本語');
  $('introText').textContent=L('60座標確率をカメラ映像上の四角形へ透過重畳し、UNO Qで合成した最尤エリアの音声を配信します。','Overlays the 60-point probability heatmap on the camera quadrilateral and streams UNO Q-synthesized audio.');
  const tabs=[['/collector.html','学習データ採取','Data Collection'],['/','推論結果','Inference'],['/position.html','位置推定','Position'],['/instrument.html','クラス演奏','Class Instrument'],['/instrument-probability.html','確率演奏','Probability Instrument']];document.querySelector('.app-tabs').setAttribute('aria-label',L('動作モード','Operating mode'));tabs.forEach(([href,ja,en])=>{const link=document.querySelector('.app-tabs a[href="'+href+'"]');if(link)link.textContent=L(ja,en);});
  [['displayLabel','表示','Display'],['instrumentLabel','音色','Instrument'],['masterVolumeLabel','音量','Volume'],['cameraSourceLabel','カメラ入力','Camera input'],['cameraLabel','PCカメラ','PC camera'],['cameraUrlLabel','UNO Q配信URL','UNO Q stream URL'],['songLabel','演奏補助','Performance guide'],['noteLengthLabel','音の長さ','Note length']].forEach(args=>setLabelText(args[0],L(args[1],args[2])));
  [['refresh','更新','Refresh'],['connect','接続','Connect'],['disconnect','切断','Disconnect'],['performanceStart','演奏開始','Start performance'],['performanceStop','演奏停止','Stop performance'],['probabilityDemo','表示デモ','Display demo'],['cameraStart','カメラ開始','Start camera'],['cameraStop','停止','Stop'],['calibrationStart','8点フィット','8-point fit'],['calibrationClear','フィット消去','Clear fit'],['songReset','最初から','Restart']].forEach(([id,ja,en])=>$(id).textContent=L(ja,en));
  $('fixedRuntime').textContent=L('400 × 300 mm・内部SPI・UNO Q Linux AI','400 × 300 mm · Internal SPI · UNO Q Linux AI');setOptionText('displayMode','panel',L('パネル表示','Panel'));setOptionText('displayMode','camera',L('カメラ重畳','Camera overlay'));
  [['steel_drum','スチールドラム','Steel drum'],['piano','ピアノ','Piano'],['harpsichord','チェンバロ','Harpsichord'],['guitar','ギター','Guitar'],['drums','ドラム','Drums']].forEach(([value,ja,en])=>setOptionText('instrumentSelect',value,L(ja,en)));
  $('heatmapTitle').textContent=L('座標確率ヒートマップ','Position Probability Heatmap');$('areaProbabilityTitle').textContent=L('12エリア確率','12-Area Probability');$('cameraSettingsTitle').textContent=L('カメラ設定','Camera settings');$('positionPanel').setAttribute('aria-label',L('400 × 300 mm アクリル板上の条件付き座標確率分布','Conditional position probability on a 400 × 300 mm acrylic panel'));document.querySelector('.sensor-marker').setAttribute('aria-label',L('加速度センサ位置','Accelerometer position'));document.querySelector('.clamp-marker').setAttribute('aria-label',L('固定領域','Clamped area'));document.querySelector('.clamp-marker span').textContent=L('固定','clamp');$('pcCamera').setAttribute('aria-label',L('PC USBカメラ映像','PC USB camera video'));$('usbCamera').setAttribute('aria-label',L('UNO Q USBカメラ映像','UNO Q USB camera stream'));$('cameraHeatmapOverlay').setAttribute('aria-label',L('カメラ映像上の8点透視位置合わせ','Eight-point perspective alignment over the camera video'));$('noteLength').setAttribute('aria-label',L('音の長さ','Note length'));
  setOptionText('cameraSource','pc',L('このPCのカメラ','This PC camera'));setOptionText('cameraSource','unoq',L('UNO QのUSBカメラ','UNO Q USB camera'));
  populateSongOptions();localizePanelProfile();updateSongAssist();updateGuideButton();updateHeatmapToggle();updatePanelAreaToggle();renderPerformanceStatus();updateCameraSourceUi();setCameraState(cameraStateKey);$('cameraPlaceholder').textContent=L(...cameraPlaceholderText);if(calibrationStatusText)showCalibrationStatus(...calibrationStatusText);if(latestStatus)updateControls(latestStatus);if(lastRenderedPosition)renderPosition(lastRenderedPosition,false);localStorage.setItem(LANGUAGE_KEY,language);
}
function calibrationStorageKey(){return CAMERA_CALIBRATION_KEY+':'+cameraSource;}
function rowDividerStorageKey(){return CAMERA_ROW_DIVIDERS_KEY+':'+cameraSource;}
function loadCalibration(){try{const saved=localStorage.getItem(calibrationStorageKey())||(cameraSource==='unoq'?localStorage.getItem(CAMERA_CALIBRATION_KEY):null)||'[]',points=JSON.parse(saved);return Array.isArray(points)&&points.length===4&&points.every(point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite))?points:[[0,0],[1,0],[1,1],[0,1]];}catch(_){return [[0,0],[1,0],[1,1],[0,1]];}}
function loadRowDividerRatios(){try{const ratios=JSON.parse(localStorage.getItem(rowDividerStorageKey())||'[]');return Array.isArray(ratios)&&ratios.length===2&&ratios.every(row=>Array.isArray(row)&&row.length===2&&row.every(value=>Number.isFinite(value)&&value>0&&value<1))?ratios:[[1/3,1/3],[2/3,2/3]];}catch(_){return [[1/3,1/3],[2/3,2/3]];}}
function saveCalibration(){if(calibrationPoints.length===4){localStorage.setItem(calibrationStorageKey(),JSON.stringify(calibrationPoints));localStorage.setItem(rowDividerStorageKey(),JSON.stringify(rowDividerRatios));}else{localStorage.removeItem(calibrationStorageKey());localStorage.removeItem(rowDividerStorageKey());}}
async function api(path,body){
  const options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
  const response=await fetch(path,options),text=await response.text(),data=text?JSON.parse(text):{};
  if(!response.ok){const error=new Error(data.error||`${response.status} ${response.statusText}`);error.status=response.status;throw error;}
  return data;
}
const modeForSource=()=> 'inference';
const sleep=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));

function noteFrequency(note){
  const match=/^([A-G])(#?)(-?\d+)$/.exec(note)||['','C','',4];
  const names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
  const midi=(Number(match[3])+1)*12+names.indexOf(match[1]+match[2]);
  return 440*Math.pow(2,(midi-69)/12);
}
function activeSong(){return SONGS[activeSongId]||null;}
function currentSongArea(offset=0){const song=activeSong(),index=songStep+offset;if(!song||index>=song.notes.length)return -1;return songPanelNotes.indexOf(song.notes[index]);}
function panelNote(area){return activeSong()?songPanelNotes[area]:FREE_PLAY_NOTES[area];}
function panelNoteLabel(area){const note=panelNote(area)||'—';return activeSong()?note:note.replace(/-?\d+$/,'');}
function updateAreaLabels(){Array.from($('areaSelectionGrid').children).forEach((cell,index)=>{let label=cell.querySelector('.area-note-label');if(!label){label=document.createElement('span');label.className='area-note-label';cell.appendChild(label);}label.textContent=panelNoteLabel(index);});}
function configureSong(songId,reset=true){if(guidePlaying)stopGuide(false);activeSongId=SONGS[songId]?songId:'';if(reset)songStep=0;songPanelNotes=Array(12).fill(null);const song=activeSong();if(song){const unique=[...new Set(song.notes)].sort((a,b)=>noteFrequency(a)-noteFrequency(b));unique.slice(0,12).forEach((note,index)=>songPanelNotes[index]=note);}localStorage.setItem(SONG_KEY,activeSongId);updateAreaLabels();updateSongAssist();}
function updateSongAssist(){const song=activeSong(),nextArea=currentSongArea(),secondArea=currentSongArea(1);if(!song)$('songProgress').textContent=L('自由演奏：C～B 半音階','Free play: C–B chromatic');else if(songStep>=song.notes.length)$('songProgress').textContent=songName(song)+L('：完奏',': Complete');else $('songProgress').textContent=L('次 ','Next ')+song.notes[songStep]+L('・エリア',' · Area ')+(nextArea+1)+' ('+(songStep+1)+'/'+song.notes.length+')';Array.from($('areaSelectionGrid').children).forEach((cell,index)=>{cell.classList.toggle('next-note',index===nextArea);cell.classList.toggle('second-next-note',index===secondArea&&index!==nextArea);});document.querySelectorAll('#areaProbabilities .area-probability').forEach((row,index)=>{row.classList.toggle('next-note',index===nextArea);row.classList.toggle('second-next-note',index===secondArea&&index!==nextArea);});updateGuideButton();redrawCameraOverlay();}
function advanceSong(area){const song=activeSong();if(!song||area!==currentSongArea())return;songStep=Math.min(song.notes.length,songStep+1);updateSongAssist();}
function updateGuideButton(){const button=$('guidePlay');if(!button)return;button.textContent=guidePlaying?L('手本停止','Stop example'):L('手本演奏','Example performance');button.disabled=!activeSong();button.classList.toggle('is-playing',guidePlaying);}
function stopGuide(update=true){guidePlaying=false;guideToken++;if(guideTimer)clearTimeout(guideTimer);guideTimer=null;guideOscillators.forEach(voice=>{try{if(typeof voice.stop==='function')voice.stop();else{voice.pause();voice.currentTime=0;}}catch(_){}});guideOscillators.clear();if(update)updateSongAssist();else updateGuideButton();}
function validateSongGuides(){const invalid=[];Object.entries(SONGS).forEach(([id,song])=>{const score=SONG_GUIDE[id],rhythm=score?.rhythm?.replace(/\s/g,'')||'',beats=[...rhythm].reduce((sum,symbol)=>sum+(RHYTHM_BEATS[symbol]||0),0);if(!score||score.bars!==16||new Set(song.notes).size>12||rhythm.length!==song.notes.length||[...rhythm].some(symbol=>!RHYTHM_BEATS[symbol])||Math.abs(beats-score.expectedBeats)>.001)invalid.push(id);});return invalid;}
function guideTiming(index){const score=SONG_GUIDE[activeSongId]||{bpm:100,rhythm:'q'},rhythm=score.rhythm.replace(/\s/g,'')||'q',beats=RHYTHM_BEATS[rhythm[index]]||1;return {beats,milliseconds:60000/score.bpm*beats};}
async function toggleGuide(){if(guidePlaying){stopGuide();return;}const song=activeSong();if(!song){$('error').textContent=L('曲を選択してください。','Select a song.');return;}try{await ensureAudio();$('error').textContent='';songStep=0;guidePlaying=true;const token=++guideToken;updateSongAssist();const playNext=()=>{if(!guidePlaying||token!==guideToken)return;if(songStep>=song.notes.length){stopGuide();return;}const timing=guideTiming(songStep);playArea(currentSongArea(),1,'guide',timing.beats);guideTimer=setTimeout(playNext,timing.milliseconds);};playNext();}catch(error){stopGuide();$('error').textContent=error.message;}}
async function ensureAudio(){
  if(!audioContext){
    const AudioContext=window.AudioContext||window.webkitAudioContext;
    if(!AudioContext)throw new Error(L('このブラウザはWeb Audioに対応していません。','This browser does not support Web Audio.'));
    audioContext=new AudioContext({latencyHint:'interactive'});masterGain=audioContext.createGain();masterGain.connect(audioContext.destination);
  }
  masterGain.gain.setTargetAtTime(settings.masterVolume,audioContext.currentTime,.01);
  if(audioContext.state!=='running')await audioContext.resume();
  if(audioContext.state!=='running')throw new Error(L('ブラウザの音声出力を開始できません。タブのミュート状態を確認してください。','Browser audio could not start. Check whether the tab is muted.'));
  if(!mediaPrimed){
    const primer=new Audio('data:audio/wav;base64,UklGRsQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YaAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');
    primer.volume=0;await primer.play();mediaPrimed=true;
  }
  await primeUnoQAudio();
}
function unoQAudioUrl(note,area,duration){
  const parameters=new URLSearchParams({note,area:String(area),instrument:settings.instrument,
    velocity:'1',volume:'1',
    release:String(Math.max(.03,duration*.72)),decay:String(Math.max(.03,duration*.22)),
    sustain:'.12',echo_mix:'.12',echo_delay:'.18',echo_feedback:'.20'});
  return `/api/audio/note.wav?${parameters}`;
}
async function loadUnoQAudio(note,area,duration){
  const url=unoQAudioUrl(note,area,duration);
  if(unoQAudioBuffers.has(url))return unoQAudioBuffers.get(url);
  if(!unoQAudioLoads.has(url))unoQAudioLoads.set(url,fetch(url,{cache:'force-cache'}).then(response=>{
    if(!response.ok)throw new Error(`${response.status} ${response.statusText}`);
    return response.arrayBuffer();
  }).then(bytes=>audioContext.decodeAudioData(bytes)).then(buffer=>{unoQAudioBuffers.set(url,buffer);unoQAudioLoads.delete(url);return buffer;}).catch(error=>{unoQAudioLoads.delete(url);throw error;}));
  return unoQAudioLoads.get(url);
}
function liveNoteDuration(){return (settings.instrument==='harpsichord'?.45:(settings.instrument==='drums'?.22:1.15))*noteLengthScale;}
async function primeUnoQAudio(){
  const duration=liveNoteDuration(),jobs=[];
  for(let area=0;area<activePanel.class_count;area++){const note=panelNote(area);if(note)jobs.push(loadUnoQAudio(note,area,duration));}
  await Promise.all(jobs);
}
function scheduleUnoQAudioPrime(){if(!audioContext)return;if(unoQPrimeTimer)clearTimeout(unoQPrimeTimer);unoQPrimeTimer=setTimeout(()=>primeUnoQAudio().catch(error=>$('error').textContent=L('UNO Q音声: ','UNO Q audio: ')+error.message),180);}
async function playUnoQMedia(note,area,probability,duration){
  const buffer=await loadUnoQAudio(note,area,duration),voice=audioContext.createBufferSource(),gain=audioContext.createGain();
  voice.buffer=buffer;gain.gain.value=Math.max(.12,Math.min(.95,.2+probability*.8));voice.connect(gain).connect(masterGain);voice.start();return voice;
}
function playArea(area,probability,source='live',beatLength=1){
  if(source==='live'&&guidePlaying)stopGuide(false);
  if(!mediaPrimed)return;
  const note=panelNote(area);if(!note)return;
  const rhythmicLength=source==='guide'?Math.max(.45,Math.min(2,beatLength)):1;
  const duration=liveNoteDuration()*rhythmicLength;
  playUnoQMedia(note,area,probability,duration).then(voice=>{if(source==='guide'){guideOscillators.add(voice);voice.onended=()=>guideOscillators.delete(voice);}}).catch(reason=>{$('error').textContent=L('音声再生: ','Audio playback: ')+reason.message;});
  $('lastNote').textContent=`A${area+1} ${note} · ${(probability*100).toFixed(1)}%`;
  performanceMessage={kind:'note',area,note,percent:(probability*100).toFixed(1)};renderPerformanceStatus();
  advanceSong(area);
}

async function ports(){const data=await api('/api/ports');$('port').replaceChildren(...data.ports.map(port=>new Option(port,port)));if(data.ports.includes('COM3'))$('port').value='COM3';}
function setButton(id,disabled,active=false){const button=$(id);button.disabled=disabled;button.classList.toggle('primary',active);}
function updateControls(data){
  latestStatus=data;
  const connected=Boolean(data.connected),running=Boolean(data.inference_active),audible=running&&performanceEnabled;
  $('connection').textContent=connected?L('接続中 ','Connected ')+data.port:L('未接続','Disconnected');$('connection').classList.toggle('online',connected);
  $('firmwareMode').textContent=audible?L('UNO Q確率演奏中','UNO Q probability performance'):(data.device_mode==='inference'?L('UNO Q Linux推論','UNO Q Linux inference'):L('モード切替中','Switching mode'));
  $('firmwareMode').classList.toggle('online',audible);$('port').disabled=connected;$('positionSource').disabled=running;
  setButton('connect',connected,connected);setButton('disconnect',!connected);setButton('performanceStart',!connected||audible,audible);setButton('performanceStop',!connected||!running);
}
async function refreshStatus(){
  try{const data=await api('/api/status');if(data.panel){activePanel=data.panel;window.panelProfileUi?.sync(data);localizePanelProfile();applyPanel();}if(!data.inference_active)performanceEnabled=false;updateControls(data);$('error').textContent=data.last_error||'';}
  catch(error){$('error').textContent=error.message;}
}
function applyPanel(){
  const canvas=$('positionHeatmap');canvas.height=Math.round(canvas.width*activePanel.height_mm/activePanel.width_mm);
  const grid=document.querySelector('.panel-grid');grid.style.backgroundImage=`repeating-linear-gradient(90deg,transparent 0,transparent calc(${100/activePanel.columns}% - 1px),#ffffff42 calc(${100/activePanel.columns}% - 1px),#ffffff42 ${100/activePanel.columns}%),repeating-linear-gradient(0deg,transparent 0,transparent calc(${100/activePanel.rows}% - 1px),#ffffff42 calc(${100/activePanel.rows}% - 1px),#ffffff42 ${100/activePanel.rows}%)`;
  const selectionGrid=$('areaSelectionGrid');selectionGrid.style.gridTemplateColumns=`repeat(${activePanel.columns},1fr)`;selectionGrid.style.gridTemplateRows=`repeat(${activePanel.rows},1fr)`;if(selectionGrid.children.length!==activePanel.class_count)selectionGrid.replaceChildren(...Array.from({length:activePanel.class_count},()=>{const cell=document.createElement('div');cell.className='area-selection-cell';return cell;}));updateAreaLabels();
  const clamp=activePanel.clamp,marker=document.querySelector('.clamp-marker');if(clamp){marker.style.left=`${clamp.x_min/activePanel.width_mm*100}%`;marker.style.top=`${clamp.y_min/activePanel.height_mm*100}%`;marker.style.width=`${(clamp.x_max-clamp.x_min)/activePanel.width_mm*100}%`;marker.style.height=`${(clamp.y_max-clamp.y_min)/activePanel.height_mm*100}%`;}
  document.querySelector('.position-axis span:last-child').textContent=`${activePanel.width_mm} mm`;
  redrawCameraOverlay();
}
function heatColor(value){
  const t=Math.max(0,Math.min(1,value)),stops=[[0,3,7,30],[.14,20,30,140],[.30,0,105,255],[.46,0,220,235],[.62,45,210,80],[.76,245,235,30],[.89,255,120,10],[1,220,15,5]];
  for(let i=1;i<stops.length;i++)if(t<=stops[i][0]){const a=stops[i-1],b=stops[i],f=(t-a[0])/(b[0]-a[0]);return [1,2,3].map(c=>Math.round(a[c]+(b[c]-a[c])*f));}return stops.at(-1).slice(1);
}
function drawHeatmap(position){
  const canvas=$('positionHeatmap'),context=canvas.getContext('2d'),map=position.probability_map||{},support=map.support_xy_mm||[],probability=map.probabilities||[];
  canvas.hidden=!heatmapVisible;if(!heatmapVisible){context.clearRect(0,0,canvas.width,canvas.height);return;}
  if(!support.length||support.length!==probability.length){context.clearRect(0,0,canvas.width,canvas.height);return;}
  const width=40,height=Math.round(width*activePanel.height_mm/activePanel.width_mm),raster=document.createElement('canvas');raster.width=width;raster.height=height;
  const rc=raster.getContext('2d'),image=rc.createImageData(width,height),values=new Float32Array(width*height),inverse=1/(2*27*27);let peak=1e-12;
  for(let row=0;row<height;row++)for(let column=0;column<width;column++){const x=(column+.5)*activePanel.width_mm/width,y=(row+.5)*activePanel.height_mm/height;let density=0;for(let i=0;i<support.length;i++){const dx=x-Number(support[i][0]),dy=y-Number(support[i][1]);density+=Math.max(0,Number(probability[i])||0)*Math.exp(-(dx*dx+dy*dy)*inverse);}values[row*width+column]=density;peak=Math.max(peak,density);}
  for(let i=0;i<values.length;i++){const level=Math.round(Math.pow(values[i]/peak,.52)*9)/9,[r,g,b]=heatColor(level),offset=i*4;image.data[offset]=r;image.data[offset+1]=g;image.data[offset+2]=b;image.data[offset+3]=255;}
  rc.putImageData(image,0,0);context.clearRect(0,0,canvas.width,canvas.height);context.imageSmoothingEnabled=false;context.drawImage(raster,0,0,canvas.width,canvas.height);
}
function areaProbabilities(position){
  const map=position.probability_map||{},support=map.support_xy_mm||[],probability=map.probabilities||[],values=Array(activePanel.class_count).fill(0);
  if(support.length&&support.length===probability.length){support.forEach((point,index)=>{const column=Math.min(activePanel.columns-1,Math.max(0,Math.floor(Number(point[0])/(activePanel.width_mm/activePanel.columns)))),row=Math.min(activePanel.rows-1,Math.max(0,Math.floor(Number(point[1])/(activePanel.height_mm/activePanel.rows))));values[row*activePanel.columns+column]+=Number(probability[index]||0);});const sum=values.reduce((total,value)=>total+value,0);return sum>0?values.map(value=>value/sum):values;}
  const supplied=position.class_probabilities;return Array.isArray(supplied)&&supplied.length===activePanel.class_count?supplied.map(Number):values;
}
function pseudoCoordinate(position){
  const suppliedX=Number(position.expected_x_mm),suppliedY=Number(position.expected_y_mm);
  if(Number.isFinite(suppliedX)&&Number.isFinite(suppliedY))return [suppliedX,suppliedY];
  const map=position.probability_map||{},support=map.support_xy_mm||[],probability=map.probabilities||[];
  if(!support.length||support.length!==probability.length)return [Number(position.x_mm),Number(position.y_mm)];
  let sum=0,x=0,y=0;support.forEach((point,index)=>{const weight=Math.max(0,Number(probability[index])||0);sum+=weight;x+=Number(point[0])*weight;y+=Number(point[1])*weight;});
  return sum>0?[x/sum,y/sum]:[Number(position.x_mm),Number(position.y_mm)];
}
function cameraCanvas(){
  const canvas=$('cameraHeatmapOverlay'),rect=canvas.getBoundingClientRect(),width=Math.max(1,rect.width),height=Math.max(1,rect.height),ratio=window.devicePixelRatio||1,targetWidth=Math.round(width*ratio),targetHeight=Math.round(height*ratio);if(canvas.width!==targetWidth||canvas.height!==targetHeight){canvas.width=targetWidth;canvas.height=targetHeight;}const context=canvas.getContext('2d');context.setTransform(ratio,0,0,ratio,0,0);context.clearRect(0,0,width,height);return {canvas,context,width,height};
}
function lerpPoint(a,b,t){return [a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];}
function mappedSideRatio(v,side){const stops=[0,rowDividerRatios[0][side],rowDividerRatios[1][side],1],scaled=Math.max(0,Math.min(1,v))*3,index=Math.min(2,Math.floor(scaled)),fraction=scaled-index;return stops[index]+(stops[index+1]-stops[index])*fraction;}
function quadPoint(u,v,width,height){
  const points=calibrationPoints.map(([x,y])=>[x*width,y*height]),left=lerpPoint(points[0],points[3],mappedSideRatio(v,0)),right=lerpPoint(points[1],points[2],mappedSideRatio(v,1));return lerpPoint(left,right,u);
}
function dividerHandlePoint(divider,side){const start=side===0?calibrationPoints[0]:calibrationPoints[1],end=side===0?calibrationPoints[3]:calibrationPoints[2];return lerpPoint(start,end,rowDividerRatios[divider][side]);}
function calibrationHandles(){if(calibrationPoints.length!==4)return calibrationPoints.map((point,index)=>({point,index,label:String(index+1),kind:'corner'}));return [...calibrationPoints.map((point,index)=>({point,index,label:String(index+1),kind:'corner'})),{point:dividerHandlePoint(0,0),index:4,label:'L1',kind:'divider'},{point:dividerHandlePoint(0,1),index:5,label:'R1',kind:'divider'},{point:dividerHandlePoint(1,0),index:6,label:'L2',kind:'divider'},{point:dividerHandlePoint(1,1),index:7,label:'R2',kind:'divider'}];}
function cameraPolygon(context,points,fill='',stroke='',lineWidth=1){context.beginPath();points.forEach((point,index)=>index?context.lineTo(...point):context.moveTo(...point));context.closePath();if(fill){context.fillStyle=fill;context.fill();}if(stroke){context.strokeStyle=stroke;context.lineWidth=lineWidth;context.stroke();}}
function redrawCameraOverlay(){
  const {canvas,context,width,height}=cameraCanvas();canvas.hidden=$('displayMode')?.value!=='camera';if(canvas.hidden)return;
  if(calibrationPoints.length===4&&lastRenderedPosition){
    const map=lastRenderedPosition.probability_map||{},support=map.support_xy_mm||[],probability=map.probabilities||[],columns=40,rows=Math.round(columns*activePanel.height_mm/activePanel.width_mm),values=new Float32Array(columns*rows),inverse=1/(2*27*27);let peak=1e-12;
    if(heatmapVisible&&support.length&&support.length===probability.length){for(let row=0;row<rows;row++)for(let column=0;column<columns;column++){const x=(column+.5)*activePanel.width_mm/columns,y=(row+.5)*activePanel.height_mm/rows;let density=0;for(let index=0;index<support.length;index++){const dx=x-Number(support[index][0]),dy=y-Number(support[index][1]);density+=Math.max(0,Number(probability[index])||0)*Math.exp(-(dx*dx+dy*dy)*inverse);}values[row*columns+column]=density;peak=Math.max(peak,density);}for(let row=0;row<rows;row++)for(let column=0;column<columns;column++){const level=Math.round(Math.pow(values[row*columns+column]/peak,.52)*9)/9,[r,g,b]=heatColor(level),u0=column/columns,u1=(column+1)/columns,v0=row/rows,v1=(row+1)/rows;cameraPolygon(context,[quadPoint(u0,v0,width,height),quadPoint(u1,v0,width,height),quadPoint(u1,v1,width,height),quadPoint(u0,v1,width,height)],`rgba(${r},${g},${b},.52)`);}}
    if(panelAreaVisible){const areaValues=areaProbabilities(lastRenderedPosition),winner=areaValues.indexOf(Math.max(...areaValues)),winnerColumn=winner%activePanel.columns,winnerRow=Math.floor(winner/activePanel.columns),u0=winnerColumn/activePanel.columns,u1=(winnerColumn+1)/activePanel.columns,v0=winnerRow/activePanel.rows,v1=(winnerRow+1)/activePanel.rows;cameraPolygon(context,[quadPoint(u0,v0,width,height),quadPoint(u1,v0,width,height),quadPoint(u1,v1,width,height),quadPoint(u0,v1,width,height)],'rgba(255,224,75,.08)','#ffe04b',4);
    const nextArea=currentSongArea(),secondArea=currentSongArea(1);if(secondArea>=0&&secondArea!==nextArea){const secondColumn=secondArea%activePanel.columns,secondRow=Math.floor(secondArea/activePanel.columns),secondU0=secondColumn/activePanel.columns,secondU1=(secondColumn+1)/activePanel.columns,secondV0=secondRow/activePanel.rows,secondV1=(secondRow+1)/activePanel.rows;cameraPolygon(context,[quadPoint(secondU0,secondV0,width,height),quadPoint(secondU1,secondV0,width,height),quadPoint(secondU1,secondV1,width,height),quadPoint(secondU0,secondV1,width,height)],'rgba(255,190,213,.14)','#ffc8dc',2);}if(nextArea>=0){const nextColumn=nextArea%activePanel.columns,nextRow=Math.floor(nextArea/activePanel.columns),nextU0=nextColumn/activePanel.columns,nextU1=(nextColumn+1)/activePanel.columns,nextV0=nextRow/activePanel.rows,nextV1=(nextRow+1)/activePanel.rows;cameraPolygon(context,[quadPoint(nextU0,nextV0,width,height),quadPoint(nextU1,nextV0,width,height),quadPoint(nextU1,nextV1,width,height),quadPoint(nextU0,nextV1,width,height)],'rgba(255,145,184,.32)','#ff91b8',4);}}
    const mapX=Number(lastRenderedPosition.map_x_mm??lastRenderedPosition.x_mm),mapY=Number(lastRenderedPosition.map_y_mm??lastRenderedPosition.y_mm),marker=quadPoint(mapX/activePanel.width_mm,mapY/activePanel.height_mm,width,height);context.save();context.translate(...marker);context.rotate(Math.PI/4);context.fillStyle='#00777ccc';context.strokeStyle='#72ffff';context.lineWidth=3;context.fillRect(-7,-7,14,14);context.strokeRect(-7,-7,14,14);context.restore();
  }
  if(panelAreaVisible&&calibrationPoints.length===4){for(let column=0;column<=activePanel.columns;column++){const u=column/activePanel.columns;context.beginPath();for(let row=0;row<=activePanel.rows;row++){const point=quadPoint(u,row/activePanel.rows,width,height);row?context.lineTo(...point):context.moveTo(...point);}context.strokeStyle='#ffffff99';context.lineWidth=1;context.stroke();}for(let row=0;row<=activePanel.rows;row++){const v=row/activePanel.rows,a=quadPoint(0,v,width,height),b=quadPoint(1,v,width,height);context.beginPath();context.moveTo(...a);context.lineTo(...b);context.strokeStyle='#ffffff99';context.lineWidth=1;context.stroke();}context.save();context.textAlign='center';context.textBaseline='middle';context.font='800 20px Consolas,monospace';context.lineWidth=5;context.strokeStyle='#071d29cc';context.fillStyle='#fff';for(let area=0;area<activePanel.class_count;area++){const column=area%activePanel.columns,row=Math.floor(area/activePanel.columns),point=quadPoint((column+.5)/activePanel.columns,(row+.5)/activePanel.rows,width,height),label=panelNoteLabel(area);context.strokeText(label,...point);context.fillText(label,...point);}context.restore();}
  calibrationHandles().forEach(({point:[x,y],index,label,kind})=>{const px=x*width,py=y*height;context.beginPath();context.arc(px,py,kind==='corner'?7:8,0,Math.PI*2);context.fillStyle=calibrating&&index===calibrationPoints.length+dividerCalibrationStep?'#ff5d5d':kind==='corner'?'#6ffcff':'#ffb64c';context.fill();context.strokeStyle='#071d29';context.lineWidth=2;context.stroke();context.font='bold 11px sans-serif';context.textBaseline='middle';if(kind==='corner'){context.fillStyle='#071d29';context.textAlign='center';context.fillText(label,px,py);}else{const side=index%2,divider=index<6?0:1,ratio=Math.round(rowDividerRatios[divider][side]*100);context.textAlign=side===0?'left':'right';context.lineWidth=4;context.strokeStyle='#071d29';context.fillStyle='#fff';const tx=px+(side===0?12:-12),text=label+' '+ratio+'%';context.strokeText(text,tx,py);context.fillText(text,tx,py);}});
}
function updateOverlayInteraction(){const canvas=$('cameraHeatmapOverlay');canvas.classList.toggle('calibrating',calibrating);canvas.classList.toggle('calibrated',!calibrating&&calibrationPoints.length===4);canvas.classList.toggle('dragging',draggingCalibrationPoint>=0);}
function applyDisplayMode(){const cameraMode=$('displayMode').value==='camera';document.body.classList.toggle('camera-overlay-mode',cameraMode);localStorage.setItem(DISPLAY_MODE_KEY,$('displayMode').value);updateOverlayInteraction();redrawCameraOverlay();}
function updateHeatmapToggle(){const button=$('heatmapToggle');button.textContent=L('ヒートマップ ','Heatmap ')+(heatmapVisible?'ON':'OFF');button.setAttribute('aria-pressed',String(heatmapVisible));button.classList.toggle('primary',heatmapVisible);$('positionHeatmap').hidden=!heatmapVisible;}
function toggleHeatmap(){heatmapVisible=!heatmapVisible;localStorage.setItem(HEATMAP_VISIBLE_KEY,String(heatmapVisible));updateHeatmapToggle();if(lastRenderedPosition)drawHeatmap(lastRenderedPosition);redrawCameraOverlay();}
function updatePanelAreaToggle(){const button=$('panelAreaToggle');button.textContent=L('エリア表示 ','Areas ')+(panelAreaVisible?'ON':'OFF');button.setAttribute('aria-pressed',String(panelAreaVisible));button.classList.toggle('primary',panelAreaVisible);}
function togglePanelArea(){panelAreaVisible=!panelAreaVisible;localStorage.setItem(PANEL_AREA_VISIBLE_KEY,String(panelAreaVisible));updatePanelAreaToggle();redrawCameraOverlay();}
function showCalibrationStatus(ja='',en=''){calibrationStatusText=ja?[ja,en||ja]:null;const status=$('calibrationStatus');status.textContent=ja?L(ja,en||ja):'';status.hidden=!ja;}
function beginCalibration(){calibrationPoints=[];rowDividerRatios=[[1/3,1/3],[2/3,2/3]];calibrating=true;dividerCalibrationStep=0;draggingCalibrationPoint=-1;$('displayMode').value='camera';applyDisplayMode();showCalibrationStatus('左上をクリックしてください（1/8）','Click the top-left corner (1/8).');redrawCameraOverlay();}
function clearCalibration(){calibrationPoints=[];rowDividerRatios=[[1/3,1/3],[2/3,2/3]];calibrating=false;dividerCalibrationStep=0;draggingCalibrationPoint=-1;saveCalibration();updateOverlayInteraction();showCalibrationStatus('位置合わせを消去しました。8点フィットを実行してください。','Alignment cleared. Run 8-point fit.');redrawCameraOverlay();}
function overlayNormalizedPoint(event){const rect=$('cameraHeatmapOverlay').getBoundingClientRect();return [Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))];}
function projectSideRatio(point,side){const start=side===0?calibrationPoints[0]:calibrationPoints[1],end=side===0?calibrationPoints[3]:calibrationPoints[2],dx=end[0]-start[0],dy=end[1]-start[1],lengthSquared=dx*dx+dy*dy;return lengthSquared>1e-8?Math.max(0,Math.min(1,((point[0]-start[0])*dx+(point[1]-start[1])*dy)/lengthSquared)):.5;}
function setDividerHandle(handleIndex,point){const divider=handleIndex<6?0:1,side=handleIndex%2,other=rowDividerRatios[1-divider][side],minimumGap=.05,ratio=projectSideRatio(point,side);rowDividerRatios[divider][side]=divider===0?Math.max(.03,Math.min(other-minimumGap,ratio)):Math.min(.97,Math.max(other+minimumGap,ratio));}
function nextCalibrationPrompt(){const namesJa=['左上','右上','右下','左下','左側の上段境界','右側の上段境界','左側の下段境界','右側の下段境界'],namesEn=['top-left corner','top-right corner','bottom-right corner','bottom-left corner','upper divider on the left edge','upper divider on the right edge','lower divider on the left edge','lower divider on the right edge'],index=calibrationPoints.length<4?calibrationPoints.length:4+dividerCalibrationStep;showCalibrationStatus(namesJa[index]+'をクリックしてください（'+(index+1)+'/8）','Click the '+namesEn[index]+' ('+(index+1)+'/8).');}
function overlayPointerDown(event){const canvas=$('cameraHeatmapOverlay'),point=overlayNormalizedPoint(event);if(calibrating){if(calibrationPoints.length<4)calibrationPoints.push(point);else{setDividerHandle(4+dividerCalibrationStep,point);dividerCalibrationStep++;}if(calibrationPoints.length===4&&dividerCalibrationStep===4){calibrating=false;saveCalibration();showCalibrationStatus('8点フィット完了。青の四隅と橙の行境界をドラッグして微調整できます。','8-point fit complete. Drag the blue corners and orange row dividers to fine-tune.');}else nextCalibrationPrompt();updateOverlayInteraction();redrawCameraOverlay();return;}if(calibrationPoints.length!==4)return;const rect=canvas.getBoundingClientRect(),radius=24/Math.max(1,Math.min(rect.width,rect.height));let nearest=-1,distance=Infinity;calibrationHandles().forEach(({point:candidate,index})=>{const value=Math.hypot(candidate[0]-point[0],candidate[1]-point[1]);if(value<distance){distance=value;nearest=index;}});if(distance<=radius){draggingCalibrationPoint=nearest;canvas.setPointerCapture?.(event.pointerId);updateOverlayInteraction();event.preventDefault();}}
function overlayPointerMove(event){if(draggingCalibrationPoint<0)return;const point=overlayNormalizedPoint(event),namesJa=['左上','右上','右下','左下','左側の上段境界','右側の上段境界','左側の下段境界','右側の下段境界'],namesEn=['Top-left','Top-right','Bottom-right','Bottom-left','Left upper divider','Right upper divider','Left lower divider','Right lower divider'];if(draggingCalibrationPoint<4)calibrationPoints[draggingCalibrationPoint]=point;else setDividerHandle(draggingCalibrationPoint,point);showCalibrationStatus(namesJa[draggingCalibrationPoint]+'を調整中…',namesEn[draggingCalibrationPoint]+': adjusting…');redrawCameraOverlay();event.preventDefault();}
function overlayPointerUp(event){if(draggingCalibrationPoint<0)return;draggingCalibrationPoint=-1;saveCalibration();$('cameraHeatmapOverlay').releasePointerCapture?.(event.pointerId);updateOverlayInteraction();showCalibrationStatus('再マッピングしました。8点は引き続きドラッグできます。','Remapped. You can continue dragging all eight points.');redrawCameraOverlay();}
function renderPosition(position,play=false){
  if(!position||!Number.isFinite(Number(position.x_mm))||!Number.isFinite(Number(position.y_mm)))return;
  drawHeatmap(position);const x=Number(position.map_x_mm??position.x_mm),y=Number(position.map_y_mm??position.y_mm);
  const [pseudoX,pseudoY]=pseudoCoordinate(position),pseudoMarker=$('pseudoPositionMarker');pseudoMarker.hidden=false;pseudoMarker.style.left=`${pseudoX/activePanel.width_mm*100}%`;pseudoMarker.style.top=`${pseudoY/activePanel.height_mm*100}%`;
  const probabilities=areaProbabilities(position),area=probabilities.indexOf(Math.max(...probabilities)),areaProbability=probabilities[area]||0;
  const nextArea=currentSongArea(),secondArea=currentSongArea(1);Array.from($('areaSelectionGrid').children).forEach((cell,index)=>{cell.classList.toggle('winner',index===area);cell.classList.toggle('next-note',index===nextArea);cell.classList.toggle('second-next-note',index===secondArea&&index!==nextArea);});
  $('coordinateReadout').textContent=L('最尤60点 ','Most likely of 60 points ')+'X '+x.toFixed(1)+' / Y '+y.toFixed(1)+' mm';$('pseudoCoordinateReadout').textContent=L('疑似XY座標 ','Pseudo XY coordinate ')+'X '+pseudoX.toFixed(1)+' / Y '+pseudoY.toFixed(1)+' mm';$('areaReadout').textContent=L('最尤エリア ','Most likely area ')+(area+1);$('peakReadout').textContent=L('エリア確率 ','Area probability ')+(areaProbability*100).toFixed(1)+'%';
  $('distributionSource').textContent=L('UNO Q Linux 60座標確率モデル','UNO Q Linux 60-point probability model');
  $('areaProbabilities').innerHTML=probabilities.map((value,index)=>'<div class="area-probability '+(index===area?'winner':'')+' '+(index===nextArea?'next-note':'')+' '+(index===secondArea&&index!==nextArea?'second-next-note':'')+'"><span>'+L('エリア','Area ')+(index+1)+'<small>'+(panelNote(index)||'—')+'</small></span><i><b style="width:'+Math.max(0,Math.min(100,value*100))+'%"></b></i><output>'+(value*100).toFixed(1)+'%</output></div>').join('');
  lastRenderedPosition=position;redrawCameraOverlay();
  if(play&&performanceEnabled)playArea(area,areaProbability);
}
function flushPendingHeatmap(){
  heatmapTimer=null;if(!pendingHeatmapPosition)return;const position=pendingHeatmapPosition;pendingHeatmapPosition=null;renderPosition(position,false);lastHeatmapRenderedAt=performance.now();
}
function scheduleLivePosition(position){
  const probabilities=areaProbabilities(position),area=probabilities.indexOf(Math.max(...probabilities));if(performanceEnabled)playArea(area,probabilities[area]||0);
  const remaining=MIN_HEATMAP_DISPLAY_MS-(performance.now()-lastHeatmapRenderedAt);if(remaining<=0&&!heatmapTimer){renderPosition(position,false);lastHeatmapRenderedAt=performance.now();return;}pendingHeatmapPosition=position;if(!heatmapTimer)heatmapTimer=setTimeout(flushPendingHeatmap,Math.max(0,remaining));
}
function clearPendingHeatmap(){if(heatmapTimer)clearTimeout(heatmapTimer);heatmapTimer=null;pendingHeatmapPosition=null;}
function demo(){
  const support=[];for(let y=25;y<300;y+=50)for(let x=25;x<400;x+=50)support.push([x,y]);for(let y=50;y<300;y+=100)for(let x=50;x<400;x+=100)support.push([x,y]);const raw=support.map(([x,y])=>Math.exp(-((x-275)**2+(y-175)**2)/2200)+.25*Math.exp(-((x-125)**2+(y-75)**2)/1800)),sum=raw.reduce((a,b)=>a+b,0),probabilities=raw.map(v=>v/sum),maximum=probabilities.indexOf(Math.max(...probabilities));renderPosition({x_mm:support[maximum][0],y_mm:support[maximum][1],probability_map:{support_xy_mm:support,probabilities},inference_source:'device'},false);
}
async function inferenceLoop(){
  while(loopRunning){if(!performanceEnabled){await sleep(60);continue;}try{const after=lastSequence===null?'':String(lastSequence),result=await api(`/api/ai/wait?after=${encodeURIComponent(after)}&timeout=1.0`);if(result.sequence!==undefined&&result.sequence!==lastSequence){lastSequence=result.sequence;if(result.position)scheduleLivePosition(result.position);$('error').textContent='';}}catch(error){if(error.status!==204)$('error').textContent=error.message;await sleep(100);}}
}
async function startPerformance(){
  try{await ensureAudio();let current=await api('/api/status');if(current.inference_active)await api('/api/inference/stop',{});if(current.panel_profile_id!=='400x300x5')await api('/api/panel',{panel_profile_id:'400x300x5'});await api('/api/inference/retrigger',{milliseconds:80});current=await api('/api/status');lastSequence=current.latest_ai?.sequence??null;await api('/api/inference/start',{mode:modeForSource()});performanceEnabled=true;$('error').textContent='';performanceMessage={kind:'running'};renderPerformanceStatus();$('performanceStatus').classList.add('playing');await refreshStatus();}catch(error){$('error').textContent=error.message;}
}
async function stopPerformance(){try{performanceEnabled=false;clearPendingHeatmap();await api('/api/inference/stop',{});performanceMessage={kind:'stopped'};renderPerformanceStatus();$('performanceStatus').classList.remove('playing');await refreshStatus();}catch(error){$('error').textContent=error.message;}}

function cameraError(error){if(error?.name==='NotAllowedError')return L('カメラの使用が許可されていません。ブラウザの権限を確認してください。','Camera access is not allowed. Check the browser permission.');if(error?.name==='NotFoundError')return L('PCにカメラが見つかりません。','No camera was found on this PC.');if(error?.name==='NotReadableError')return L('PCカメラは他のアプリで使用中です。','The PC camera is in use by another application.');return error?.message||String(error);}
function releaseCamera(){if(cameraStream?.getTracks)cameraStream.getTracks().forEach(track=>track.stop());cameraStream=null;const pc=$('pcCamera'),frame=$('usbCamera');pc.pause();pc.srcObject=null;pc.hidden=true;frame.onload=null;frame.onerror=null;frame.removeAttribute('src');frame.hidden=true;$('cameraPlaceholder').hidden=false;$('cameraStart').disabled=false;$('cameraStop').disabled=true;$('calibrationStart').disabled=true;$('cameraState').classList.remove('is-running');}
async function refreshPcCameras(preferred=''){if(!navigator.mediaDevices?.enumerateDevices){$('cameraDevice').replaceChildren(new Option(L('利用できません','Unavailable'),''));return [];}const devices=(await navigator.mediaDevices.enumerateDevices()).filter(device=>device.kind==='videoinput'),current=preferred||localStorage.getItem(PC_CAMERA_KEY)||'';$('cameraDevice').replaceChildren(...(devices.length?devices.map((device,index)=>new Option(device.label||L('PCカメラ ','PC Camera ')+(index+1),device.deviceId)):[new Option(L('PCカメラが見つかりません','No PC camera found'),'')]));if(devices.some(device=>device.deviceId===current))$('cameraDevice').value=current;if(cameraSource==='pc')$('cameraStart').disabled=Boolean(cameraStream);return devices;}
function updateCameraSourceUi(){const local=cameraSource==='pc';$('cameraSource').value=cameraSource;$('cameraLabel').hidden=!local;$('cameraUrlLabel').hidden=local;$('cameraTitle').textContent=local?L('PCカメラ＋透過ヒートマップ','PC Camera + Heatmap Overlay'):L('UNO Q USBカメラ＋透過ヒートマップ','UNO Q USB Camera + Heatmap Overlay');if(!cameraStream){if(local)setCameraPlaceholder('このPCのカメラを選択して「カメラ開始」を押してください。','Select a camera on this PC and press Start camera.');else setCameraPlaceholder('UNO Qのカメラ配信URLを確認して「カメラ開始」を押してください。','Check the UNO Q camera stream URL and press Start camera.');}}
async function startCamera(){
  releaseCamera();setCameraState('connecting');
  try{
    if(cameraSource==='pc'){
      if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia)throw new Error(L('PCカメラは、このPCで開いた http://127.0.0.1 またはHTTPSページから利用してください。','Open this page through http://127.0.0.1 on this PC or through HTTPS to use the PC camera.'));
      const selected=$('cameraDevice').value,video={width:{ideal:1280},height:{ideal:720},frameRate:{ideal:30}};if(selected)video.deviceId={exact:selected};cameraStream=await navigator.mediaDevices.getUserMedia({audio:false,video});const pc=$('pcCamera');pc.srcObject=cameraStream;pc.hidden=false;await pc.play();const id=cameraStream.getVideoTracks()[0]?.getSettings().deviceId||selected;if(id)localStorage.setItem(PC_CAMERA_KEY,id);await refreshPcCameras(id);
    }else{
      const url=new URL($('cameraUrl').value.trim()||DEFAULT_CAMERA_STREAM);if(!['http:','https:'].includes(url.protocol))throw new Error(L('HTTPまたはHTTPSの配信URLを指定してください。','Specify an HTTP or HTTPS stream URL.'));$('cameraUrl').value=url.href;localStorage.setItem(CAMERA_KEY,url.href);const frame=$('usbCamera');cameraStream=url.href;frame.hidden=false;await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error(L('UNO Qカメラ配信が応答しません。USBホスト接続を確認してください。','The UNO Q camera stream did not respond. Check the USB host connection.'))),10000);frame.onload=()=>{clearTimeout(timer);resolve();};frame.onerror=()=>{clearTimeout(timer);reject(new Error(L('UNO Qカメラ配信を読み込めません。','Could not load the UNO Q camera stream.')));};frame.src=url.href;});
    }
    $('cameraPlaceholder').hidden=true;$('cameraStart').disabled=true;$('cameraStop').disabled=false;$('calibrationStart').disabled=false;setCameraState('running');$('cameraState').classList.add('is-running');redrawCameraOverlay();
  }catch(error){releaseCamera();setCameraState('failed');const message=cameraError(error);setCameraPlaceholder(message,message);}
}
async function setupCamera(){
  $('cameraUrl').value=localStorage.getItem(CAMERA_KEY)||DEFAULT_CAMERA_STREAM;$('cameraSource').value=cameraSource;updateCameraSourceUi();if(cameraSource==='pc')await refreshPcCameras().catch(()=>[]);setCameraState('waiting');
  $('cameraStart').onclick=startCamera;$('cameraStop').onclick=()=>{releaseCamera();setCameraState('stopped');};
  $('cameraSource').onchange=async()=>{releaseCamera();cameraSource=$('cameraSource').value==='unoq'?'unoq':'pc';localStorage.setItem(CAMERA_SOURCE_KEY,cameraSource);calibrationPoints=loadCalibration();rowDividerRatios=loadRowDividerRatios();calibrating=false;dividerCalibrationStep=0;draggingCalibrationPoint=-1;updateCameraSourceUi();updateOverlayInteraction();redrawCameraOverlay();if(cameraSource==='pc')await refreshPcCameras().catch(()=>[]);setCameraState('waiting');};
  $('cameraDevice').onchange=()=>{localStorage.setItem(PC_CAMERA_KEY,$('cameraDevice').value);if(cameraStream?.getTracks)startCamera();};$('cameraUrl').onchange=()=>localStorage.setItem(CAMERA_KEY,$('cameraUrl').value.trim());
  $('calibrationStart').onclick=beginCalibration;$('calibrationClear').onclick=clearCalibration;const overlay=$('cameraHeatmapOverlay');overlay.onpointerdown=overlayPointerDown;overlay.onpointermove=overlayPointerMove;overlay.onpointerup=overlayPointerUp;overlay.onpointercancel=overlayPointerUp;new ResizeObserver(redrawCameraOverlay).observe(document.querySelector('.camera-viewport'));showCalibrationStatus('','');updateOverlayInteraction();
  window.addEventListener('pagehide',releaseCamera);
}

$('refresh').onclick=()=>ports().catch(error=>$('error').textContent=error.message);
$('connect').onclick=async()=>{try{await api('/api/connect',{port:$('port').value});const current=await api('/api/status');if(current.panel_profile_id!=='400x300x5')await api('/api/panel',{panel_profile_id:'400x300x5'});await api('/api/device/mode',{mode:modeForSource()});await refreshStatus();}catch(error){$('error').textContent=error.message;}};
$('disconnect').onclick=async()=>{try{performanceEnabled=false;await api('/api/disconnect',{});await refreshStatus();}catch(error){$('error').textContent=error.message;}};
$('performanceStart').onclick=startPerformance;$('performanceStop').onclick=stopPerformance;$('probabilityDemo').onclick=demo;
$('positionSource').onchange=async()=>{try{const current=await api('/api/status');if(current.connected&&!current.inference_active)await api('/api/device/mode',{mode:modeForSource()});await refreshStatus();}catch(error){$('error').textContent=error.message;}};
$('instrumentSelect').value=settings.instrument;$('instrumentSelect').onchange=()=>{settings.instrument=$('instrumentSelect').value;saveInstrument();scheduleUnoQAudioPrime();};
$('masterVolume').value=String(Math.round(settings.masterVolume*100));const updateMasterVolume=()=>{settings.masterVolume=Number($('masterVolume').value)/100;$('masterVolumeValue').textContent=`${Math.round(settings.masterVolume*100)}%`;if(masterGain&&audioContext)masterGain.gain.setTargetAtTime(settings.masterVolume,audioContext.currentTime,.01);saveInstrument();};$('masterVolume').oninput=updateMasterVolume;updateMasterVolume();
$('songSelect').value=localStorage.getItem(SONG_KEY)||'';$('songSelect').onchange=()=>{configureSong($('songSelect').value,true);scheduleUnoQAudioPrime();};
$('songReset').onclick=()=>{stopGuide(false);songStep=0;updateSongAssist();};$('guidePlay').onclick=toggleGuide;configureSong($('songSelect').value,true);
$('noteLength').value=String(Math.round(noteLengthScale*100));const updateNoteLength=()=>{noteLengthScale=Number($('noteLength').value)/100;$('noteLengthValue').textContent=`${Math.round(noteLengthScale*100)}%`;localStorage.setItem(NOTE_LENGTH_KEY,String(noteLengthScale));scheduleUnoQAudioPrime();};$('noteLength').oninput=updateNoteLength;updateNoteLength();
$('languageToggle').onclick=()=>{language=language==='ja'?'en':'ja';applyLanguage();};applyLanguage();
$('displayMode').value='camera';localStorage.setItem(DISPLAY_MODE_KEY,'camera');applyDisplayMode();
$('heatmapToggle').onclick=toggleHeatmap;updateHeatmapToggle();
$('panelAreaToggle').onclick=togglePanelArea;updatePanelAreaToggle();
document.querySelectorAll('.app-tabs a').forEach(link=>link.addEventListener('click',async event=>{event.preventDefault();try{const current=await api('/api/status'),href=link.getAttribute('href');if(current.collection?.active)throw new Error(L('データ採取中はタブを切り替えられません。','Tabs cannot be switched while collecting data.'));if(current.inference_active)await api('/api/inference/stop',{});window.location.href=href;}catch(error){$('error').textContent=error.message;}}));

async function initialize(){try{const invalid=validateSongGuides();if(invalid.length)throw new Error(L('楽曲データ不整合: ','Invalid song data: ')+invalid.join(', '));await ports();const current=await api('/api/status');if(current.connected&&current.inference_active)await api('/api/inference/stop',{});if(current.connected&&current.panel_profile_id!=='400x300x5')await api('/api/panel',{panel_profile_id:'400x300x5'});await refreshStatus();}catch(error){$('error').textContent=error.message;}renderPosition({x_mm:200,y_mm:150,probability_map:{support_xy_mm:[],probabilities:[]},class_probabilities:Array(12).fill(1/12)},false);setupCamera();inferenceLoop();}
initialize();setInterval(refreshStatus,500);
