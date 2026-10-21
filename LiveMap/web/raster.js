'use strict';

// Canvas fallback for colour/height views and unavailable WebGL textures.
function terrainFill(colour, height, bounds, mode) {
  if (mode !== 'height' && colour) {
    // Mild exposure lift for readability; colour still comes from the disc.
    return `rgb(${colour.map(v => Math.round(255 * Math.pow(v / 255, .8))).join(',')})`;
  }
  const range = Math.max(1, bounds[1][1] - bounds[1][0]);
  const shade = Math.round(47 + 36 * (bounds[1][1] - height) / range);
  return `rgb(${shade - 8},${shade + 5},${shade})`;
}

function rasterTerrain(g, displayMode, showObjects) {
  const mode = displayMode === 'texture' ? 'colour' : displayMode;
  if (g.raster && g.raster.mode === mode && g.raster.objects === showObjects) return g.raster;
  const bounds = showObjects ? (g.scene_bounds || g.bounds) : g.bounds;
  const dx = Math.max(1, bounds[0][1] - bounds[0][0]);
  const dz = Math.max(1, bounds[2][1] - bounds[2][0]);
  const pixelsPerUnit = 2048 / Math.max(dx, dz);
  const image = document.createElement('canvas');
  image.width = Math.ceil(dx * pixelsPerUnit) + 2;
  image.height = Math.ceil(dz * pixelsPerUnit) + 2;
  const context = image.getContext('2d');
  for (const [prop, index, height] of sceneFaceOrder(g)) {
    if (prop && !showObjects) continue;
    const mesh = prop ? g.object_mesh : g;
    const face = mesh.faces[index];
    context.fillStyle = terrainFill(mesh.face_colours?.[index], height, bounds, mode);
    context.beginPath();
    face.forEach((vertex, i) => {
      const point = mesh.vertices[vertex];
      const x = 1 + (point[0] - bounds[0][0]) * pixelsPerUnit;
      const y = 1 + (bounds[2][1] - point[2]) * pixelsPerUnit;
      if (i) context.lineTo(x, y);
      else context.moveTo(x, y);
    });
    context.closePath();
    context.fill();
    if (mode === 'height') {
      context.strokeStyle = '#91a28c44';
      context.lineWidth = .5;
      context.stroke();
    }
  }
  g.raster = {
    image, mode, objects: showObjects, pixelsPerUnit,
    left: bounds[0][0] - 1 / pixelsPerUnit,
    top: bounds[2][1] + 1 / pixelsPerUnit,
  };
  return g.raster;
}

function drawEdgeOnFaces(ctx, g, displayMode, showObjects, scale, toScreen) {
  const bounds = showObjects ? (g.scene_bounds || g.bounds) : g.bounds;
  for (const [prop, index, height] of sceneFaceOrder(g)) {
    if (prop && !showObjects) continue;
    const mesh = prop ? g.object_mesh : g;
    const offsets = mesh.edge_on_faces?.[index];
    if (!offsets) continue;
    ctx.fillStyle = terrainFill(mesh.face_colours[index], height, bounds, displayMode);
    ctx.beginPath();
    mesh.faces[index].forEach((vertex, i) => {
      const point = mesh.vertices[vertex];
      const [x, y] = toScreen(point[0], point[2]);
      const offset = offsets[i];
      if (i) ctx.lineTo(x + offset[0], y - offset[1]);
      else ctx.moveTo(x + offset[0], y - offset[1]);
    });
    ctx.closePath();
    ctx.fill();
  }
  for (const proxy of (g.fence_proxies || []).slice().sort((a, b) => b.ends[0][1] - a.ends[0][1])) {
    if (proxy.width * scale >= 2) continue;
    const [a, b] = proxy.ends;
    const [ax, ay] = toScreen(a[0], a[2]);
    const [bx, by] = toScreen(b[0], b[2]);
    const dx = bx - ax, dy = by - ay, length = Math.hypot(dx, dy);
    if (!length) continue;
    const nx = -dy / length, ny = dx / length;
    ctx.fillStyle = terrainFill(g.face_colours[proxy.face], a[1], bounds, displayMode);
    ctx.beginPath();
    ctx.moveTo(ax - nx, ay - ny);
    ctx.lineTo(bx - nx, by - ny);
    ctx.lineTo(bx + nx, by + ny);
    ctx.lineTo(ax + nx, ay + ny);
    ctx.closePath();
    ctx.fill();
  }
}
