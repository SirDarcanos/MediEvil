'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const calls=[];const ctx=new Proxy({}, {get:(o,k)=>o[k]??((...args)=>calls.push([k,...args]))});
const node={getContext:()=>ctx,addEventListener(){},setAttribute(){},options:[],classList:{toggle(){}},getBoundingClientRect:()=>({width:800,height:600})};
let now=1000,timerId=0;const timers=new Map();
function advance(t){now=t;for(const [id,timer]of [...timers])if(timer.at<=now){timers.delete(id);timer.fn();}}
const sandbox={document:{getElementById:()=>node},Image:class{},TerrainRenderer:class{},ResizeObserver:class{observe(){}},window:{addEventListener(){}},fetch:()=>new Promise(()=>{}),Date:{now:()=>now},setTimeout(fn,delay){const id=++timerId;timers.set(id,{fn,at:now+delay});return id;},clearTimeout(id){timers.delete(id);},AbortSignal};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(__dirname,'app.js'),'utf8'),sandbox);
const run=s=>vm.runInContext(s,sandbox);
const sample=(frame,position,extra={})=>({status:'live',source:'live',frame,position,epoch:1,level:16,pid:9,player_address:'0x800f0000',...extra});
function track(s,t=now){now=t;sandbox.input=s;sandbox.time=t;run('trackMovement(input,time)');}
function direction(){return JSON.parse(run('JSON.stringify(movementDirection)'));}
function reset(){track(null);now=1000;calls.length=0;timers.clear();run('w=800;h=600;geometry=null;');}
function scene(s){sandbox.input=s;run("state=input;lastReceived=Date.now();connected=true;cx=0;cz=0;scale=1;geometry={table_index:16,bounds:[[-10000,10000],[-100,100],[-10000,10000]],items:[],exits:[]};terrainRenderer.render=()=>({});");}
test('cardinal and diagonal directions use actual X/Z movement, with +Z upward',()=>{
 for(const [p,want]of[[[10,0,0],[1,0]],[[-10,0,0],[-1,0]],[[0,0,10],[0,-1]],[[0,0,-10],[0,1]],[[10,0,10],[Math.SQRT1_2,-Math.SQRT1_2]]]){
  reset();track(sample(1,[0,0,0]));track(sample(2,p),1050);const d=direction();assert.ok(Math.abs(d.x-want[0])<1e-12);assert.ok(Math.abs(d.y-want[1])<1e-12);
 }
});
test('new stationary or vertical-only frame clears movement',()=>{
 for(const p of[[10,0,0],[10,-50,0]]){reset();track(sample(1,[0,0,0]));track(sample(2,[10,0,0]),1050);track(sample(3,p),1100);assert.equal(direction(),null);}
});
test('duplicate frames retain direction briefly, but drawing expires',()=>{
 reset();track(sample(1,[0,0,0]));track(sample(2,[10,0,0]),1050);track(sample(2,[10,0,0]),1100);assert.equal(direction().x,1);
 run("state={status:'live'}");now=1200;run('drawMovementArrow(100,100)');assert.ok(calls.some(c=>c[0]==='lineTo'&&c[1]===39));calls.length=0;now=1400;run('drawMovementArrow(100,100)');assert.equal(calls.length,0);
});
test('paused, disconnected, recorded and invalid samples clear history',()=>{
 for(const bad of[null,sample(2,[1,0,0],{status:'paused'}),sample(2,[1,0,0],{source:'snapshot'}),sample(2,[NaN,0,0]),sample(2,[1,0]),sample(2,[1,0,0],{frame:null})]){
  reset();track(sample(1,[0,0,0]));track(sample(2,[10,0,0]),1050);track(bad,1100);assert.equal(direction(),null);track(sample(3,[20,0,0]),1150);assert.equal(direction(),null);
 }
});
test('painted arrow clears automatically while the next HTTP fetch is unresolved',()=>{
 reset();track(sample(1,[0,0,0]));const s=sample(2,[10,0,0]);track(s,1050);scene(s);run('draw();poll();');
 assert.ok(calls.some(c=>c[0]==='lineTo'&&c[1]===39));calls.length=0;advance(1302);
 assert.ok(calls.some(c=>c[0]==='clearRect'));assert.ok(!calls.some(c=>c[0]==='lineTo'&&c[1]===39));assert.equal(direction(),null);
});
test('near-edge portrait and offscreen classification stay unchanged; only the arrow becomes compact',()=>{
 for(const moving of [false,true]){
  reset();track(sample(1,[-360,0,0]));const s=sample(2,[-370,0,0]);if(moving)track(s,1050);scene(s);run('draw()');
  assert.ok(calls.some(c=>c[0]==='arc'&&c[1]===30&&c[2]===300&&c[3]===16));
  assert.equal(calls.filter(c=>c[0]==='translate').length,moving?1:0);
  if(moving){assert.ok(calls.some(c=>c[0]==='moveTo'&&c[1]===22));assert.ok(!calls.some(c=>c[0]==='lineTo'&&c[1]===39));}
 }
 reset();const s=sample(2,[-390,0,0]);scene(s);run('draw()');assert.ok(calls.some(c=>c[0]==='arc'&&c[1]===24&&c[3]===16));assert.equal(calls.filter(c=>c[0]==='translate').length,1);
});
test('new session, actor, level, frame rewind, delay and large jumps cannot produce false arrows',()=>{
 for(const next of[sample(3,[20,0,0],{epoch:2}),sample(3,[20,0,0],{level:17}),sample(3,[20,0,0],{player_address:'0x80100000'}),sample(1,[20,0,0]),sample(3,[5000,0,0]),sample(2,[15,0,0])]){
  reset();track(sample(1,[0,0,0]));track(sample(2,[10,0,0]),1050);track(next,1100);assert.equal(direction(),null);
 }
 reset();track(sample(1,[0,0,0]));track(sample(2,[10,0,0]),1700);assert.equal(direction(),null);
});
