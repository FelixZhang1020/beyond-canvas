// Untextured triangle meshes with point-light shadows. A fixed 1024px cube map
// records the nearest surface in all six directions from the movable lamp.
// Shadows update only when the light moves; orbiting needs one colour pass.
(function () {
  const LIMIT = 60000, SHADOW = 1024, FAR = 40;
  const sub=(a,b)=>a.map((x,i)=>x-b[i]);
  const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
  const unit=a=>a.map(x=>x/Math.hypot(...a));
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  function perspective(fov,aspect,near,far){
    const f=1/Math.tan(fov*Math.PI/360),d=near-far;
    return [f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)/d,-1, 0,0,2*far*near/d,0];
  }
  function view(eye,target,up){
    const z=unit(sub(eye,target)),x=unit(cross(up,z)),y=cross(z,x);
    return [x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1];
  }
  function multiply(a,b){
    const out=Array(16).fill(0);
    for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];
    return out;
  }
  function valid(mesh){
    if(!mesh || !Array.isArray(mesh.positions) || !Array.isArray(mesh.normals) || !Array.isArray(mesh.indices))return false;
    const n=mesh.positions.length/3;
    if(!Number.isInteger(n)||n<4||n>LIMIT||mesh.normals.length!==n*3||mesh.indices.length<12||mesh.indices.length>LIMIT*3||mesh.indices.length%3)return false;
    if(!mesh.positions.every((v,i)=>Number.isFinite(v)&&Math.abs(v)<=6&&(i%3!==1||v>=-.002)))return false;
    if(!mesh.normals.every(v=>Number.isFinite(v)&&Math.abs(v)<=1.001))return false;
    for(let i=0;i<mesh.normals.length;i+=3)if(Math.abs(Math.hypot(...mesh.normals.slice(i,i+3))-1)>.02)return false;
    return mesh.indices.every(v=>Number.isInteger(v)&&v>=0&&v<n) &&
      Array.isArray(mesh.size)&&mesh.size.length===3&&mesh.size.every(v=>Number.isFinite(v)&&v>.01&&v<=6);
  }
  const vertex=`attribute vec3 position,normal;uniform mat4 mvp;varying vec3 world,n;
void main(){world=position;n=normal;gl_Position=mvp*vec4(position,1.);}`;
  const pack=`vec4 pack(float d){vec4 a=fract(d*vec4(1.,255.,65025.,16581375.));return a-a.yzww*vec4(1./255.,1./255.,1./255.,0.);}`;
  const depth=`precision highp float;varying vec3 world;uniform vec3 lamp;${pack}
void main(){gl_FragColor=pack(min(length(world-lamp)/40.,.99999));}`;
  const fragment=`precision highp float;varying vec3 world,n;uniform samplerCube shadows;
uniform vec3 lamp,eye;uniform float strength,softness,ground,materialMode;
float test(vec3 delta,float depth){float nearest=dot(textureCube(shadows,delta),vec4(1.,1./255.,1./65025.,1./16581375.))*40.;return step(depth,nearest);}
void main(){vec3 normal=normalize(n);if(!gl_FrontFacing)normal=-normal;
 vec3 delta=world-lamp;float diffuse=max(0.,dot(normal,-normalize(delta)));
 // Offset the receiver along its normal to avoid shadow acne on grazing faces.
 delta+=normal*(.012+.012*(1.-diffuse));
 float depth=length(delta)-.006;float visibility=test(delta,depth);
 if(softness>0.)visibility=(visibility+test(delta+vec3(.018,0.,0.),depth)+test(delta+vec3(0.,.018,0.),depth)+test(delta+vec3(0.,0.,.018),depth))*.25;
 float light=.19+.07*max(normal.y,0.)+strength*.65*diffuse*visibility;
 vec3 albedo=ground>.5?vec3(.90,.865,.79):materialMode>1.5?vec3(.5)+normal*.38:materialMode>.5?vec3(.72):vec3(.89,.88,.85);
 if(materialMode>3.5){gl_FragColor=vec4(vec3(.23),1.);return;}
 vec3 color=pow(albedo*light,vec3(1./2.2));
 float fog=1.-exp(-max(length(world-eye)-12.,0.)*.07);
 gl_FragColor=vec4(mix(color,vec3(.995,.985,.964),fog),1.);}`;
  function renderer(canvas,scene){
    const gl=canvas.getContext('webgl',{alpha:false,antialias:false,preserveDrawingBuffer:true});
    if(!gl || !valid(scene.mesh))throw new Error('Mesh renderer unavailable');
    const buffers=[],programs=[],shaders=[],textures=[],frames=[],depths=[];
    function dispose(){buffers.forEach(b=>gl.deleteBuffer(b));programs.forEach(p=>gl.deleteProgram(p));shaders.forEach(s=>gl.deleteShader(s));textures.forEach(t=>gl.deleteTexture(t));frames.forEach(f=>gl.deleteFramebuffer(f));depths.forEach(d=>gl.deleteRenderbuffer(d));}
    try{
      function program(fragment){
        const p=gl.createProgram();programs.push(p);
        for(const [type,code] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
          const s=gl.createShader(type);shaders.push(s);gl.shaderSource(s,code);gl.compileShader(s);
          if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error('Mesh shader compilation failed');
          gl.attachShader(p,s);
        }
        gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw new Error('Mesh shader link failed');
        const loc={};['mvp','lamp','eye','shadows','strength','softness','ground','materialMode'].forEach(k=>loc[k]=gl.getUniformLocation(p,k));
        return {p,loc,position:gl.getAttribLocation(p,'position'),normal:gl.getAttribLocation(p,'normal')};
      }
      function geometry(positions,normals,indices){
        const data=new Float32Array(positions.length*2);
        for(let i=0;i<positions.length/3;i++){data.set(positions.slice(i*3,i*3+3),i*6);data.set(normals.slice(i*3,i*3+3),i*6+3);}
        const b=gl.createBuffer(),index=gl.createBuffer();buffers.push(b,index);
        gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,index);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);
        return {b,index,count:indices.length};
      }
      const color=program(fragment),shadow=program(depth);
      const mesh=geometry(scene.mesh.positions,scene.mesh.normals,scene.mesh.indices);
      const edges=[];
      for(let i=0;i<scene.mesh.indices.length;i+=3){const a=scene.mesh.indices[i],b=scene.mesh.indices[i+1],c=scene.mesh.indices[i+2];edges.push(a,b,b,c,c,a);}
      const wireIndex=gl.createBuffer();buffers.push(wireIndex);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,wireIndex);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(edges),gl.STATIC_DRAW);
      const wire={b:mesh.b,index:wireIndex,count:edges.length};
      const floor=geometry([-30,0,-30,30,0,-30,30,0,30,-30,0,30],[0,1,0,0,1,0,0,1,0,0,1,0],[0,2,1,0,3,2]);
      const cube=gl.createTexture();textures.push(cube);gl.bindTexture(gl.TEXTURE_CUBE_MAP,cube);
      for(let i=0;i<6;i++)gl.texImage2D(gl.TEXTURE_CUBE_MAP_POSITIVE_X+i,0,gl.RGBA,SHADOW,SHADOW,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
      gl.texParameteri(gl.TEXTURE_CUBE_MAP,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_CUBE_MAP,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_CUBE_MAP,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_CUBE_MAP,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      const fbo=gl.createFramebuffer(),zbuf=gl.createRenderbuffer();frames.push(fbo);depths.push(zbuf);
      gl.bindFramebuffer(gl.FRAMEBUFFER,fbo);gl.bindRenderbuffer(gl.RENDERBUFFER,zbuf);
      gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT16,SHADOW,SHADOW);gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,zbuf);
      gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_CUBE_MAP_POSITIVE_X,cube,0);
      if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw new Error('Mesh shadows unavailable');
      gl.bindFramebuffer(gl.FRAMEBUFFER,null);
      let lastLight='';
      const dirs=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],ups=[[0,-1,0],[0,-1,0],[0,0,1],[0,0,-1],[0,-1,0],[0,-1,0]];
      function drawGeometry(p,g,mode=gl.TRIANGLES){
        gl.bindBuffer(gl.ARRAY_BUFFER,g.b);gl.enableVertexAttribArray(p.position);gl.vertexAttribPointer(p.position,3,gl.FLOAT,false,24,0);
        if(p.normal>=0){gl.enableVertexAttribArray(p.normal);gl.vertexAttribPointer(p.normal,3,gl.FLOAT,false,24,12);}
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,g.index);gl.drawElements(mode,g.count,gl.UNSIGNED_SHORT,0);
        if(p.normal>=0)gl.disableVertexAttribArray(p.normal);gl.disableVertexAttribArray(p.position);
      }
      return {dispose,draw(camera,light,strength,interacting,appearance={material:'plaster',ground:true}){
        const rect=canvas.getBoundingClientRect(),[w,h]=Studio.relight.resolution(rect.width,rect.height,window.devicePixelRatio);
        if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
        gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);gl.disable(gl.BLEND);gl.depthFunc(gl.LEQUAL);
        const key=light.join(',');
        if(key!==lastLight){
          gl.useProgram(shadow.p);gl.uniform3fv(shadow.loc.lamp,light);gl.bindFramebuffer(gl.FRAMEBUFFER,fbo);gl.viewport(0,0,SHADOW,SHADOW);
          gl.clearColor(1,1,1,1);const projection=perspective(90,1,.025,FAR);
          for(let i=0;i<6;i++){
            gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_CUBE_MAP_POSITIVE_X+i,cube,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
            gl.uniformMatrix4fv(shadow.loc.mvp,false,multiply(projection,view(light,light.map((x,j)=>x+dirs[i][j]),ups[i])));drawGeometry(shadow,mesh);
          }
          lastLight=key;
        }
        gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.viewport(0,0,w,h);gl.clearColor(.995,.985,.964,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
        gl.useProgram(color.p);const b=Studio.relight.basis(camera);
        gl.uniformMatrix4fv(color.loc.mvp,false,multiply(perspective(camera.fov,w/h,.05,FAR),view(b.eye,camera.target,[0,1,0])));
        gl.uniform3fv(color.loc.lamp,light);gl.uniform3fv(color.loc.eye,b.eye);gl.uniform1f(color.loc.strength,strength);gl.uniform1f(color.loc.softness,interacting?0:1);
        gl.uniform1f(color.loc.materialMode,appearance.material==='normal'?2:appearance.material==='matte'?1:0);
        gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_CUBE_MAP,cube);gl.uniform1i(color.loc.shadows,0);
        if(appearance.ground){gl.uniform1f(color.loc.ground,1);drawGeometry(color,floor);}
        gl.uniform1f(color.loc.ground,0);
        if(appearance.material==='wire'){
          gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(1,1);drawGeometry(color,mesh);gl.disable(gl.POLYGON_OFFSET_FILL);
          gl.uniform1f(color.loc.materialMode,4);drawGeometry(color,wire,gl.LINES);
        }else drawGeometry(color,mesh);
      }};
    }catch(error){dispose();throw error;}
  }
  Studio.mesh={valid,renderer,perspective,view,multiply};
})();
