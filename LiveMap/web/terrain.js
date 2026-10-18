'use strict';
// One active GPU mesh/atlas. Render at viewport pixel resolution, never stretch a
// low-resolution whole-level bitmap. The 2D canvas draws markers above this layer.
// Merge draw order without rewriting the original terrain arrays/bounds.
function sceneFaceOrder(g) {
  if (g.sceneOrder) return g.sceneOrder;
  const order=[];
  for (const [prop,mesh] of [[0,g],[1,g.object_mesh]]) {
    if (!mesh) continue;
    for (let i=0;i<mesh.faces.length;i++) {
      const face=mesh.faces[i], height=face.reduce((sum,v)=>sum+mesh.vertices[v][1],0)/face.length;
      order.push([prop,i,height]);
    }
  }
  return g.sceneOrder=order.sort((a,b)=>b[2]-a[2]);
}
class TerrainRenderer {
  constructor(onUnavailable) {
    this.canvas = document.createElement('canvas');
    this.onUnavailable = onUnavailable;
    this.reason = '';
    this.geometry = null;
    this.buffer = null;
    this.texture = null;
    this.key = null;
    this.gl = this.canvas.getContext('webgl', {alpha:true, antialias:true, preserveDrawingBuffer:true, premultipliedAlpha:true});
    this.canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault();
      this.reason = 'Graphics context lost — reload to restore textures';
      this.clear();
      this.onUnavailable();
    });
    if (!this.gl) { this.reason = 'WebGL unavailable'; return; }
    const gl = this.gl;
    try {
      const compile = (type, source) => {
        const shader = gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);
        if (!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) { const message=gl.getShaderInfoLog(shader);gl.deleteShader(shader);throw Error(message); }
        return shader;
      };
      const vertex = compile(gl.VERTEX_SHADER, `
        attribute vec2 position; attribute vec2 uv; attribute vec3 shade; attribute float textured;
        attribute float elevation; attribute float isProp; attribute vec2 widthOffset; attribute float proxyWidth;
        uniform vec2 centre; uniform vec2 extent; uniform vec2 heightRange; uniform vec2 pixelSize;
        varying vec2 texcoord; varying vec3 colour; varying float useTexture; varying float prop; varying float fenceWidth;
        void main(){
          float depth=(2.0*(elevation-heightRange.x)/heightRange.y-1.0)*0.99;
          gl_Position=vec4((position-centre)*extent+widthOffset*pixelSize,depth,1.0);
          texcoord=uv;colour=shade;useTexture=textured;prop=isProp;fenceWidth=proxyWidth;
        }`);
      const fragment = compile(gl.FRAGMENT_SHADER, `
        precision mediump float;
        uniform sampler2D atlas; uniform bool showProps; uniform float viewScale;
        varying vec2 texcoord; varying vec3 colour; varying float useTexture; varying float prop; varying float fenceWidth;
        void main(){
          if(prop>0.5&&!showProps)discard;
          if(fenceWidth>=0.0 && fenceWidth*viewScale>=2.0)discard;
          vec4 texel=useTexture>0.5?texture2D(atlas,texcoord):vec4(1.0);
          if(texel.a<0.01)discard;
          gl_FragColor=vec4(pow(clamp(texel.rgb*colour,0.0,1.0),vec3(0.8)),texel.a);
        }`);
      this.program=gl.createProgram();gl.attachShader(this.program,vertex);gl.attachShader(this.program,fragment);gl.linkProgram(this.program);
      gl.deleteShader(vertex);gl.deleteShader(fragment);
      if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(this.program));
      this.attributes=['position','uv','shade','textured','elevation','isProp','widthOffset','proxyWidth'].map(name=>gl.getAttribLocation(this.program,name));
      this.heightUniform=gl.getUniformLocation(this.program,'heightRange');this.propsUniform=gl.getUniformLocation(this.program,'showProps');
      this.pixelSize=gl.getUniformLocation(this.program,'pixelSize');this.viewScale=gl.getUniformLocation(this.program,'viewScale');
      this.centre=gl.getUniformLocation(this.program,'centre');this.extent=gl.getUniformLocation(this.program,'extent');
      this.sampler=gl.getUniformLocation(this.program,'atlas');
      this.maxSize=Math.min(8192,gl.getParameter(gl.MAX_RENDERBUFFER_SIZE));
    } catch(error) { this.reason='Texture renderer unavailable: '+error.message; }
  }
  clear() {
    if(this.gl) { this.gl.deleteBuffer(this.buffer);this.gl.deleteTexture(this.texture); }
    this.buffer=null;this.texture=null;this.geometry=null;this.key=null;
  }
  setMap(g, image) {
    this.clear();
    if(this.reason || !image || !g.texture_atlas)return false;
    const gl=this.gl, atlas=g.texture_atlas, vertices=[], thinVertices=[];
    try {
      if(atlas.width>gl.getParameter(gl.MAX_TEXTURE_SIZE)||atlas.height>gl.getParameter(gl.MAX_TEXTURE_SIZE))throw Error('Atlas exceeds graphics limit');
      let minY=Infinity,maxY=-Infinity;
      for(const [prop,index] of sceneFaceOrder(g)) {
        const mesh=prop?g.object_mesh:g;
        const face=mesh.faces[index], tid=mesh.face_textures[index], rect=tid===null?null:atlas.rects[tid];
        if(tid!==null&&!rect)throw Error('Missing texture rectangle');
        const output=mesh.edge_on_faces?.[index]?thinVertices:vertices;
        // Faces are cyclic. GXSP was converted from strip order; MOF wire
        // quads were already cyclic. Both split across vertices 1 and 3.
        for(const j of face.length===4?[0,1,3,3,1,2]:[0,1,2]) {
          const p=mesh.vertices[face[j]], rgb=mesh.vertex_colours[face[j]], raw=mesh.face_uvs[index][j];
          minY=Math.min(minY,p[1]);maxY=Math.max(maxY,p[1]);
          const u=rect?(rect[0]+.5+raw[0]/255*(rect[2]-1))/atlas.width:0;
          // PS1 V=0 addresses the first stored image row, as does our PNG atlas.
          // With UNPACK_FLIP_Y_WEBGL=false, do not reverse V a second time.
          const v=rect?(rect[1]+.5+raw[1]/255*(rect[3]-1))/atlas.height:0;
          const divisor=rect?128:255;
          const offset=mesh.edge_on_faces?.[index]?.[j] || [0,0];
          output.push(p[0],p[2],u,v,rgb[0]/divisor,rgb[1]/divisor,rgb[2]/divisor,rect?1:0,p[1],prop,...offset,-1);
        }
      }
      // Real fence cutouts can disappear at subpixel scale. Use an opaque,
      // native-colour 2px readout only while their actual width is below 2px.
      for(const proxy of (g.fence_proxies||[]).slice().sort((a,b)=>b.ends[0][1]-a.ends[0][1])) {
        const [a,b]=proxy.ends,dx=b[0]-a[0],dz=b[2]-a[2],length=Math.hypot(dx,dz);
        if(!length)continue;
        const nx=-dz/length,nz=dx/length,rgb=g.face_colours[proxy.face].map(c=>c/255);
        for(const [p,side] of [[a,-1],[b,-1],[a,1],[a,1],[b,-1],[b,1]])
          thinVertices.push(p[0],p[2],0,0,...rgb,0,p[1],0,nx*side,nz*side,proxy.width);
      }
      this.normalCount=vertices.length/13;
      const data=new Float32Array(vertices.length+thinVertices.length);data.set(vertices);data.set(thinVertices,vertices.length);
      this.buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
      this.texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,this.texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      if(gl.getError()!==gl.NO_ERROR)throw Error('Graphics upload failed');
      this.heightRange=[minY,Math.max(1,maxY-minY)];
      this.count=data.length/13;this.geometry=g;
      return true;
    } catch(error) { this.clear();this.reason='Texture renderer unavailable: '+error.message;return false; }
  }
  render(g,cx,cz,scale,w,h,dpr,showProps=true) {
    if(this.reason || this.geometry!==g)return null;
    const width=Math.max(1,Math.min(this.maxSize,Math.round(w*dpr))), height=Math.max(1,Math.min(this.maxSize,Math.round(h*dpr)));
    const key=[cx,cz,scale,w,h,width,height,showProps].join(',');
    if(this.key===key)return this.canvas;
    if(this.canvas.width!==width||this.canvas.height!==height){this.canvas.width=width;this.canvas.height=height;}
    const gl=this.gl;gl.viewport(0,0,width,height);gl.clearColor(0,0,0,0);gl.clearDepth(1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);
    gl.useProgram(this.program);gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);
    const sizes=[2,2,3,1,1,1,2,1], offsets=[0,8,16,28,32,36,40,48];
    this.attributes.forEach((a,i)=>{gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,sizes[i],gl.FLOAT,false,52,offsets[i]);});
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.texture);gl.uniform1i(this.sampler,0);
    gl.uniform2f(this.heightUniform,...this.heightRange);gl.uniform1i(this.propsUniform,showProps?1:0);
    // Unit offsets span -1..1: exactly two CSS pixels, at any zoom/DPR.
    gl.uniform2f(this.pixelSize,2/Math.max(1,w),2/Math.max(1,h));gl.uniform1f(this.viewScale,scale);
    gl.uniform2f(this.centre,cx,cz);gl.uniform2f(this.extent,2*scale/Math.max(1,w),2*scale/Math.max(1,h));
    gl.enable(gl.BLEND);gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
    gl.drawArrays(gl.TRIANGLES,0,this.normalCount);
    // Only the otherwise invisible fence/gate faces get this 2px map readout;
    // an overlapping wall cap must not hide them again. No wall outlines.
    gl.disable(gl.DEPTH_TEST);
    gl.drawArrays(gl.TRIANGLES,this.normalCount,this.count-this.normalCount);
    this.key=key;return this.canvas;
  }
}

async function decodeTerrainAtlas(g) {
  if(!g.texture_atlas)return null;
  const image=new Image();
  image.src=g.texture_atlas.png;
  await image.decode();
  if(image.width!==g.texture_atlas.width||image.height!==g.texture_atlas.height)throw Error('Texture atlas dimensions mismatch');
  return image;
}
