'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');

function fixture(search = '') {
  const nodes = new Map(), classes = new Set(), opened = [];
  const context = new Proxy({}, {get: (o, k) => o[k] ?? (() => {})});
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, {
      hidden: false, listeners: {}, options: [],
      getContext: () => context, setAttribute() {}, setPointerCapture() {},
      getBoundingClientRect: () => ({left:0, top:0, width:800, height:600}),
      addEventListener(event, fn) { this.listeners[event] = fn; },
    });
    return nodes.get(id);
  }
  let focused = 0, blocked = false, now = 1000, frameId = 0;
  const frames = new Map(), motionPreference = {matches:false};
  const sandbox = {
    URL, URLSearchParams, AbortSignal,
    Date: {now: () => now}, performance: {now: () => now},
    requestAnimationFrame(fn) { const id = ++frameId; frames.set(id, fn); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
    document: {getElementById: node, body: {classList: {add: name => classes.add(name)}}},
    window: {
      location: {search, href: 'http://127.0.0.1:8765/' + search}, addEventListener() {},
      matchMedia: () => motionPreference,
      open(...args) { opened.push(args); return blocked ? null : {focus() { focused++; }}; },
    },
    Image: class {}, ResizeObserver: class {observe() {}},
    TerrainRenderer: class {render() {return {}; }}, MovementTracker: class {directionAt() {return null; }},
    fetch: () => new Promise(() => {}),
  };
  vm.createContext(sandbox);
  const run = code => vm.runInContext(code, sandbox);
  run(fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8'));
  return {run, node, classes, opened, focused: () => focused, block: value => blocked = value,
    frames, motionPreference,
    advance(ms) { now += ms; const pending = [...frames.values()]; frames.clear(); pending.forEach(fn => fn(now)); },
  };
}

function cameraScene(f) {
  f.run(`w=800;h=600;scale=1;connected=true;
    geometry={code:'CR',table_index:0,bounds:[[-10000,10000],[0,10],[-10000,10000]],items:[],exits:[]};
    state={status:'live',source:'live',level:0,frame:1,epoch:1,position:[0,0,0]};
    lastReceived=Date.now();setFollow(true);draw();`);
}

test('Follow Dan eases the camera in both windows without smoothing his reported marker', () => {
  for (const search of ['', '?view=map&follow=1']) {
    const f = fixture(search); cameraScene(f);
    f.advance(50);
    f.run('state={...state,frame:2,position:[100,0,0]};lastReceived=Date.now();draw()');
    assert.equal(f.run('marker()[0]'), 100);
    f.advance(16);
    assert.ok(f.run('cx > 0 && cx < 100'), 'camera should catch up rather than jump to each sample');
    assert.equal(f.frames.size, 1, 'only one animation may be queued');
    for (let i=0; i<50; i++) f.advance(16);
    assert.equal(f.run('cx'), 100);
    assert.equal(f.frames.size, 0, 'stationary camera must stop animating');
  }
});

function moveCamera(f, x=100, z=0) {
  f.advance(50);
  f.run(`state={...state,frame:state.frame+1,position:[${x},0,${z}]};lastReceived=Date.now();draw()`);
}

test('easing is time-based, not refresh rate or number of redraws', () => {
  const results=[];
  for (const steps of [3,6,12]) {
    const f=fixture();cameraScene(f);moveCamera(f);
    for(let i=0;i<steps;i++) f.advance(100/steps);
    results.push(f.run('cx'));
    const before=f.run('cx');
    f.run('draw();draw();draw()');
    assert.equal(f.run('cx'),before,'extra paints without elapsed time must not speed up the camera');
  }
  assert.ok(results.every(x=>x>60&&x<75),'camera should be roughly two-thirds caught up after 100 ms');
  assert.ok(Math.max(...results)-Math.min(...results)<1e-8);
});

test('teleports, session changes, frame rewind, map changes and sample gaps snap immediately', () => {
  for (const change of [
    'state.position=[5000,0,5000]', 'state.epoch++', 'state.pid=7',
    "state.emulator='bizhawk'", "state.player_address='new'", "state.state_address='new'",
    'state.frame=0', 'state.level=1;geometry={...geometry,table_index:1}',
    'geometry={...geometry}',
  ]) {
    const f=fixture();cameraScene(f);moveCamera(f);f.advance(16);
    assert.ok(f.run('cx<100'));
    f.run(`${change};draw()`);
    assert.equal(f.run('cx'),f.run('state.position[0]'),change);
    assert.equal(f.run('cz'),f.run('state.position[2]'),change);
    assert.equal(f.frames.size,0,change);
  }
  const f=fixture();cameraScene(f);moveCamera(f);f.advance(16);f.advance(600);
  f.run('state.position=[200,0,0];lastReceived=Date.now();draw()');
  assert.equal(f.run('cx'),200);
  assert.equal(f.frames.size,0);
});

test('pause, snapshots and reduced motion snap without animation', () => {
  for(const mode of ['paused','snapshot','reduced']) {
    const f=fixture();cameraScene(f);moveCamera(f);f.advance(16);
    if(mode==='reduced') f.motionPreference.matches=true;
    else f.run(mode==='paused'?"state.status='paused'":"state.source='snapshot'");
    f.run('draw()');
    assert.equal(f.run('cx'),100);
    assert.equal(f.frames.size,0);
  }
});

test('disconnect, stale position and preview mismatch stop animation; reconnect snaps', () => {
  for(const change of ['connected=false','lastReceived=Date.now()-1600','geometry.table_index=99']) {
    const f=fixture();cameraScene(f);moveCamera(f);f.advance(16);
    const before=f.run('cx');
    f.run(`${change};draw()`);
    assert.equal(f.run('cx'),before);
    assert.equal(f.frames.size,0);
    f.run('connected=true;lastReceived=Date.now();geometry.table_index=0;state.position=[200,0,0];draw()');
    assert.equal(f.run('cx'),200);
  }
});

test('dragging cancels camera motion, zoom still works, and F fits with follow off', () => {
  for(const search of ['', '?view=map&follow=1']) {
    const f=fixture(search);cameraScene(f);moveCamera(f);f.advance(16);
    const before=f.run('cx');
    f.node('map').listeners.pointerdown({clientX:100,clientY:100,pointerId:1});
    assert.equal(f.frames.size,0);
    assert.equal(f.run('follow'),false);
    f.node('map').listeners.pointermove({clientX:120,clientY:110});
    assert.equal(f.run('cx'),before-20);
    f.node('map').listeners.pointerup();
    const scale=f.run('scale');
    f.node('map').listeners.wheel({deltaY:-100,clientX:400,clientY:300,preventDefault(){}});
    assert.ok(f.run('scale')>scale);
    f.run('setFollow(true);draw()');
    assert.equal(f.run('cx'),100,'re-enabling follow should recenter immediately');
    f.run('fit()');
    assert.equal(f.run('follow'),false);
    assert.equal(f.run('cx'),0);
    assert.equal(f.frames.size,0);
  }
});

test('zooming while following does not pull the camera toward the mouse; manual zoom stays pointer-anchored', () => {
  for(const search of ['', '?view=map&follow=1']) {
    const f=fixture(search);cameraScene(f);moveCamera(f);f.advance(16);
    const beforeX=f.run('cx'),beforeZ=f.run('cz'),beforeScale=f.run('scale');
    f.run('zoom(3,0,0)');
    assert.equal(f.run('cx'),beforeX,'follow-mode zoom must preserve the tracked world centre');
    assert.equal(f.run('cz'),beforeZ);
    assert.equal(f.run('scale'),beforeScale*3);
    assert.equal(f.run('follow'),true);
    f.run('setFollow(false)');
    const worldX=f.run('cx-w/2/scale'),worldZ=f.run('cz+h/2/scale');
    f.run('zoom(2,0,0)');
    assert.ok(Math.abs(f.run('cx-w/2/scale')-worldX)<1e-10);
    assert.ok(Math.abs(f.run('cz+h/2/scale')-worldZ)<1e-10);
  }
});

test('normal page keeps controls and the button opens a named same-origin map window', () => {
  const f = fixture('?unrelated=value');
  assert.equal(f.classes.has('map-only'), false);
  f.node('popout').listeners.click();
  const [href, name, features] = f.opened[0], url = new URL(href);
  assert.equal(url.origin, 'http://127.0.0.1:8765');
  assert.equal(url.pathname, '/');
  assert.equal(url.searchParams.get('view'), 'map');
  assert.equal(url.searchParams.get('level'), 'auto');
  assert.equal(url.searchParams.has('unrelated'), false);
  assert.equal(name, 'medievil-map');
  assert.match(features, /popup/);
  assert.match(features, /resizable=yes/);
  assert.equal(f.focused(), 1);
  assert.equal(f.node('popout-status').hidden, true);
});

test('pop-out copies level, terrain, overlays and follow, not just defaults', () => {
  const f = fixture();
  f.run("selected='GY1';displayMode='height';showItems=false;showObjects=false;showExits=false;follow=true");
  f.node('popout').listeners.click();
  const url = new URL(f.opened[0][0]);
  assert.deepEqual(Object.fromEntries(url.searchParams), {
    view: 'map', level: 'GY1', terrain: 'height', items: '0', objects: '0', exits: '0', follow: '1',
  });
  const child = fixture(url.search);
  assert.equal(child.classes.has('map-only'), true);
  assert.equal(child.run('selected'), 'GY1');
  assert.equal(child.run('displayMode'), 'height');
  for (const key of ['showItems', 'showObjects', 'showExits']) assert.equal(child.run(key), false);
  assert.equal(child.run('follow'), true);
  assert.equal(child.node('map-style').value, 'height');
  assert.equal(child.node('show-items').checked, false);
});

test('blocked popup reports an actionable status and a successful retry clears it', () => {
  const f = fixture();
  f.block(true); f.node('popout').listeners.click();
  assert.equal(f.node('popout-status').hidden, false);
  assert.match(f.node('popout-status').textContent, /Allow pop-ups/);
  assert.equal(f.focused(), 0);
  f.block(false); f.node('popout').listeners.click();
  assert.equal(f.node('popout-status').hidden, true);
  assert.equal(f.node('popout-status').textContent, '');
  assert.equal(f.opened[0][1], f.opened[1][1]);
});

test('map-only hover hides item and exit details while normal-window tooltips remain', () => {
  for (const type of ['item', 'exit']) {
    for (const mapOnly of [false, true]) {
      const f = fixture(mapOnly ? '?view=map' : '');
      f.run(`w=800;h=600;cx=0;cz=0;scale=1;
        geometry={items:[],exits:[]};`);
      if (type === 'item') f.run("geometry.items=[{name:'Gold',position:[0,0,0]}]");
      else f.run("geometry.exits=[{event:1,centre:[0,0,0],height_range:[0,10],footprints:[]}]");
      f.node('map').title = '';
      f.node('map').listeners.pointermove({clientX:400, clientY:300});
      if (mapOnly) assert.equal(f.node('map').title, '');
      else assert.match(f.node('map').title, /X 0, Z 0/);
    }
  }
});

test('map-only links work without an opener and reject unknown terrain values', () => {
  const f = fixture('?view=map&terrain=invalid');
  assert.equal(f.classes.has('map-only'), true);
  assert.equal(f.run('displayMode'), 'texture');
  assert.equal(f.run('selected'), 'auto');
  assert.equal(f.run('showItems && showObjects && showExits'), true);
  assert.equal(f.run('follow'), false);
});
