'use strict';
const $ = id => document.getElementById(id);
const canvas = $('map'), ctx = canvas.getContext('2d'), cache = new Map();
let maps = [], geometry = null, state = null, selected = 'auto', loadingCode = null, generation = 0;
// Presentation order only. Never reorder the executable's level table/IDs.
const PLAY_ORDER=['CR','GY1','CH','DC','GY2','SF','PG','PS','SV','AG','IA','EE','AC','PD','LA','CC','GG','HR','GS','EH','TD','ZL'];
function populateMapOptions() {
  const select=$('map-select');
  while(select.options.length>1) select.remove(1);
  PLAY_ORDER.forEach((code,index)=>{
    const map=maps.find(m=>m.code===code);if(!map)return;
    const option=document.createElement('option');option.value=code;
    option.textContent=`${String(index+1).padStart(2,'0')} - ${map.name}${code==='AC'?' (optional)':''}`;
    select.appendChild(option);
  });
  const heroes=maps.find(m=>m.code==='HH');
  if(heroes){const option=document.createElement('option');option.value='HH';option.textContent=`${heroes.name} (repeatable bonus)`;select.appendChild(option);}
}
let w = 1, h = 1, dpr = 1, cx = 0, cz = 0, scale = 1, follow = false, drag = null;
let lastReceived = 0, connected = true, displayMode = 'texture', showItems = true, chosenItem = null;
const terrainRenderer = new TerrainRenderer(()=>draw());
let showExits = true, chosenExit = -1, showObjects = true;
const danImage = new Image();
let danImageReady = false;
danImage.onload = () => { danImageReady = true; draw(); };
danImage.onerror = () => { danImageReady = false; draw(); };
danImage.src = '/dan.png';
const categories = {
  gold: ['#f4c76a', '$'], health: ['#7ed6df', '+'], rune: ['#c5a0f0', '♦'],
  chalice: ['#ffe29a', 'C'], equipment: ['#9ebbf4', 'E'], quest: ['#f2a7be', '?'], chest: ['#e2b188', '□'],
};
const statusLabels = {live:'LIVE',paused:'PAUSED',connecting:'CONNECTING',disconnected:'EMULATOR OFF',waiting_game:'WAITING FOR GAME',not_playing:'NOT IN LEVEL',loading:'LOADING',updating:'SAMPLING',multiple:'SELECT EMULATOR',unavailable:'RECONNECTING',error:'READER ERROR'};
let movementSample = null, movementDirection = null, lastMovementAt = 0, movementExpiryTimer = null;
function clearMovementDirection() {
  movementDirection=null;clearTimeout(movementExpiryTimer);movementExpiryTimer=null;
}
function trackMovement(sample, now) {
  const p=sample?.position;
  if (sample?.status!=='live' || sample.source==='snapshot' || !Array.isArray(p) ||
      p.length!==3 || !p.every(Number.isFinite) || !Number.isInteger(sample.frame)) {
    movementSample=null;clearMovementDirection();return;
  }
  const key=JSON.stringify([sample.epoch,sample.pid,sample.emulator,sample.level,sample.player_address,sample.state_address]);
  const previous=movementSample;
  movementSample={key,frame:sample.frame,position:p.slice(),at:now};
  if (!previous || previous.key!==key || now<previous.at || now-previous.at>500 || sample.frame<previous.frame) {
    clearMovementDirection();return;
  }
  const dx=p[0]-previous.position[0], dz=p[2]-previous.position[2], distance=Math.hypot(dx,dz);
  if (sample.frame===previous.frame) {
    if (distance) clearMovementDirection();
    return; // Repeated HTTP samples are not a new movement observation.
  }
  if (distance<1 || distance>1024) { clearMovementDirection();return; }
  movementDirection={x:dx/distance,y:-dz/distance};lastMovementAt=now;
  clearTimeout(movementExpiryTimer);
  movementExpiryTimer=setTimeout(()=>{clearMovementDirection();draw();},251);
}
function drawMovementArrow(x,y) {
  if (!movementDirection || state?.status!=='live' || Date.now()-lastMovementAt>250) return;
  ctx.save();ctx.translate(x,y);ctx.rotate(Math.atan2(movementDirection.y,movementDirection.x));
  const compact=x<48 || x>w-48 || y<48 || y>h-48;
  if (!compact) {
    ctx.lineCap='round';ctx.strokeStyle='#10170c';ctx.lineWidth=6;
    ctx.beginPath();ctx.moveTo(26,0);ctx.lineTo(39,0);ctx.stroke();
    ctx.strokeStyle='#c5ed72';ctx.lineWidth=3;ctx.stroke();
  }
  ctx.beginPath();ctx.moveTo(compact?22:46,0);ctx.lineTo(compact?18:36,compact?-4:-6);ctx.lineTo(compact?18:36,compact?4:6);ctx.closePath();
  ctx.fillStyle='#c5ed72';ctx.fill();ctx.strokeStyle='#10170c';ctx.lineWidth=2;ctx.stroke();ctx.restore();
}
function marker() {
  return connected && state && ['live','paused'].includes(state.status) && state.position && geometry &&
    state.level === geometry.table_index && Date.now() - lastReceived < 1500 ? state.position : null;
}
function setFollow(on) { follow = on; $('follow').setAttribute('aria-pressed', String(on)); }
function fit(resetFollow = true) {
  if (!geometry) return;
  const b = geometry.bounds;
  cx = (b[0][0]+b[0][1])/2; cz = (b[2][0]+b[2][1])/2;
  scale = Math.max(.001, Math.min((w-60)/Math.max(1,b[0][1]-b[0][0]), (h-60)/Math.max(1,b[2][1]-b[2][0])));
  if (resetFollow) setFollow(false);
  draw();
}
function resize() {
  const r = canvas.getBoundingClientRect(); w = r.width; h = r.height; dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr);
  if (geometry) fit(false); else draw();
}
function toScreen(x,z) { return [w/2+(x-cx)*scale, h/2-(z-cz)*scale]; }
function terrain(g) {
  const mode = displayMode === 'texture' ? 'colour' : displayMode;
  if (g.raster && g.raster.mode === mode && g.raster.objects === showObjects) return g.raster;
  const b = showObjects ? (g.scene_bounds || g.bounds) : g.bounds, dx = Math.max(1,b[0][1]-b[0][0]), dz = Math.max(1,b[2][1]-b[2][0]);
  const pixelsPerUnit = 2048/Math.max(dx,dz), image = document.createElement('canvas');
  image.width = Math.ceil(dx*pixelsPerUnit)+2; image.height = Math.ceil(dz*pixelsPerUnit)+2;
  const c = image.getContext('2d'), range = Math.max(1,b[1][1]-b[1][0]);
  for (const [prop,i] of sceneFaceOrder(g)) {
    if (prop && !showObjects) continue;
    const mesh=prop?g.object_mesh:g;
    const face = mesh.faces[i], colour = mesh.face_colours?.[i];
    if (mode === 'colour' && colour) {
      // Mild exposure lift for map readability; colour comes from the disc.
      c.fillStyle = `rgb(${colour.map(v=>Math.round(255*Math.pow(v/255,.8))).join(',')})`;
    } else {
      const height = face.reduce((sum,v)=>sum+mesh.vertices[v][1],0)/face.length;
      const shade = Math.round(47+36*(b[1][1]-height)/range);
      c.fillStyle = `rgb(${shade-8},${shade+5},${shade})`;
    }
    c.beginPath();
    face.forEach((v,j)=> { const p=mesh.vertices[v], x=1+(p[0]-b[0][0])*pixelsPerUnit, y=1+(b[2][1]-p[2])*pixelsPerUnit; if(j)c.lineTo(x,y);else c.moveTo(x,y); });
    c.closePath(); c.fill();
    if (mode === 'height') { c.strokeStyle='#91a28c44'; c.lineWidth=.5; c.stroke(); }
  }
  g.raster = {image, mode, objects:showObjects, pixelsPerUnit, left:b[0][0]-1/pixelsPerUnit, top:b[2][1]+1/pixelsPerUnit};
  return g.raster;
}
function drawItems() {
  if (!showItems) return;
  ctx.font = 'bold 10px ui-monospace, monospace'; ctx.textAlign='center'; ctx.textBaseline='middle';
  for (const item of geometry.items || []) {
    const [x,y] = toScreen(item.position[0],item.position[2]);
    if (x < -12 || x > w+12 || y < -12 || y > h+12) continue;
    const [colour,symbol] = categories[item.category] || ['#ccc','?'];
    ctx.fillStyle='#101612'; ctx.strokeStyle=colour; ctx.lineWidth=1.5;
    ctx.beginPath(); ctx.arc(x,y,7,0,Math.PI*2); ctx.fill(); ctx.stroke();
    ctx.fillStyle=colour; ctx.fillText(symbol,x,y+.5);
    if (item.record === chosenItem) { ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.beginPath();ctx.arc(x,y,11,0,Math.PI*2);ctx.stroke(); }
  }
}
function exitText(zone, index) {
  return `Exit ${index+1}/${geometry.exits.length} · ${zone.script_source?'scripted ':''}event ${zone.event} · X ${zone.centre[0]}, Z ${zone.centre[2]} · collision Y ${zone.height_range[0]}…${zone.height_range[1]} (16-bit) · static volume; gates/scripts may apply`;
}
function populateExits() {
  chosenExit=-1;
  const exits=geometry?.exits || [];
  $('find-exit').disabled=!showExits||!exits.length;
  $('find-exit').textContent=exits.length>1?'Find / next exit':'Find exit';
  $('exit-detail').textContent=!geometry || !Array.isArray(geometry.exits)?'Exit data unavailable':exits.length?`${exits.length} mapped exit volume${exits.length===1?'':'s'} · static footprint; height/gates matter, not live activation`:'No verified exit volume mapped here — other or scripted exits may still exist.';
}
function drawExits() {
  if(!showExits)return;
  ctx.save();ctx.strokeStyle='#ffad85';ctx.fillStyle='#ff986526';ctx.lineWidth=2;ctx.setLineDash([5,3]);
  for(const [index,zone] of (geometry.exits || []).entries()) {
    for(const poly of zone.footprints) {
      ctx.beginPath();poly.forEach((p,i)=>{const [x,y]=toScreen(p[0],p[1]);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});
      ctx.closePath();ctx.fill();ctx.stroke();
    }
    const [x,y]=toScreen(zone.centre[0],zone.centre[2]);
    if(x<0||x>w||y<0||y>h)continue;
    ctx.save();ctx.setLineDash([]);ctx.beginPath();ctx.moveTo(x-5,y);ctx.lineTo(x+5,y);ctx.moveTo(x,y-5);ctx.lineTo(x,y+5);ctx.stroke();
    ctx.font='bold 11px ui-monospace,monospace';ctx.textAlign='left';ctx.textBaseline='middle';
    const label=geometry.exits.length>1?`EXIT ${index+1}`:'EXIT';
    ctx.fillStyle='#17120ee8';ctx.fillRect(x+8,y-9,ctx.measureText(label).width+8,18);
    ctx.fillStyle='#ffad85';ctx.fillText(label,x+12,y);ctx.restore();
  }
  ctx.restore();
}
function findExit() {
  const exits=geometry?.exits || [];
  if(!showExits||!exits.length)return;
  chosenExit=(chosenExit+1)%exits.length;
  const zone=exits[chosenExit], points=zone.footprints.flat();
  const xs=points.map(p=>p[0]),zs=points.map(p=>p[1]);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minZ=Math.min(...zs),maxZ=Math.max(...zs);
  setFollow(false);cx=(minX+maxX)/2;cz=(minZ+maxZ)/2;
  scale=Math.max(.001,Math.min(.5,Math.max(1,w-100)/Math.max(1,maxX-minX),Math.max(1,h-100)/Math.max(1,maxZ-minZ)));
  $('exit-detail').textContent=exitText(zone,chosenExit);draw();
}
function exitAt(px,py) {
  if(!showExits || !geometry)return null;
  const x=cx+(px-w/2)/scale,z=cz-(py-h/2)/scale;
  for(const [index,zone] of (geometry.exits || []).entries()) {
    const point=toScreen(zone.centre[0],zone.centre[2]);
    if(Math.hypot(point[0]-px,point[1]-py)<10)return {zone,index};
    for(const poly of zone.footprints) {
      let inside=false;
      for(let i=0,j=poly.length-1;i<poly.length;j=i++) {
        const a=poly[i],b=poly[j];
        if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])inside=!inside;
      }
      if(inside)return {zone,index};
    }
  }
  return null;
}
function drawEdgeOnFaces(g) {
  const bounds=showObjects?(g.scene_bounds||g.bounds):g.bounds, range=Math.max(1,bounds[1][1]-bounds[1][0]);
  for(const [prop,i] of sceneFaceOrder(g)) {
    if(prop&&!showObjects)continue;
    const mesh=prop?g.object_mesh:g, offsets=mesh.edge_on_faces?.[i];if(!offsets)continue;
    const face=mesh.faces[i],colour=mesh.face_colours[i];
    if(displayMode!=='height'&&colour)ctx.fillStyle=`rgb(${colour.map(v=>Math.round(255*Math.pow(v/255,.8))).join(',')})`;
    else {const y=face.reduce((sum,v)=>sum+mesh.vertices[v][1],0)/face.length,s=Math.round(47+36*(bounds[1][1]-y)/range);ctx.fillStyle=`rgb(${s-8},${s+5},${s})`;}
    ctx.beginPath();face.forEach((v,j)=>{const p=mesh.vertices[v],[x,y]=toScreen(p[0],p[2]),o=offsets[j];if(j)ctx.lineTo(x+o[0],y-o[1]);else ctx.moveTo(x+o[0],y-o[1]);});ctx.closePath();ctx.fill();
  }
  for(const proxy of (g.fence_proxies||[]).slice().sort((a,b)=>b.ends[0][1]-a.ends[0][1])) {
    if(proxy.width*scale>=2)continue;
    const [a,b]=proxy.ends,[ax,ay]=toScreen(a[0],a[2]),[bx,by]=toScreen(b[0],b[2]),dx=bx-ax,dy=by-ay,length=Math.hypot(dx,dy);if(!length)continue;
    const nx=-dy/length,ny=dx/length;
    if(displayMode!=='height')ctx.fillStyle=`rgb(${g.face_colours[proxy.face].map(v=>Math.round(255*Math.pow(v/255,.8))).join(',')})`;
    else {const s=Math.round(47+36*(bounds[1][1]-a[1])/range);ctx.fillStyle=`rgb(${s-8},${s+5},${s})`;}
    ctx.beginPath();ctx.moveTo(ax-nx,ay-ny);ctx.lineTo(bx-nx,by-ny);ctx.lineTo(bx+nx,by+ny);ctx.lineTo(ax+nx,ay+ny);ctx.closePath();ctx.fill();
  }
}
function draw() {
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,w,h);
  const p = marker(); if (follow && p) { cx=p[0]; cz=p[2]; }
  if (!geometry) return;
  const detailed = displayMode === 'texture' && terrainRenderer.render(geometry,cx,cz,scale,w,h,dpr,showObjects);
  ctx.imageSmoothingEnabled = true;
  if(detailed) ctx.drawImage(detailed,0,0,w,h);
  else {
    const r = terrain(geometry), [left,top] = toScreen(r.left,r.top);
    ctx.drawImage(r.image,left,top,r.image.width/r.pixelsPerUnit*scale,r.image.height/r.pixelsPerUnit*scale);
    drawEdgeOnFaces(geometry);
  }
  $('render-note').textContent = displayMode === 'texture' ? (detailed ? 'Original PS1 textures · smooth shading' : `Simple colours · ${terrainRenderer.reason || geometry.textureError || 'texture data unavailable'}`) : ''; 
  drawExits();drawItems();
  // Dan is always drawn last and remains visually distinct from static spawns.
  if (p) {
    let [x,y] = toScreen(p[0],p[2]); const margin=24, outside=x<margin||x>w-margin||y<margin||y>h-margin, tx=x, ty=y;
    x=Math.max(margin,Math.min(w-margin,x)); y=Math.max(margin,Math.min(h-margin,y));
    drawMovementArrow(x,y);
    ctx.save();
    ctx.fillStyle='#10170cdd';ctx.strokeStyle='#c5ed72';ctx.lineWidth=1.5;
    ctx.beginPath();ctx.arc(x,y,16,0,Math.PI*2);ctx.fill();ctx.stroke();
    if (danImageReady) {
      const width=28, height=width*danImage.naturalHeight/danImage.naturalWidth;
      ctx.drawImage(danImage,x-width/2,y-height/2,width,height);
    } else {
      // Keep tracking visible while the optional portrait loads or fails.
      ctx.fillStyle='#c5ed72';ctx.beginPath();ctx.arc(x,y,6,0,Math.PI*2);ctx.fill();
    }
    if (outside) { ctx.fillStyle='#c5ed72';ctx.translate(x,y);ctx.rotate(Math.atan2(ty-h/2,tx-w/2));ctx.beginPath();ctx.moveTo(22,0);ctx.lineTo(16,-5);ctx.lineTo(16,5);ctx.closePath();ctx.fill(); }
    ctx.restore();
  }
  $('scale').textContent=`80 px ≈ ${Math.max(1,Math.round(80/scale)).toLocaleString()} units`;
}
function itemText(item) { return `${item.name} · X ${item.position[0]}, Z ${item.position[2]}, Y ${item.position[1]} · static spawn, availability unknown`; }
function populateItems() {
  chosenItem=null; canvas.title=''; $('item-detail').textContent='Static spawns — includes collected, hidden or conditional items. No dropped-item tracking.';
  const select=$('item-locate'), items=geometry?.items || []; select.replaceChildren();
  const first=document.createElement('option');first.value='';first.textContent=items.length?`Find an item (${items.length} spawns)`:'No mapped item spawns';select.append(first);
  for (const item of items) { const option=document.createElement('option');option.value=String(item.record);option.textContent=`${item.name} · #${item.id}`;select.append(option); }
  select.disabled=!showItems||!items.length;
}
function populateObjects() {
  const count=geometry?.objects?.length || 0;
  $('show-objects').disabled=!count;
  $('object-detail').textContent=geometry?.scene_version
    ? `${count} static props · gates and visibility are not live. ${geometry.object_omissions.length} other entities omitted.`
    : 'Static prop data unavailable.';
  $('object-detail').title=geometry?.object_source || '';
}
async function loadMap(info) {
  if (!info) return;
  if (geometry?.code===info.code) { if(loadingCode){++generation;loadingCode=null;$('empty').hidden=true;}return; }
  if (loadingCode===info.code) return;
  const id=++generation;loadingCode=info.code;$('empty').hidden=false;$('empty').textContent='Loading '+info.name+'…';
  try {
    let g=cache.get(info.code);
    if (!g) {
      const response=await fetch('/maps/'+info.code+'.json');if(!response.ok)throw Error('Map not found');g=await response.json();
      g.faceOrder=g.faces.map((_,i)=>i).sort((a,b)=>g.faces[b].reduce((s,i)=>s+g.vertices[i][1],0)/g.faces[b].length-g.faces[a].reduce((s,i)=>s+g.vertices[i][1],0)/g.faces[a].length);
      cache.set(info.code,g);
    }
    let image=null;
    g.textureError='';
    if(!terrainRenderer.reason) {
      try { image=await decodeTerrainAtlas(g); }
      catch(error) { g.textureError=error.message; }
    }
    if(id!==generation)return;
    terrainRenderer.setMap(g,image);
    if(geometry && geometry!==g)geometry.raster=null; // Keep only one large raster resident.
    geometry=g;$('level-name').textContent=info.name;$('empty').hidden=true;populateItems();populateExits();populateObjects();fit(false);
  } catch(e) { if(id===generation){if(geometry)geometry.raster=null;terrainRenderer.clear();geometry=null;$('render-note').textContent='';populateItems();populateExits();populateObjects();$('empty').hidden=false;$('empty').textContent='Could not load map: '+e.message;draw();} }
  finally { if(id===generation)loadingCode=null; }
}
function choose() {
  let info;
  if(selected==='auto') { info=maps.find(m=>m.table_index===state?.level&&['live','paused','loading'].includes(state?.status));if(!info&&!geometry)info=maps.find(m=>m.code==='CR'); }
  else info=maps.find(m=>m.code===selected);
  if(info)loadMap(info);
}
function update() {
  const p=marker();$('connection').textContent=connected?(state?.source==='snapshot'?'SNAPSHOT':statusLabels[state?.status]||'CONNECTING'):'CONNECTION LOST';
  $('connection').classList.toggle('live',connected&&state?.status==='live'&&state?.source!=='snapshot');
  $('recorded').hidden=state?.source!=='snapshot';$('x').textContent=p?p[0]:'—';$('y').textContent=p?p[1]:'—';$('z').textContent=p?p[2]:'—';
  let message=connected?(state?.message||'Connecting…'):'Map server disconnected. No live position.';
  if(connected&&state?.position&&geometry&&state.level!==geometry.table_index)message='Map preview — this is not Dan’s current level.';
  if(p&&(p[0]<geometry.bounds[0][0]||p[0]>geometry.bounds[0][1]||p[2]<geometry.bounds[2][0]||p[2]>geometry.bounds[2][1]))message='Outside map geometry · tracking continues. Use Follow Dan to centre.';
  const emulatorName={duckstation:'DuckStation','duckstation-gdb':'DuckStation (GDB)',redux:'PCSX-Redux',bizhawk:'BizHawk (Lua bridge)'}[state?.emulator];
  if(connected&&emulatorName)message=emulatorName+' · '+message;
  $('message').textContent=message;draw();
}
async function poll() {
  try { const response=await fetch('/api/state',{signal:AbortSignal.timeout(1500)});if(!response.ok)throw Error('Reader unavailable');state=await response.json();lastReceived=Date.now();connected=true;trackMovement(state,lastReceived);choose(); }
  catch { connected=false;trackMovement(null,Date.now()); }
  update();setTimeout(poll,50);
}
function zoom(factor,px=w/2,py=h/2) {
  const wx=cx+(px-w/2)/scale,wz=cz-(py-h/2)/scale;scale=Math.max(.001,Math.min(5,scale*factor));cx=wx-(px-w/2)/scale;cz=wz+(py-h/2)/scale;draw();
}
$('map-select').addEventListener('change',e=>{selected=e.target.value;choose();update();});
$('fit').addEventListener('click',()=>fit());$('follow').addEventListener('click',()=>{setFollow(!follow);draw();});
$('zoom-in').addEventListener('click',()=>zoom(1.5));$('zoom-out').addEventListener('click',()=>zoom(1/1.5));
$('map-style').addEventListener('change',e=>{displayMode=e.target.value;draw();});
$('find-exit').addEventListener('click',findExit);
$('show-objects').addEventListener('change',e=>{showObjects=e.target.checked;draw();});
$('show-exits').addEventListener('change',e=>{showExits=e.target.checked;$('find-exit').disabled=!showExits||!geometry?.exits?.length;canvas.title='';draw();});
$('show-items').addEventListener('change',e=>{showItems=e.target.checked;$('item-locate').disabled=!showItems||!geometry?.items?.length;canvas.title='';draw();});
$('item-locate').addEventListener('change',e=>{
  const item=e.target.value===''?null:geometry?.items?.find(i=>i.record===Number(e.target.value));chosenItem=item?.record??null;
  if(item){setFollow(false);cx=item.position[0];cz=item.position[2];scale=Math.max(scale,.12);$('item-detail').textContent=itemText(item);}
  else $('item-detail').textContent='Static spawns — includes collected, hidden or conditional items. No dropped-item tracking.';
  draw();
});
canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.001),e.clientX-r.left,e.clientY-r.top);},{passive:false});
canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,cx,cz};setFollow(false);canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{
  if(drag){cx=drag.cx-(e.clientX-drag.x)/scale;cz=drag.cz+(e.clientY-drag.y)/scale;draw();return;}
  const r=canvas.getBoundingClientRect(), x=e.clientX-r.left,y=e.clientY-r.top;
  const hit=showItems&&geometry?.items?.find(item=>{const p=toScreen(item.position[0],item.position[2]);return Math.hypot(p[0]-x,p[1]-y)<10;});
  const exit=exitAt(x,y);
  canvas.title=hit?itemText(hit):exit?exitText(exit.zone,exit.index):'';
});
canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',()=>drag=null);
window.addEventListener('keydown',e=>{if(e.key.toLowerCase()==='f'&&!['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName))fit();});
new ResizeObserver(resize).observe($('viewport'));
(async()=>{
  try { const response=await fetch('/api/maps');if(!response.ok)throw Error('Map index unavailable');maps=(await response.json()).maps;
    populateMapOptions();choose();poll();
  } catch(e){$('empty').textContent=e.message;$('message').textContent='Run extract_maps.py to prepare your disc’s map data.';}
})();
