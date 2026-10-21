'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture() {
  const calls = [];
  const context = new Proxy({}, {
    get(target, name) {
      if (name in target) return target[name];
      return (...args) => calls.push([name, ...args, target.fillStyle]);
    },
  });
  const sandbox = {
    document: {createElement: () => ({getContext: () => context})},
    context,
    geometry: {
      bounds: [[0, 100], [0, 10], [0, 100]],
      vertices: [[0, 10, 0], [100, 10, 0], [0, 10, 100]],
      faces: [[0, 1, 2]], face_colours: [[255, 0, 0]],
      object_mesh: {
        vertices: [[0, 0, 0], [100, 0, 0], [0, 0, 100]],
        faces: [[0, 1, 2]], face_colours: [[0, 255, 0]],
      },
    },
  };
  vm.createContext(sandbox);
  for (const file of ['terrain.js', 'raster.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, file), 'utf8'), sandbox);
  }
  return {calls, sandbox, run: source => vm.runInContext(source, sandbox)};
}

test('fallback preserves scene order, exposure, height shading and object toggle', () => {
  const {calls, run} = fixture();
  run("rasterTerrain(geometry, 'colour', true)");
  assert.deepEqual(calls.filter(call => call[0] === 'fill'), [['fill', 'rgb(255,0,0)'], ['fill', 'rgb(0,255,0)']]);
  calls.length = 0;
  run("rasterTerrain(geometry, 'height', true)");
  assert.deepEqual(calls.filter(call => call[0] === 'fill'), [['fill', 'rgb(39,52,47)'], ['fill', 'rgb(75,88,83)']]);
  assert.equal(calls.filter(call => call[0] === 'stroke').length, 2);
  calls.length = 0;
  run("rasterTerrain(geometry, 'colour', false)");
  assert.deepEqual(calls.filter(call => call[0] === 'fill'), [['fill', 'rgb(255,0,0)']]);
  assert.equal(run("terrainFill([128,128,128], 0, geometry.bounds, 'colour')"), 'rgb(147,147,147)');
});

test('scene faces are sorted by height rather than terrain/object insertion order', () => {
  const {calls, sandbox, run} = fixture();
  // The object is inserted after terrain, but must be painted first here.
  for (const point of sandbox.geometry.object_mesh.vertices) point[1] = 20;
  run("rasterTerrain(geometry, 'colour', true)");
  assert.deepEqual(calls.filter(call => call[0] === 'fill'), [['fill', 'rgb(0,255,0)'], ['fill', 'rgb(255,0,0)']]);
});

test('raster cache is reused only for matching mode and object visibility', () => {
  const {run} = fixture();
  assert.equal(run("rasterTerrain(geometry, 'texture', true) === rasterTerrain(geometry, 'colour', true)"), true);
  assert.equal(run("rasterTerrain(geometry, 'colour', true) === rasterTerrain(geometry, 'height', true)"), false);
  assert.equal(run("rasterTerrain(geometry, 'height', true) === rasterTerrain(geometry, 'height', false)"), false);
  assert.equal(run("rasterTerrain(geometry, 'colour', true).image.width"), 2050);
});

test('edge-on offsets remain screen-space and fences appear only below two pixels', () => {
  const {calls, sandbox, run} = fixture();
  sandbox.geometry.edge_on_faces = {0: [[-1, 0], [1, 0], [1, 0]]};
  run("drawEdgeOnFaces(context, geometry, 'colour', false, 1, (x,z) => [x,-z])");
  assert.deepEqual(calls.find(call => call[0] === 'moveTo'), ['moveTo', -1, -0, 'rgb(255,0,0)']);
  sandbox.geometry.edge_on_faces = {};
  sandbox.geometry.fence_proxies = [{face: 0, width: 1, ends: [[0, 10, 0], [100, 10, 0]]}];
  calls.length = 0;
  run("drawEdgeOnFaces(context, geometry, 'colour', false, 1, (x,z) => [x,-z])");
  assert.equal(calls.filter(call => call[0] === 'fill').length, 1);
  assert.equal(Math.abs(calls.find(call => call[0] === 'moveTo')[2]), 1);
  calls.length = 0;
  run("drawEdgeOnFaces(context, geometry, 'colour', false, 2, (x,z) => [x,-z])");
  assert.equal(calls.length, 0);
});
