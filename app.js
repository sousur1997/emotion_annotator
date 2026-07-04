/* ---- PWA registration ---- */
if('serviceWorker' in navigator){
  window.addEventListener('load', ()=>{ navigator.serviceWorker.register('service-worker.js').catch(()=>{}); });
}

/* ============ emotion wheel data (3 rings) ============ */
const WHEEL = [
  { name:'Joy', color:'#e8b923', mid:[
      {label:'Optimistic', outer:['Hopeful','Inspired','Eager']},
      {label:'Confident',  outer:['Proud','Courageous','Self-assured']},
      {label:'Loving',     outer:['Affectionate','Fond','Warm']},
      {label:'Playful',    outer:['Delighted','Amused','Cheerful']} ]},
  { name:'Trust', color:'#5b9a4d', mid:[
      {label:'Accepted',  outer:['Respected','Valued','Included']},
      {label:'Grateful',  outer:['Blessed','Appreciative','Thankful']},
      {label:'Peaceful',  outer:['Calm','Content','Serene']},
      {label:'Admiring',  outer:['Impressed','Reverent','Devoted']} ]},
  { name:'Fear', color:'#3d84cf', mid:[
      {label:'Scared',      outer:['Frightened','Terrified','Panicky']},
      {label:'Anxious',     outer:['Worried','Nervous','Uneasy']},
      {label:'Insecure',    outer:['Inadequate','Inferior','Worthless']},
      {label:'Vulnerable',  outer:['Fragile','Hopeless','Exposed']} ]},
  { name:'Surprise', color:'#1fa6b8', mid:[
      {label:'Amazed',    outer:['Astonished','Awed','Dazzled']},
      {label:'Confused',  outer:['Disillusioned','Perplexed','Dumbfounded']},
      {label:'Startled',  outer:['Shocked','Speechless','Stunned']},
      {label:'Overcome',  outer:['Moved','Overwhelmed','Reeling']} ]},
  { name:'Sadness', color:'#5c6bc0', mid:[
      {label:'Lonely',     outer:['Isolated','Abandoned','Excluded']},
      {label:'Grieving',   outer:['Despair','Sorrow','Heartbroken']},
      {label:'Hurt',       outer:['Injured','Wronged','Disappointed']},
      {label:'Depressed',  outer:['Empty','Hopeless','Miserable']} ]},
  { name:'Disgust', color:'#9c46a8', mid:[
      {label:'Disapproving', outer:['Judgmental','Critical','Skeptical']},
      {label:'Disliking',    outer:['Repelled','Detestable','Loathsome']},
      {label:'Contemptuous', outer:['Ridicule','Scorn','Disdain']},
      {label:'Revolted',     outer:['Nauseated','Appalled','Awful']} ]},
  { name:'Anger', color:'#d64545', mid:[
      {label:'Frustrated',  outer:['Annoyed','Irritated','Aggravated']},
      {label:'Hostile',     outer:['Hateful','Spiteful','Vindictive']},
      {label:'Aggressive',  outer:['Provoked','Furious','Enraged']},
      {label:'Critical',    outer:['Insulted','Indignant','Betrayed']} ]},
  { name:'Anticipation', color:'#e08324', mid:[
      {label:'Interested',  outer:['Curious','Alert','Attentive']},
      {label:'Eager',       outer:['Enthusiastic','Motivated','Energized']},
      {label:'Excited',     outer:['Passionate','Aroused','Elated']},
      {label:'Stressed',    outer:['Overwhelmed','Pressured','Impatient']} ]},
];
const RING = {core:1/3, mid:2/3, outer:1};

const legend = document.getElementById('legend');
WHEEL.forEach(s=>{
  const c = document.createElement('div'); c.className='chip';
  c.innerHTML = `<span class="dot" style="background:${s.color}"></span>${s.name}`;
  legend.appendChild(c);
});

function hexToRgba(hex, a){
  const n = parseInt(hex.slice(1),16);
  return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`;
}
function coreIndex(theta){ return Math.floor((((theta%360)+360)%360)/45); }
function coreOf(theta){ return WHEEL[coreIndex(theta)]; }
function leafOf(theta,r){
  const idx = coreIndex(theta);
  const core = WHEEL[idx];
  const norm = (((theta%360)+360)%360);
  const angInSector = norm - idx*45;
  const midW = 45/core.mid.length;
  const midIdx = Math.min(core.mid.length-1, Math.floor(angInSector/midW));
  const mid = core.mid[midIdx];
  const angInMid = angInSector - midIdx*midW;
  const outW = midW/mid.outer.length;
  const outIdx = Math.min(mid.outer.length-1, Math.floor(angInMid/outW));
  let ring, word;
  if(r < RING.core){ ring='core'; word=core.name; }
  else if(r < RING.mid){ ring='mid'; word=mid.label; }
  else { ring='outer'; word=mid.outer[outIdx]; }
  return {core, mid, ring, word};
}
function breadcrumbFor(s){
  const leaf = leafOf(s.theta, s.r);
  return `${leaf.core.name} → ${leaf.mid.label}${leaf.ring==='outer' ? ' → '+leaf.word : ''}`;
}
function colorForStrip(strip){
  const core = coreOf(strip.theta);
  return hexToRgba(core.color, 0.28 + 0.55*strip.r);
}

/* ============ toast ============ */
const toastEl = document.getElementById('toast');
let toastTimer = null;
function showToast(msg){
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(()=>toastEl.classList.remove('show'), 2600);
}

/* ============ state ============ */
let duration = 0;
let strips = [];
let selectedId = null;
let selectedIds = new Set();
let boxSelectMode = false;
let nextId = 1;
let clipboard = null;
let stripPlaying = null;
let waveform = null;
let hover = {id:null, part:null};
let ctxTargetId = null;
const SNAP_PX = 10;

// undo/redo stacks
const UNDO_LIMIT = 80;
let undoStack = [];
let redoStack = [];

function snapshot(){ return { strips: JSON.parse(JSON.stringify(strips)), nextId }; }
function restoreSnapshot(snap){ strips = snap.strips.map(s=>Object.assign({}, s)); nextId = snap.nextId; select(null); drawTimeline(); refreshPanel(); }
function saveStateForUndo(){ undoStack.push(snapshot()); if(undoStack.length>UNDO_LIMIT) undoStack.shift(); redoStack = []; }
function undo(){ if(undoStack.length===0) return; redoStack.push(snapshot()); const snap = undoStack.pop(); restoreSnapshot(snap); }
function redo(){ if(redoStack.length===0) return; undoStack.push(snapshot()); const snap = redoStack.pop(); restoreSnapshot(snap); }

// track pointer inside timeline for Ctrl+A behavior
let pointerOverTimeline = false;

let viewStart = 0;
let pxPerSec = 50;
let fitPxPerSec = 50;

const video = document.getElementById('video');
const emptyHint = document.getElementById('emptyHint');
const mediaInput = document.getElementById('mediaInput');
const addStripBtn = document.getElementById('addStripBtn');
const dupBtn = document.getElementById('dupBtn');
const copyBtn = document.getElementById('copyBtn');
const pasteBtn = document.getElementById('pasteBtn');
const deleteBtnTop = document.getElementById('deleteBtnTop');
const playStripBtn = document.getElementById('playStripBtn');
const loopChk = document.getElementById('loopChk');
const exportBtn = document.getElementById('exportBtn');
const importInput = document.getElementById('importInput');
const timeLabel = document.getElementById('timeLabel');
const frameInput = document.getElementById('frameInput');
const FPS = 30; // assumed rate for frame-based stepping/display — browsers don't expose a video's real fps
const panSlider = document.getElementById('panSlider');
const sidebarEl = document.querySelector('.sidebar');
const ctxMenu = document.getElementById('ctxMenu');

// Create small icon buttons and replace existing button labels for compact UI
function makeIcon(html){ const span = document.createElement('span'); span.className='icon'; span.innerHTML = html; return span; }
try{
  addStripBtn.innerHTML = ''; addStripBtn.appendChild(makeIcon('➕'));
  dupBtn.innerHTML = ''; dupBtn.appendChild(makeIcon('⎘'));
  copyBtn.innerHTML = ''; copyBtn.appendChild(makeIcon('📋'));
  pasteBtn.innerHTML = ''; pasteBtn.appendChild(makeIcon('📥'));
  deleteBtnTop.innerHTML = ''; deleteBtnTop.appendChild(makeIcon('🗑'));
  playStripBtn.innerHTML = ''; playStripBtn.appendChild(makeIcon('▶'));
  exportBtn.innerHTML = ''; exportBtn.appendChild(makeIcon('⬇'));
}catch(err){ }

// add undo/redo, clear all and new project buttons near addStripBtn if toolbar present
(function addExtraButtons(){
  const toolbar = addStripBtn && addStripBtn.parentNode;
  if(!toolbar) return;
  const btns = [
    {id:'undoBtn', title:'Undo (Ctrl+Z)', icon:'↺', on:()=>undo()},
    {id:'redoBtn', title:'Redo (Ctrl+Shift+Z)', icon:'↻', on:()=>redo()},
    {id:'clearAllBtn', title:'Remove all strips', icon:'🧹', on:()=>{ if(strips.length===0) return; saveStateForUndo(); strips=[]; select(null); drawTimeline(); showToast('All strips removed'); }},
    {id:'newProjectBtn', title:'New project', icon:'🆕', on:()=>{
      saveStateForUndo(); strips=[]; nextId=1; selectedIds.clear(); selectedId=null; video.pause(); video.src=''; video.style.display='none'; emptyHint.style.display='block'; waveform=null; duration=0; addStripBtn.disabled=true; exportBtn.disabled=true; fitView(); drawTimeline(); showToast('New project started');
    }}
  ];
  btns.forEach(b=>{
    if(document.getElementById(b.id)) return;
    const n=document.createElement('button'); n.id=b.id; n.className='icon-btn'; n.title=b.title; n.appendChild(makeIcon(b.icon)); n.addEventListener('click', b.on);
    toolbar.insertBefore(n, addStripBtn);
  });
})();

/* ============ media load ============ */
mediaInput.addEventListener('change', e=>{
  const f = e.target.files[0];
  if(!f) return;
  video.src = URL.createObjectURL(f);
  video.style.display='block';
  emptyHint.style.display='none';
  waveform = null;
  decodeWaveform(f);
});
video.addEventListener('loadedmetadata', ()=>{
  duration = video.duration;
  addStripBtn.disabled = false;
  exportBtn.disabled = false;
  frameInput.max = Math.round(duration*FPS);
  fitView();
  drawTimeline();
});
const playPauseBtn = document.getElementById('playPauseBtn');
function syncPlayIcon(){ if(playPauseBtn) playPauseBtn.textContent = video.paused ? '▶' : '⏸'; }
video.addEventListener('play', syncPlayIcon);
video.addEventListener('pause', syncPlayIcon);
video.addEventListener('ended', syncPlayIcon);

video.addEventListener('timeupdate', ()=>{
  if(stripPlaying && video.currentTime >= stripPlaying.end){
    if(loopChk.checked){ video.currentTime = stripPlaying.start; }
    else { video.pause(); video.currentTime = stripPlaying.end; stripPlaying = null; }
  }
  if(document.activeElement!==frameInput) frameInput.value = Math.round(video.currentTime*FPS);
  updateTimeLabel();
});
frameInput.addEventListener('change', ()=>{
  if(!duration) return;
  let f = parseInt(frameInput.value,10);
  if(isNaN(f)) f=0;
  f = Math.max(0, Math.min(Math.round(duration*FPS), f));
  video.currentTime = f/FPS;
  frameInput.value = f;
});

// transport button wiring
playPauseBtn.addEventListener('click', ()=>{ if(video.paused) video.play(); else video.pause(); });
document.getElementById('firstFrameBtn').addEventListener('click', ()=>{ video.pause(); stripPlaying=null; video.currentTime=0; });
document.getElementById('prevFrameBtn').addEventListener('click', ()=>{ video.pause(); stripPlaying=null; video.currentTime=Math.max(0, video.currentTime-1/FPS); });
document.getElementById('nextFrameBtn').addEventListener('click', ()=>{ video.pause(); stripPlaying=null; video.currentTime=Math.min(duration||0, video.currentTime+1/FPS); });
document.getElementById('lastFrameBtn').addEventListener('click', ()=>{ video.pause(); stripPlaying=null; video.currentTime=duration||0; });
function updateTimeLabel(){
  timeLabel.textContent = `${fmt(video.currentTime)} / ${fmt(duration||0)}`;
  drawTimeline();
}
function fmt(t){
  const m = Math.floor(t/60), s = (t%60);
  return String(m).padStart(2,'0')+':'+s.toFixed(2).padStart(5,'0');
}
function raf(){ if(video && !video.paused){ drawTimeline(); } requestAnimationFrame(raf); }
requestAnimationFrame(raf);

/* ============ waveform decode ============ */
async function decodeWaveform(file){
  try{
    const buf = await file.arrayBuffer();
    const ctx = new (window.AudioContext||window.webkitAudioContext)();
    const audioBuffer = await ctx.decodeAudioData(buf);
    const chans = [];
    for(let c=0;c<audioBuffer.numberOfChannels;c++) chans.push(audioBuffer.getChannelData(c));
    const len = chans[0].length;
    const N = 6000;
    const bucket = Math.max(1, Math.floor(len/N));
    const peaks = new Float32Array(N*2);
    for(let i=0;i<N;i++){
      const start = i*bucket, end = Math.min(len, start+bucket);
      let mn=1, mx=-1;
      for(let j=start;j<end;j++){
        let v=0; for(let c=0;c<chans.length;c++) v+=chans[c][j];
        v/=chans.length;
        if(v<mn) mn=v; if(v>mx) mx=v;
      }
      if(end<=start){ mn=0; mx=0; }
      peaks[i*2]=mn; peaks[i*2+1]=mx;
    }
    waveform = {peaks, n:N, dur:audioBuffer.duration};
    drawTimeline();
  }catch(err){ waveform = null; }
}

/* ============ zoom / pan ============ */
function fitView(){
  const w = tl.getBoundingClientRect().width || tl.clientWidth || 900;
  fitPxPerSec = duration>0 ? w/duration : 50;
  pxPerSec = fitPxPerSec;
  viewStart = 0;
  updatePanSlider();
}
function visibleDur(){ const w = tl.getBoundingClientRect().width; return w/pxPerSec; }
function clampView(){
  const vd = visibleDur();
  viewStart = Math.max(0, Math.min(Math.max(0,duration-vd), viewStart));
}
function updatePanSlider(){
  const vd = visibleDur();
  const maxStart = Math.max(0.0001, duration-vd);
  panSlider.max = 1;
  panSlider.value = maxStart>0 ? viewStart/maxStart : 0;
  panSlider.style.opacity = (pxPerSec>fitPxPerSec*1.02) ? '1' : '.35';
}
panSlider.addEventListener('input', ()=>{
  const vd = visibleDur();
  const maxStart = Math.max(0, duration-vd);
  viewStart = parseFloat(panSlider.value)*maxStart;
  drawTimeline();
});
document.getElementById('zoomInBtn').addEventListener('click', ()=>zoomAt(tl.clientWidth/2, 1.5));
document.getElementById('zoomOutBtn').addEventListener('click', ()=>zoomAt(tl.clientWidth/2, 1/1.5));
document.getElementById('fitBtn').addEventListener('click', ()=>{ fitView(); drawTimeline(); });
const boxSelectBtn = document.getElementById('boxSelectBtn');
boxSelectBtn.addEventListener('click', ()=>{
  boxSelectMode = !boxSelectMode;
  boxSelectBtn.classList.toggle('active', boxSelectMode);
});

function zoomAt(x, factor){
  if(!duration) return;
  const t = xToTime(x);
  pxPerSec = Math.max(fitPxPerSec, Math.min(4000, pxPerSec*factor));
  viewStart = t - x/pxPerSec;
  clampView();
  updatePanSlider();
  drawTimeline();
}

/* ============ timeline canvas ============ */
const tl = document.getElementById('timeline');
const tlCtx = tl.getContext('2d');
// track pointer inside timeline for Ctrl+A behavior (attach after element exists)
tl.addEventListener('mouseenter', ()=>pointerOverTimeline=true);
tl.addEventListener('mouseleave', ()=>pointerOverTimeline=false);
window.addEventListener('resize', ()=>{
  fitPxPerSec = duration? tl.getBoundingClientRect().width/duration : fitPxPerSec;
  layoutWheelCanvas(); drawWheel(strips.find(s=>s.id===selectedId)||null);
  drawTimeline();
});

function xToTime(x){ return Math.max(0, Math.min(duration, viewStart + x/pxPerSec)); }
function timeToX(t){ return (t-viewStart)*pxPerSec; }
function relPos(e){ const r=tl.getBoundingClientRect(); return {x:e.clientX-r.left, y:e.clientY-r.top}; }

const RULER_H=18, STRIP_H=46, EDGE_PX=7;
function getLayout(){
  const h = tl.getBoundingClientRect().height || 150;
  const waveH = Math.max(20, h - RULER_H - STRIP_H - 10);
  return { RULER_H, WAVE_H: waveH, STRIP_Y: RULER_H+waveH, STRIP_H };
}

function roundRectPath(ctx,x,y,w,h,rad){
  const r = Math.max(0, Math.min(rad, w/2, h/2));
  ctx.beginPath();
  ctx.moveTo(x+r,y);
  ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);
  ctx.arcTo(x,y,x+w,y,r);
  ctx.closePath();
}

function hitStrip(x){
  for(const s of strips){
    const x1=timeToX(s.start), x2=timeToX(s.end);
    if(Math.abs(x-x1)<=EDGE_PX) return {strip:s, part:'left'};
    if(Math.abs(x-x2)<=EDGE_PX) return {strip:s, part:'right'};
    if(x>x1 && x<x2) return {strip:s, part:'move'};
  }
  return null;
}

/* ---- snapping / overlap helpers ---- */
function getBounds(excludeId, refStart, refEnd){
  let left=0, right=duration;
  strips.forEach(s=>{
    if(s.id===excludeId) return;
    if(s.end<=refStart+1e-9 && s.end>left) left=s.end;
    if(s.start>=refEnd-1e-9 && s.start<right) right=s.start;
  });
  return {left,right};
}
function snapCandidates(excludeId){
  const arr=[0,duration];
  if(!isNaN(video.currentTime)) arr.push(video.currentTime);
  strips.forEach(s=>{ if(s.id!==excludeId){ arr.push(s.start); arr.push(s.end); } });
  return arr;
}
function trySnap(value, candidates){
  const snapSecs = SNAP_PX/pxPerSec;
  let best=value, bestDist=snapSecs;
  candidates.forEach(c=>{ const d=Math.abs(c-value); if(d<=bestDist){ bestDist=d; best=c; } });
  return best;
}
function strictlyInsideAnother(t, excludeId){
  return strips.some(s=> s.id!==excludeId && t>s.start+1e-6 && t<s.end-1e-6);
}

function drawTimeline(){
  const dpr = window.devicePixelRatio||1;
  const {RULER_H, WAVE_H, STRIP_Y, STRIP_H} = getLayout();
  const rect = tl.getBoundingClientRect();
  const w = rect.width, h = rect.height || 150;
  tl.width = w*dpr; tl.height = h*dpr;
  tlCtx.setTransform(dpr,0,0,dpr,0,0);
  tlCtx.clearRect(0,0,w,h);
  tlCtx.fillStyle = '#fbfbfc';
  tlCtx.fillRect(0,0,w,h);

  if(duration>0){
    tlCtx.strokeStyle = '#e6e8ec';
    tlCtx.fillStyle = '#8a90a0';
    tlCtx.font = '10px Consolas, monospace';
    const step = niceStep(visibleDur());
    const t0 = Math.floor(viewStart/step)*step;
    for(let t=t0; t<=viewStart+visibleDur()+step; t+=step){
      if(t<0) continue;
      const x = timeToX(t);
      tlCtx.beginPath(); tlCtx.moveTo(x,RULER_H); tlCtx.lineTo(x,h); tlCtx.stroke();
      tlCtx.fillText(fmt(t), x+3, 12);
    }

    tlCtx.fillStyle = '#eef0f4';
    tlCtx.fillRect(0,RULER_H,w,WAVE_H);
    const midY = RULER_H+WAVE_H/2;
    if(waveform){
      tlCtx.strokeStyle = '#8a93d8';
      tlCtx.beginPath();
      for(let x=0;x<w;x++){
        const t = xToTime(x);
        const bIdx = Math.floor((t/waveform.dur)*waveform.n);
        const pxSpanBuckets = Math.max(1, Math.ceil((1/pxPerSec)/(waveform.dur/waveform.n)));
        let mn=1, mx=-1;
        for(let k=0;k<pxSpanBuckets;k++){
          const idx = Math.min(waveform.n-1, Math.max(0, bIdx+k));
          const a = waveform.peaks[idx*2], b = waveform.peaks[idx*2+1];
          if(a<mn) mn=a; if(b>mx) mx=b;
        }
        if(mx<mn){ mn=0; mx=0; }
        tlCtx.moveTo(x, midY - mx*(WAVE_H/2-2));
        tlCtx.lineTo(x, midY - mn*(WAVE_H/2-2));
      }
      tlCtx.stroke();
    } else {
      tlCtx.fillStyle='#a9aebb'; tlCtx.font='11px Segoe UI, sans-serif';
      tlCtx.fillText('waveform unavailable for this file', 10, midY+4);
    }
    tlCtx.fillStyle='rgba(68,83,216,0.06)';
    tlCtx.fillRect(0,0,w,RULER_H+WAVE_H);

    let boxT0=null, boxT1=null;
    if(drag && drag.mode==='boxselect'){
      const curT = drag.currentT ?? drag.anchorT;
      boxT0 = Math.min(drag.anchorT, curT);
      boxT1 = Math.max(drag.anchorT, curT);
    }

    strips.forEach(s=>{
      const x1 = timeToX(s.start), x2 = timeToX(s.end);
      if(x2<0 || x1>w) return;
      const rx = Math.max(0,x1), rw = Math.max(2, x2-rx);
      const inBox = boxT0!=null && s.end>boxT0 && s.start<boxT1;
      const isSel = selectedIds.has(s.id) || inBox;
      const isHover = hover.id===s.id;

      roundRectPath(tlCtx, rx, STRIP_Y, rw, STRIP_H, 8);
      tlCtx.fillStyle = colorForStrip(s);
      tlCtx.fill();
      tlCtx.lineWidth = isSel ? 2.4 : (isHover ? 1.6 : 1);
      tlCtx.strokeStyle = isSel ? '#20242c' : (isHover ? '#4453d8' : 'rgba(0,0,0,0.18)');
      tlCtx.stroke();

      tlCtx.save();
      roundRectPath(tlCtx, rx, STRIP_Y, rw, STRIP_H, 8);
      tlCtx.clip();
      tlCtx.fillStyle = coreOf(s.theta).color;
      tlCtx.fillRect(rx, STRIP_Y, 4, STRIP_H);
      if(inBox && !selectedIds.has(s.id)){
        tlCtx.fillStyle='rgba(68,83,216,0.18)';
        tlCtx.fillRect(rx, STRIP_Y, rw, STRIP_H);
      }
      tlCtx.restore();

      if(isHover && hover.part==='left'){
        tlCtx.fillStyle='#4453d8'; tlCtx.fillRect(x1-2,STRIP_Y+4,4,STRIP_H-8);
      }
      if(isHover && hover.part==='right'){
        tlCtx.fillStyle='#4453d8'; tlCtx.fillRect(x2-2,STRIP_Y+4,4,STRIP_H-8);
      }

      if(rw>36){
        const leaf = leafOf(s.theta,s.r);
        tlCtx.save();
        roundRectPath(tlCtx, rx, STRIP_Y, rw, STRIP_H, 8); tlCtx.clip();
        tlCtx.fillStyle = '#171a20';
        tlCtx.font = 'bold 11px Segoe UI, sans-serif';
        tlCtx.fillText(s.r>0 ? leaf.word : `${leaf.word} (neutral)`, rx+10, STRIP_Y+18);
        tlCtx.fillStyle = 'rgba(23,26,32,0.65)';
        tlCtx.font = '10px Segoe UI, sans-serif';
        tlCtx.fillText(`${leaf.core.name} · ${(s.r*100).toFixed(0)}%`, rx+10, STRIP_Y+33);
        tlCtx.restore();
      }
    });

    if(boxT0!=null){
      const bx1 = timeToX(boxT0), bx2 = timeToX(boxT1);
      tlCtx.fillStyle = 'rgba(68,83,216,0.12)';
      tlCtx.fillRect(bx1, 2, Math.max(1,bx2-bx1), h-4);
      tlCtx.strokeStyle = '#4453d8'; tlCtx.lineWidth = 1.4;
      tlCtx.setLineDash([4,3]);
      tlCtx.strokeRect(bx1, 2, Math.max(1,bx2-bx1), h-4);
      tlCtx.setLineDash([]);
    }

    const px = timeToX(video.currentTime);
    if(px>=0 && px<=w){
      tlCtx.strokeStyle = '#e0433f'; tlCtx.lineWidth = 1.5;
      tlCtx.beginPath(); tlCtx.moveTo(px,0); tlCtx.lineTo(px,h); tlCtx.stroke();
      tlCtx.fillStyle='#e0433f';
      tlCtx.beginPath(); tlCtx.moveTo(px-5,0); tlCtx.lineTo(px+5,0); tlCtx.lineTo(px,7); tlCtx.closePath(); tlCtx.fill();
    }
  }
  updatePanSlider();
}
function niceStep(visSec){
  const target = visSec/8;
  const steps=[0.05,0.1,0.25,0.5,1,2,5,10,15,30,60,120,300,600];
  return steps.find(s=>s>=target)||600;
}

/* ============ timeline interaction ============ */
let drag = null;

/* pinch-to-zoom / two-finger pan (touch only — mice never have 2 contact points) */
const activeTouches = new Map(); // pointerId -> {x,y}
let pinchStartDist = null, pinchStartPxPerSec = null, pinchStartMidTime = null;

function touchMidAndDist(){
  const pts = [...activeTouches.values()];
  const dx = pts[0].x - pts[1].x, dy = pts[0].y - pts[1].y;
  const dist = Math.sqrt(dx*dx + dy*dy);
  const midX = (pts[0].x + pts[1].x)/2;
  return {dist, midX};
}
tl.addEventListener('pointerdown', e=>{
  if(e.pointerType!=='touch') return;
  activeTouches.set(e.pointerId, {x:e.clientX, y:e.clientY});
  if(activeTouches.size===2){
    // a second finger arrived — cancel whatever single-finger drag/long-press was in progress
    drag = null;
    cancelLongPressWatch();
    const {dist, midX} = touchMidAndDist();
    pinchStartDist = dist;
    pinchStartPxPerSec = pxPerSec;
    const rect = tl.getBoundingClientRect();
    pinchStartMidTime = xToTime(midX - rect.left);
  }
});
window.addEventListener('pointermove', e=>{
  if(e.pointerType!=='touch' || !activeTouches.has(e.pointerId)) return;
  activeTouches.set(e.pointerId, {x:e.clientX, y:e.clientY});
  if(activeTouches.size===2 && pinchStartDist!=null){
    e.preventDefault();
    const {dist, midX} = touchMidAndDist();
    const scale = dist / Math.max(1, pinchStartDist);
    pxPerSec = Math.max(fitPxPerSec, Math.min(4000, pinchStartPxPerSec * scale));
    const rect = tl.getBoundingClientRect();
    const midT = xToTime(midX - rect.left);
    // keep the point under the fingers fixed (combined pinch-zoom + two-finger pan)
    viewStart += (pinchStartMidTime - midT);
    clampView();
    drawTimeline();
  }
});
function endTouch(e){
  if(e.pointerType!=='touch') return;
  activeTouches.delete(e.pointerId);
  if(activeTouches.size<2){ pinchStartDist=null; pinchStartPxPerSec=null; pinchStartMidTime=null; }
}
window.addEventListener('pointerup', endTouch);
window.addEventListener('pointercancel', endTouch);

// make timeline touch/pen friendly: prevent browser scrolling during interaction
tl.style.touchAction = tl.style.touchAction || 'none';

tl.addEventListener('auxclick', e=>{ if(e.button===1) e.preventDefault(); });

// unify mouse + pointer handling so pen/touch interactions won't scroll the page
function handleDown(e){
  if(!duration) return;
  // middle button = pan
  if(e.button===1){
    e.preventDefault();
    drag = {mode:'pan', startX:e.clientX, startViewStart:viewStart};
    tl.style.cursor='grabbing';
    return;
  }
  // block right-click and any non-primary button from creating strips
  if(e.button !== 0 && e.button !== undefined) return;

  const {STRIP_Y, STRIP_H} = getLayout();
  const {x,y} = relPos(e);
  const t = xToTime(x);

  if(boxSelectMode || (e.shiftKey && !e.ctrlKey)){
    drag = {mode:'boxselect', anchorX:x, anchorT:t, currentX:x, currentT:t};
    drawTimeline();
    return;
  }

  if(y < STRIP_Y-2 || y > STRIP_Y+STRIP_H+2){
    drag = {mode:'scrub'};
    video.currentTime = t;
    drawTimeline();
    return;
  }

  const hit = hitStrip(x);
  if(hit){
    // ctrl-click = toggle single strip in/out of selection
    if(e.ctrlKey){
      if(selectedIds.has(hit.strip.id)){
        selectedIds.delete(hit.strip.id);
        if(selectedId===hit.strip.id) selectedId = [...selectedIds][0]||null;
      } else { selectedIds.add(hit.strip.id); selectedId = hit.strip.id; }
      copyBtn.disabled = dupBtn.disabled = deleteBtnTop.disabled = playStripBtn.disabled = selectedIds.size===0;
      drawTimeline(); return;
    }
    if(hit.part==='left'){
      saveStateForUndo();
      const b = getBounds(hit.strip.id, hit.strip.start, hit.strip.end);
      drag={mode:'resize-l',id:hit.strip.id,bounds:b};
      select(hit.strip.id); return;
    }
    if(hit.part==='right'){
      saveStateForUndo();
      const b = getBounds(hit.strip.id, hit.strip.start, hit.strip.end);
      drag={mode:'resize-r',id:hit.strip.id,bounds:b};
      select(hit.strip.id); return;
    }
    saveStateForUndo();
    // multi-selection move: drag the whole group
    if(selectedIds.size > 1 && selectedIds.has(hit.strip.id)){
      const origPositions = {};
      [...selectedIds].forEach(id=>{
        const ss = strips.find(s=>s.id===id);
        if(ss) origPositions[id] = {start:ss.start, end:ss.end};
      });
      drag={mode:'multimove', ids:[...selectedIds], origPositions, grabT:t};
    } else {
      const b = getBounds(hit.strip.id, hit.strip.start, hit.strip.end);
      drag={mode:'move',id:hit.strip.id,origStart:hit.strip.start,origEnd:hit.strip.end,grabT:t,bounds:b};
      select(hit.strip.id);
    }
    return;
  }

  // empty space click/tap — deselect first, create strip on second click
  if(selectedIds.size > 0){
    selectedIds.clear(); selectedId=null;
    copyBtn.disabled = dupBtn.disabled = deleteBtnTop.disabled = playStripBtn.disabled = true;
    refreshPanel(); drawTimeline();
    return;
  }

  if(strictlyInsideAnother(t, null)){
    showToast('Can’t start a strip here — it overlaps an existing strip.');
    return;
  }
  const id = nextId++;
  saveStateForUndo();
  const bounds = getBounds(id, t, t);
  strips.push({id,start:t,end:t,theta:0,r:0});
  drag = {mode:'create', id, anchor:t, bounds};
  select(id);
}

function handleMove(e){
  const {x,y} = relPos(e);
  if(drag && drag.mode==='pan'){
    const deltaX = e.clientX - drag.startX;
    viewStart = drag.startViewStart - deltaX/pxPerSec;
    clampView();
    drawTimeline();
    return;
  }
  if(drag && drag.mode==='boxselect'){
    drag.currentX = x;
    drag.currentT = xToTime(x);
    drawTimeline();
    return;
  }
  const {STRIP_Y, STRIP_H} = getLayout();
  if(!drag){
    if(!duration) return;
    if(y < STRIP_Y-2 || y > STRIP_Y+STRIP_H+2){
      hover = {id:null, part:null};
      tl.style.cursor = 'pointer';
      return;
    }
    const hit = hitStrip(x);
    if(hit){
      hover = {id:hit.strip.id, part:hit.part};
      tl.style.cursor = hit.part==='move' ? 'grab' : 'ew-resize';
    } else {
      hover = {id:null, part:null};
      tl.style.cursor = 'crosshair';
    }
    drawTimeline();
    return;
  }
  const t = xToTime(x);
  if(drag.mode==='scrub'){ video.currentTime = t; return; }

  // multimove has no drag.id — handle it before the single-strip lookup
  if(drag.mode==='multimove'){
    tl.style.cursor='grabbing';
    let delta = t - drag.grabT;
    const selSet = new Set(drag.ids);
    drag.ids.forEach(id=>{
      const orig = drag.origPositions[id]; if(!orig) return;
      let leftBound = 0, rightBound = duration;
      strips.forEach(s=>{
        if(selSet.has(s.id)) return;
        if(s.end <= orig.start + 1e-9 && s.end > leftBound) leftBound = s.end;
        if(s.start >= orig.end - 1e-9 && s.start < rightBound) rightBound = s.start;
      });
      delta = Math.max(leftBound - orig.start, Math.min(rightBound - orig.end, delta));
    });
    drag.ids.forEach(id=>{
      const ss = strips.find(s=>s.id===id);
      const orig = drag.origPositions[id];
      if(!ss || !orig) return;
      ss.start = orig.start + delta;
      ss.end   = orig.end   + delta;
    });
    drawTimeline();
    return;
  }

  const s = strips.find(s=>s.id===drag.id);
  if(!s) return;
  const cands = snapCandidates(drag.id);

  if(drag.mode==='create'){
    let a=Math.max(drag.bounds.left, Math.min(drag.bounds.right, Math.min(drag.anchor,t)));
    let b=Math.max(drag.bounds.left, Math.min(drag.bounds.right, Math.max(drag.anchor,t)));
    a = trySnap(a, cands); b = trySnap(b, cands);
    a = Math.max(drag.bounds.left, a); b = Math.min(drag.bounds.right, b);
    s.start=a; s.end=b;
  } else if(drag.mode==='move'){
    tl.style.cursor='grabbing';
    const len=drag.origEnd-drag.origStart;
    let ns = drag.origStart + (t-drag.grabT);
    ns = Math.max(drag.bounds.left, Math.min(drag.bounds.right-len, ns));
    const snappedStart = trySnap(ns, cands);
    if(snappedStart!==ns){ ns = snappedStart; }
    else {
      const snappedEnd = trySnap(ns+len, cands);
      if(snappedEnd!==ns+len) ns = snappedEnd-len;
    }
    ns = Math.max(drag.bounds.left, Math.min(drag.bounds.right-len, ns));
    s.start=ns; s.end=ns+len;
  } else if(drag.mode==='resize-l'){
    const s = strips.find(s=>s.id===drag.id); if(!s) return;
    const cands = snapCandidates(drag.id);
    let a = Math.max(drag.bounds.left, Math.min(t, s.end-0.05));
    a = trySnap(a, cands);
    a = Math.max(drag.bounds.left, Math.min(a, s.end-0.05));
    s.start=a;
  } else if(drag.mode==='resize-r'){
    const s = strips.find(s=>s.id===drag.id); if(!s) return;
    const cands = snapCandidates(drag.id);
    let b = Math.min(drag.bounds.right, Math.max(t, s.start+0.05));
    b = trySnap(b, cands);
    b = Math.min(drag.bounds.right, Math.max(b, s.start+0.05));
    s.end=b;
  }
  drawTimeline();
}

function handleUp(e){
  if(drag && drag.mode==='boxselect'){
    const movedPx = Math.abs((drag.currentX ?? drag.anchorX) - drag.anchorX);
    if(movedPx < 4){
      const hit = hitStrip(drag.anchorX);
      if(hit){
        if(selectedIds.has(hit.strip.id)) selectedIds.delete(hit.strip.id);
        else selectedIds.add(hit.strip.id);
        selectedId = [...selectedIds][selectedIds.size-1] ?? null;
      } else if(!boxSelectMode){
        selectedIds.clear(); selectedId = null;
      }
    } else {
      const t0 = Math.min(drag.anchorT, drag.currentT), t1 = Math.max(drag.anchorT, drag.currentT);
      const matched = strips.filter(s=> s.end>t0 && s.start<t1);
      matched.forEach(s=>selectedIds.add(s.id));
      if(matched.length) selectedId = matched[matched.length-1].id;
    }
    copyBtn.disabled = dupBtn.disabled = deleteBtnTop.disabled = playStripBtn.disabled = selectedIds.size===0;
    drag = null; tl.style.cursor='crosshair';
    refreshPanel(); drawTimeline();
    return;
  }
  if(drag && drag.mode==='create'){
    const s = strips.find(s=>s.id===drag.id);
    if(s && s.end-s.start<0.05){
      s.end=Math.min(drag.bounds.right, s.start+1.5);
    }
    if(s && s.end-s.start<0.05){
      strips = strips.filter(x=>x.id!==s.id);
      select(null);
      showToast('No room for a strip there \u2014 it overlaps an existing strip.');
    }
  }
  drag=null; tl.style.cursor='crosshair'; refreshPanel(); drawTimeline();
}

tl.addEventListener('mousedown', handleDown);
/* long-press = context menu, for stylus/touch users with no barrel button or right-click */
let longPressTimer = null;
let longPressStart = null;
function startLongPressWatch(e){
  cancelLongPressWatch();
  const {STRIP_Y, STRIP_H} = getLayout();
  const {x,y} = relPos(e);
  if(y<STRIP_Y-2||y>STRIP_Y+STRIP_H+2) return;
  const hit = hitStrip(x);
  if(!hit || hit.part!=='move') return; // only long-press the body, not while resizing an edge
  longPressStart = {x:e.clientX, y:e.clientY, id:hit.strip.id};
  longPressTimer = setTimeout(()=>{
    if(!longPressStart) return;
    select(longPressStart.id);
    openContextMenu(longPressStart.id, longPressStart.x, longPressStart.y);
    drag = null; // don't also start a move-drag once the menu opens
    longPressStart = null;
  }, 500);
}
function cancelLongPressWatch(moveEvent){
  if(moveEvent && longPressStart){
    const dx = moveEvent.clientX-longPressStart.x, dy = moveEvent.clientY-longPressStart.y;
    if(Math.sqrt(dx*dx+dy*dy) < 10) return; // small jitter is fine, don't cancel yet
  }
  clearTimeout(longPressTimer);
  longPressTimer = null;
  longPressStart = null;
}

tl.addEventListener('pointerdown', e=>{
  if(e.pointerType==='mouse') return;
  if(e.pointerType==='touch' && activeTouches.size>=2) return;
  e.preventDefault();
  try{ tl.setPointerCapture(e.pointerId); }catch(err){}
  startLongPressWatch(e);
  handleDown(e);
});
window.addEventListener('mousemove', handleMove);
window.addEventListener('pointermove', e=>{ if(e.pointerType==='mouse') return; e.preventDefault(); cancelLongPressWatch(e); handleMove(e); });
window.addEventListener('mouseup', handleUp);
window.addEventListener('pointerup', e=>{ if(e.pointerType==='mouse') return; cancelLongPressWatch(); e.preventDefault(); try{ tl.releasePointerCapture(e.pointerId); }catch(err){} handleUp(e); });

tl.addEventListener('wheel', e=>{
  if(!duration) return;
  e.preventDefault();
  const {x} = relPos(e);
  if(e.shiftKey || Math.abs(e.deltaX)>Math.abs(e.deltaY)){
    viewStart += (e.deltaX||e.deltaY)/pxPerSec;
    clampView();
  } else {
    zoomAt(x, e.deltaY<0 ? 1.15 : 1/1.15);
  }
  drawTimeline();
}, {passive:false});

/* right-click context menu */
tl.addEventListener('contextmenu', e=>{
  e.preventDefault();
  if(!duration) return;
  const {STRIP_Y, STRIP_H} = getLayout();
  const {x,y} = relPos(e);
  if(y<STRIP_Y-2||y>STRIP_Y+STRIP_H+2) return;
  const hit = hitStrip(x);
  if(!hit) return;
  select(hit.strip.id);
  openContextMenu(hit.strip.id, e.clientX, e.clientY);
});
function openContextMenu(id, clientX, clientY){
  const s = strips.find(s=>s.id===id); if(!s) return;
  ctxTargetId = id;
  const leaf = leafOf(s.theta, s.r);
  document.getElementById('ctxEmoLabel').textContent = `${leaf.word} \u00b7 ${(s.r*100).toFixed(0)}%`;
  document.getElementById('ctxEmoBreadcrumb').textContent = breadcrumbFor(s);

  ctxMenu.style.visibility='hidden';
  ctxMenu.style.display='block';
  ctxMenu.style.left='0px'; ctxMenu.style.top='0px';
  const mw = ctxMenu.offsetWidth, mh = ctxMenu.offsetHeight;

  let left = clientX;
  let top = clientY - mh - 10; // prefer opening upward, above the strip
  if(top < 8) top = clientY + 10; // not enough room above — fall back to below
  if(left + mw > window.innerWidth - 8) left = window.innerWidth - mw - 8;
  if(left < 8) left = 8;

  ctxMenu.style.left = left+'px';
  ctxMenu.style.top = top+'px';
  ctxMenu.style.visibility='visible';
}
document.addEventListener('click', ()=>{ ctxMenu.style.display='none'; });
document.getElementById('ctxPlay').addEventListener('click', ()=>{
  const s = strips.find(s=>s.id===ctxTargetId); if(!s) return;
  stripPlaying=s; video.currentTime=s.start; video.play();
});
document.getElementById('ctxDup').addEventListener('click', ()=>{ duplicateStrip(ctxTargetId); });
document.getElementById('ctxDelete').addEventListener('click', ()=>{
  saveStateForUndo();
  strips = strips.filter(s=>s.id!==ctxTargetId);
  if(selectedIds.has(ctxTargetId)){
    selectedIds.delete(ctxTargetId);
    if(selectedId===ctxTargetId) selectedId = [...selectedIds][0]||null;
  }
  if(selectedIds.size===0) select(null);
  drawTimeline();
});

/* ============ selection & panel ============ */
const panelEmpty=document.getElementById('panelEmpty');
const panelSelected=document.getElementById('panelSelected');
const emoLabel=document.getElementById('emoLabel');
const emoBreadcrumb=document.getElementById('emoBreadcrumb');
const emoSub=document.getElementById('emoSub');
const startInput=document.getElementById('startInput');
const endInput=document.getElementById('endInput');

function select(id){
  // id may be null or a number or an array of ids
  if(Array.isArray(id)){
    selectedIds = new Set(id);
    selectedId = id.length? id[0] : null;
  } else if(id==null){
    selectedIds.clear(); selectedId = null;
  } else {
    selectedIds = new Set([id]); selectedId = id;
  }
  const has = selectedIds.size>0;
  copyBtn.disabled = dupBtn.disabled = deleteBtnTop.disabled = playStripBtn.disabled = !has;
  refreshPanel(); drawTimeline();
}
function refreshPanel(){
  const s = strips.find(s=>s.id===selectedId) || strips.find(s=>selectedIds.has(s.id));
  if(!s){ panelEmpty.style.display='block'; panelSelected.style.display='none'; drawWheel(null); return; }
  panelEmpty.style.display='none'; panelSelected.style.display='block';
  startInput.value=s.start.toFixed(2); endInput.value=s.end.toFixed(2);
  updateReadout(s); drawWheel(s);
}
function updateReadout(s){
  const leaf = leafOf(s.theta, s.r);
  emoLabel.textContent = s.r>0 ? leaf.word : `${leaf.word} (neutral)`;
  emoLabel.style.color = leaf.core.color;
  emoBreadcrumb.textContent = breadcrumbFor(s);
  emoSub.textContent = `θ ${s.theta.toFixed(1)}° · r ${s.r.toFixed(2)} · intensity ${(s.r*100).toFixed(0)}%`;
}
startInput.addEventListener('change', ()=>{
  const s=strips.find(s=>s.id===selectedId); if(!s) return;
  const b = getBounds(s.id, s.start, s.end);
  let v=parseFloat(startInput.value); if(isNaN(v)) return;
  s.start=Math.max(b.left,Math.min(s.end-0.05,v)); drawTimeline();
});
endInput.addEventListener('change', ()=>{
  const s=strips.find(s=>s.id===selectedId); if(!s) return;
  const b = getBounds(s.id, s.start, s.end);
  let v=parseFloat(endInput.value); if(isNaN(v)) return;
  s.end=Math.min(b.right,Math.max(s.start+0.05,v)); drawTimeline();
});
document.getElementById('seekBtn').addEventListener('click', ()=>{
  const s=strips.find(s=>s.id===selectedId); if(s) video.currentTime=s.start;
});
function deleteSelected(){
  if(selectedIds.size===0) return;
  saveStateForUndo();
  strips = strips.filter(s=>!selectedIds.has(s.id));
  select(null); drawTimeline();
}
document.getElementById('deleteBtn').addEventListener('click', deleteSelected);
deleteBtnTop.addEventListener('click', deleteSelected);

addStripBtn.addEventListener('click', ()=>{
  const t=video.currentTime;
  if(strictlyInsideAnother(t, null)){
    showToast('Can\u2019t add a strip here \u2014 the playhead is inside an existing strip.');
    return;
  }
  saveStateForUndo();
  const id=nextId++;
  const b = getBounds(id, t, t);
  const end = Math.min(b.right, t+1.5);
  if(end-t < 0.05){ showToast('No room for a strip at the playhead.'); return; }
  strips.push({id,start:t,end,theta:0,r:0});
  select(id); drawTimeline();
});

function copySelected(){
  const s=strips.find(s=>s.id===selectedId) || strips.find(s=>selectedIds.has(s.id)); if(!s) return;
  clipboard={dur:s.end-s.start, theta:s.theta, r:s.r};
  pasteBtn.disabled=false;
}
function pasteAtPlayhead(){
  if(!clipboard) return;
  const t=video.currentTime;
  if(strictlyInsideAnother(t, null)){
    showToast('Can\u2019t paste here \u2014 the playhead is inside an existing strip.');
    return;
  }
  saveStateForUndo();
  const id=nextId++;
  const b = getBounds(id, t, t);
  const end = Math.min(b.right, t+clipboard.dur);
  if(end-t < 0.05){ showToast('No room to paste at the playhead.'); return; }
  strips.push({id,start:t,end,theta:clipboard.theta,r:clipboard.r});
  select(id); drawTimeline();
}
function duplicateStrip(id){
  const s = strips.find(s=>s.id===id); if(!s) return;
  const len = s.end-s.start;
  const b = getBounds(s.id, s.start, s.end);
  let start = s.end;
  if(start >= b.right-0.05){
    showToast('No room to duplicate this strip \u2014 it\u2019s boxed in by neighbours.');
    return;
  }
  saveStateForUndo();
  const end = Math.min(b.right, start+len);
  const newId = nextId++;
  strips.push({id:newId, start, end, theta:s.theta, r:s.r});
  select(newId); drawTimeline();
}
copyBtn.addEventListener('click', copySelected);
pasteBtn.addEventListener('click', pasteAtPlayhead);
dupBtn.addEventListener('click', ()=>{ if(selectedId!=null) duplicateStrip(selectedId); });

playStripBtn.addEventListener('click', ()=>{
  const s=strips.find(s=>s.id===selectedId); if(!s) return;
  stripPlaying=s; video.currentTime=s.start; video.play();
});

document.addEventListener('keydown', e=>{
  if(document.activeElement && document.activeElement.tagName==='INPUT') return;
  // global undo/redo
  if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='z'){
    e.preventDefault();
    if(e.shiftKey) redo(); else undo();
    return;
  }

  if(!duration) return;

  if(e.key===' '){
    e.preventDefault();
    if(video.paused) video.play(); else video.pause();
    return;
  }
  if(e.key==='ArrowLeft' || e.key==='ArrowRight'){
    e.preventDefault();
    video.pause();
    stripPlaying = null;
    const step = e.shiftKey ? 1 : 1/FPS;
    const dir = e.key==='ArrowLeft' ? -1 : 1;
    video.currentTime = Math.max(0, Math.min(duration, video.currentTime + dir*step));
    return;
  }
  if(e.key==='Home'){ e.preventDefault(); video.currentTime = 0; return; }
  if(e.key==='Escape'){
    selectedIds.clear(); selectedId=null;
    if(boxSelectMode){ boxSelectMode=false; boxSelectBtn.classList.remove('active'); }
    drag=null; refreshPanel(); drawTimeline();
    return;
  }
  if(e.key==='End'){ e.preventDefault(); video.currentTime = duration; return; }

  if((e.key==='Delete'||e.key==='Backspace') && selectedIds.size>0){ deleteSelected(); }
  if(e.ctrlKey && e.key.toLowerCase()==='c'){ copySelected(); }
  if(e.ctrlKey && e.key.toLowerCase()==='v'){ pasteAtPlayhead(); }
  if(e.ctrlKey && e.key.toLowerCase()==='d'){ e.preventDefault(); if(selectedIds.size>0) duplicateStrip([...selectedIds][0]); }
  if(e.key.toLowerCase()==='p' && !e.ctrlKey && selectedId!=null){ playStripBtn.click(); }
  if(e.key.toLowerCase()==='a' && !e.ctrlKey){ addStripBtn.click(); }
});

// Ctrl+A select all when pointer is over the timeline
document.addEventListener('keydown', e=>{
  if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='a' && pointerOverTimeline){
    e.preventDefault();
    if(strips.length===0) return;
    saveStateForUndo();
    select(strips.map(s=>s.id));
  }
});

/* ============ resizable sidebar / wheel ============ */
const resizer = document.getElementById('resizer');
let resizingSidebar = false;
function sidebarResizeStart(e){ resizingSidebar=true; document.body.style.cursor='col-resize'; e.preventDefault(); }
function sidebarResizeMove(e){
  if(!resizingSidebar) return;
  const newWidth = Math.max(260, Math.min(640, window.innerWidth - e.clientX));
  sidebarEl.style.width = newWidth+'px';
  layoutWheelCanvas();
  drawWheel(strips.find(s=>s.id===selectedId)||null);
}
function sidebarResizeEnd(){ if(resizingSidebar){ resizingSidebar=false; document.body.style.cursor=''; } }
resizer.addEventListener('mousedown', sidebarResizeStart);
resizer.addEventListener('pointerdown', e=>{ if(e.pointerType==='mouse') return; try{ resizer.setPointerCapture(e.pointerId); }catch(err){} sidebarResizeStart(e); });
window.addEventListener('mousemove', sidebarResizeMove);
window.addEventListener('pointermove', e=>{ if(e.pointerType==='mouse') return; if(resizingSidebar) e.preventDefault(); sidebarResizeMove(e); });
window.addEventListener('mouseup', sidebarResizeEnd);
window.addEventListener('pointerup', e=>{ if(e.pointerType==='mouse') return; try{ resizer.releasePointerCapture(e.pointerId); }catch(err){} sidebarResizeEnd(); });

/* ============ resizable media area / timeline split ============ */
const mediaWrapEl = document.querySelector('.media-wrap');
const resizerH = document.getElementById('resizerH');
let resizingMedia = false;
let mediaResizeStartY = 0, mediaResizeStartH = 0;
function mediaResizeStart(e){
  resizingMedia = true;
  mediaResizeStartY = e.clientY;
  mediaResizeStartH = mediaWrapEl.getBoundingClientRect().height;
  document.body.style.cursor='row-resize';
  e.preventDefault();
}
function mediaResizeMove(e){
  if(!resizingMedia) return;
  const delta = e.clientY - mediaResizeStartY; // drag down = taller media area
  const mainH = document.querySelector('.main').getBoundingClientRect().height;
  const minMedia = 140, minTimeline = 90;
  const maxMedia = mainH - resizerH.offsetHeight - minTimeline;
  const newH = Math.max(minMedia, Math.min(maxMedia, mediaResizeStartH + delta));
  mediaWrapEl.style.height = newH+'px';
  drawTimeline();
}
function mediaResizeEnd(){ if(resizingMedia){ resizingMedia=false; document.body.style.cursor=''; } }
resizerH.addEventListener('mousedown', mediaResizeStart);
resizerH.addEventListener('pointerdown', e=>{ if(e.pointerType==='mouse') return; try{ resizerH.setPointerCapture(e.pointerId); }catch(err){} mediaResizeStart(e); });
window.addEventListener('mousemove', mediaResizeMove);
window.addEventListener('pointermove', e=>{ if(e.pointerType==='mouse') return; if(resizingMedia) e.preventDefault(); mediaResizeMove(e); });
window.addEventListener('mouseup', mediaResizeEnd);
window.addEventListener('pointerup', e=>{ if(e.pointerType==='mouse') return; try{ resizerH.releasePointerCapture(e.pointerId); }catch(err){} mediaResizeEnd(); });

/* ============ emotion wheel: reference image + thin overlay ============ */
const wheelWrap=document.getElementById('wheelWrap');
const wheel=document.getElementById('wheel');
const wCtx=wheel.getContext('2d');
let W=380, CX=190, CY=190, MAXR=190;

function layoutWheelCanvas(){
  const size = wheelWrap.getBoundingClientRect().width || Math.max(220, Math.min(560, sidebarEl.clientWidth-32));
  const dpr = window.devicePixelRatio||1;
  wheel.width = size*dpr;
  wheel.height = size*dpr;
  wCtx.setTransform(dpr,0,0,dpr,0,0);
  W=size; CX=size/2; CY=size/2; MAXR=size/2;
}

function toRad(thetaTop){ return (thetaTop-90)*Math.PI/180; }

function drawWheel(strip){
  wCtx.clearRect(0,0,W,W);
  wCtx.fillStyle='#ffffff'; wCtx.strokeStyle='#c7cbd3';
  wCtx.beginPath(); wCtx.arc(CX,CY,4,0,Math.PI*2); wCtx.fill(); wCtx.stroke();

  if(strip){
    const rad=toRad(strip.theta);
    const px=CX+Math.cos(rad)*MAXR*strip.r, py=CY+Math.sin(rad)*MAXR*strip.r;
    wCtx.strokeStyle='#1a1c22'; wCtx.lineWidth=2.4;
    wCtx.beginPath(); wCtx.moveTo(CX,CY); wCtx.lineTo(px,py); wCtx.stroke();
    wCtx.fillStyle='#ffffff'; wCtx.beginPath(); wCtx.arc(px,py,7,0,Math.PI*2); wCtx.fill();
    wCtx.lineWidth=2.8; wCtx.strokeStyle=coreOf(strip.theta).color;
    wCtx.beginPath(); wCtx.arc(px,py,7,0,Math.PI*2); wCtx.stroke();
    wCtx.lineWidth=1; wCtx.strokeStyle='rgba(0,0,0,0.35)';
    wCtx.beginPath(); wCtx.arc(px,py,7,0,Math.PI*2); wCtx.stroke();
  }
}

/*
  Wheel click -> (theta, r) mapping, derived fresh from the live element rect
  on every call (see prior debugging notes: never trust cached size vars).
  theta=0 is the top of the image, increasing clockwise, matching how the
  reference PNG's sectors are laid out (Joy occupies 0°-45°, i.e. starts
  exactly at 12 o'clock and runs clockwise to the Joy/Trust boundary — the
  wheel's sector *boundaries* sit at multiples of 45°, not its sector
  *centers*, which is what coreIndex()/leafOf() now assume too).
*/
let wheelDragging=false;
function setFromWheel(clientX,clientY){
  const s=strips.find(s=>s.id===selectedId); if(!s) return;
  const rect=wheel.getBoundingClientRect();
  const cx=rect.width/2, cy=rect.height/2, maxr=Math.min(rect.width,rect.height)/2;
  const x=clientX-rect.left, y=clientY-rect.top;
  const dx=x-cx, dy=y-cy;
  let theta=Math.atan2(dx,-dy)*180/Math.PI; if(theta<0) theta+=360;
  const r=Math.max(0,Math.min(1, Math.sqrt(dx*dx+dy*dy)/maxr));
  s.theta=theta; s.r=r;
  updateReadout(s); drawWheel(s); drawTimeline();
}
wheel.style.touchAction = wheel.style.touchAction || 'none';
wheel.addEventListener('mousedown', e=>{ if(selectedId==null) return; wheelDragging=true; setFromWheel(e.clientX,e.clientY); });
wheel.addEventListener('pointerdown', e=>{ if(e.pointerType==='mouse' || selectedId==null) return; e.preventDefault(); try{ wheel.setPointerCapture(e.pointerId); }catch(err){} wheelDragging=true; setFromWheel(e.clientX,e.clientY); });
window.addEventListener('mousemove', e=>{ if(wheelDragging) setFromWheel(e.clientX,e.clientY); });
window.addEventListener('pointermove', e=>{ if(e.pointerType==='mouse' || !wheelDragging) return; e.preventDefault(); setFromWheel(e.clientX,e.clientY); });
window.addEventListener('mouseup', ()=>{ wheelDragging=false; });
window.addEventListener('pointerup', e=>{ if(e.pointerType==='mouse') return; wheelDragging=false; try{ wheel.releasePointerCapture(e.pointerId); }catch(err){} });

layoutWheelCanvas();
drawWheel(null);

/* ============ export / import ============ */
exportBtn.addEventListener('click', ()=>{
  const data={duration, strips:strips.map(({id,...r})=>r)};
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='emotion_annotations.json'; a.click();
});
importInput.addEventListener('change', e=>{
  const f=e.target.files[0]; if(!f) return;
  const reader=new FileReader();
  reader.onload=()=>{
    try{
      saveStateForUndo();
      const data=JSON.parse(reader.result);
      strips=(data.strips||[]).map(s=>({id:nextId++,start:s.start,end:s.end,theta:s.theta??0,r:s.r??0}));
      select(null); drawTimeline();
    }catch(err){ alert('Could not parse that JSON file.'); }
  };
  reader.readAsText(f);
});
