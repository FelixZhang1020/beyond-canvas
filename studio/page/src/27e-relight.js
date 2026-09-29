// Perspective solid intersections and shadows. No downloaded library or model
// calls: one draw only when something changes, bounded even on a 4K display.
(function () {
  const MAX = 6, DEG = Math.PI / 180;
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const add = (a, b) => a.map((v, i) => v + b[i]);
  const mul = (a, s) => a.map(v => v * s);
  const unit = a => mul(a, 1 / Math.hypot(...a));
  const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
  const dot = (a, b) => a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
  function basis(camera) {
    const e = camera.elevation * DEG, a = camera.azimuth * DEG;
    const offset = [Math.sin(a)*Math.cos(e), Math.sin(e), Math.cos(a)*Math.cos(e)];
    const eye = add(camera.target, mul(offset, camera.distance));
    const forward = mul(offset, -1), right = unit(cross(forward, [0, 1, 0]));
    return { eye, forward, right, up: cross(right, forward) };
  }
  function ray(camera, u, v, aspect) {
    const b = basis(camera), f = Math.tan(camera.fov * DEG / 2);
    return { origin: b.eye, direction: unit(add(b.forward, add(mul(b.right, (u*2-1)*f*aspect), mul(b.up, (1-v*2)*f)))) };
  }
  function floorPoint(camera, u, v, aspect) {
    const r = ray(camera, u, v, aspect);
    if (r.direction[1] >= -.001) return null;
    return add(r.origin, mul(r.direction, -r.origin[1] / r.direction[1]));
  }
  function resolution(w, h, dpr) {
    const k = Math.min(dpr || 1, 1.5, 1440 / Math.max(w, 1), Math.sqrt(1000000 / Math.max(1, w*h)));
    return [Math.max(1, Math.floor(w*k)), Math.max(1, Math.floor(h*k))];
  }
  function valid(scene) {
    const number = (v, lo, hi) => typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi;
    const vec = (v, lo, hi) => Array.isArray(v) && v.length === 3 && v.every(x => number(x, lo, hi));
    const c = scene && scene.camera;
    const mesh = scene && ['single-image-mesh','parametric-still-life'].includes(scene.method);
    const objects = kinds => Array.isArray(scene.objects) && scene.objects.length > 0 && scene.objects.length <= MAX &&
      scene.objects.every(o => o && kinds.includes(o.kind) && vec(o.position,-16,16) && vec(o.size,.01,16) &&
        number(o.yaw,-90,90) && Math.abs(o.position[1]-o.size[1]/2)<.002);
    return !!(scene && scene.version === 1 && (scene.method === 'geometric-approximation' || mesh) && c &&
      (scene.subject === undefined || scene.method === 'single-image-mesh' && scene.subject === 'fruit') &&
      vec(c.target, -6, 6) && number(c.distance, 4, 25) && number(c.elevation, 10, 80) &&
      number(c.azimuth, -180, 180) && number(c.fov, 20, 65) && number(scene.source_aspect, .1, 10) &&
      vec(scene.light, -8, 8) && scene.light[1] >= 3 && (mesh ? !!(Studio.mesh && Studio.mesh.valid(scene.mesh)) &&
        (scene.method !== 'parametric-still-life' || objects(['box','sphere','cylinder','pear','apple','orange'])) :
        objects(['box','sphere','cylinder'])));
  }

  const vertex = `attribute vec2 point; void main(){gl_Position=vec4(point,0.,1.);}`;
  // Intersect analytic primitives in normalized object space. The ray parameter
  // stays in WORLD units, so all objects, caps, ground and shadows share depth.
  const fragment = `precision highp float;
uniform vec2 resolution;
uniform vec3 eye, forward, right, up, light;
uniform float focal, aspect, strength, softness, materialMode, groundEnabled;
uniform int count;
uniform vec4 centers[6], sizes[6];
const float FAR=10000.;
vec3 rotateY(vec3 p,float a){float c=cos(a),s=sin(a);return vec3(c*p.x+s*p.z,p.y,-s*p.x+c*p.z);}
vec4 hit(vec3 origin,vec3 direction,vec4 center,vec4 size){
 vec3 halfSize=size.xyz*.5;
 vec3 ro=rotateY(origin-center.xyz,-size.w)/halfSize;
 vec3 rd=rotateY(direction,-size.w)/halfSize;
 float t=FAR; vec3 n=vec3(0.);
 if(center.w<.5){
  vec3 safe=mix(vec3(1.e-7),rd,step(vec3(1.e-7),abs(rd)));
  vec3 a=(-vec3(1.)-ro)/safe,b=(vec3(1.)-ro)/safe;
  vec3 near=min(a,b),far=max(a,b);
  float lo=max(max(near.x,near.y),near.z),hi=min(min(far.x,far.y),far.z);
  if(hi>=max(lo,.0001)){
   t=lo>.0001?lo:hi; vec3 p=ro+rd*t,q=abs(p);
   if(q.x>=q.y&&q.x>=q.z)n=vec3(sign(p.x),0.,0.);
   else if(q.y>=q.z)n=vec3(0.,sign(p.y),0.);else n=vec3(0.,0.,sign(p.z));
  }
 }else if(center.w<1.5){
  float a=dot(rd,rd),b=dot(ro,rd),c=dot(ro,ro)-1.,disc=b*b-a*c;
  if(disc>=0.){float lo=(-b-sqrt(disc))/a,hi=(-b+sqrt(disc))/a;
   if(hi>.0001){t=lo>.0001?lo:hi;n=ro+rd*t;}}
 }else{
  float a=dot(rd.xz,rd.xz),b=dot(ro.xz,rd.xz),c=dot(ro.xz,ro.xz)-1.,disc=b*b-a*c;
  if(a>1.e-9&&disc>=0.){
   float lo=(-b-sqrt(disc))/a,hi=(-b+sqrt(disc))/a;
   if(lo>.0001&&abs(ro.y+rd.y*lo)<=1.)t=lo;
   else if(hi>.0001&&abs(ro.y+rd.y*hi)<=1.)t=hi;
   n=vec3(ro.x+rd.x*t,0.,ro.z+rd.z*t);
  }
  if(abs(rd.y)>1.e-9){
   for(int j=0;j<2;j++){float y=j==0?-1.:1.;float cap=(y-ro.y)/rd.y;
    vec3 p=ro+rd*cap;if(cap>.0001&&cap<t&&dot(p.xz,p.xz)<=1.){t=cap;n=vec3(0.,y,0.);}}
  }
 }
 if(t==FAR)return vec4(0.,0.,0.,FAR);
 return vec4(normalize(rotateY(n/halfSize,size.w)),t);
}
float shadow(vec3 p,vec3 n,vec3 lamp){
 vec3 delta=lamp-p;float distance=length(delta);vec3 rd=delta/distance;
 for(int i=0;i<6;i++){if(i>=count)break;
  if(hit(p+n*.003,rd,centers[i],sizes[i]).w<distance)return 0.;}
 return 1.;
}
void main(){
 vec2 uv=gl_FragCoord.xy/resolution*2.-1.;
 vec3 rd=normalize(forward+right*uv.x*focal*aspect+up*uv.y*focal);
 float depth=FAR;vec3 n=vec3(0.);float ground=0.;
 if(groundEnabled>.5&&rd.y<-.0001){float t=-eye.y/rd.y;if(t>0.){depth=t;n=vec3(0.,1.,0.);ground=1.;}}
 for(int i=0;i<6;i++){if(i>=count)break;vec4 h=hit(eye,rd,centers[i],sizes[i]);
  if(h.w<depth){depth=h.w;n=h.xyz;ground=0.;}}
 if(depth==FAR){gl_FragColor=vec4(.995,.985,.964,1.);return;}
 vec3 p=eye+rd*depth,ld=normalize(light-p);
 float visibility=shadow(p,n,light);
 if(softness>.0){visibility=(visibility+shadow(p,n,light+vec3(.14,0.,.09))+
  shadow(p,n,light+vec3(-.14,0.,.09))+shadow(p,n,light+vec3(0.,0.,-.16)))*.25;}
 float diffuse=max(0.,dot(n,ld));
 float illumination=.19+.07*max(n.y,0.)+strength*.65*diffuse*visibility;
 vec3 albedo=ground>.5?vec3(.90,.865,.79):materialMode>1.5?vec3(.5)+n*.38:materialMode>.5?vec3(.72):vec3(.89,.88,.85);
 vec3 color=pow(albedo*illumination,vec3(1./2.2));
 float fog=1.-exp(-max(depth-12.,0.)*.07);
 gl_FragColor=vec4(mix(color,vec3(.995,.985,.964),fog),1.);
}`;

  function renderer(canvas, scene) {
    const gl = canvas.getContext('webgl', { alpha: false, antialias: false, depth: false, preserveDrawingBuffer: true });
    if (!gl) throw new Error('WebGL unavailable');
    const shaders = [], program = gl.createProgram();
    let buffer = null;
    function dispose() { if (buffer) gl.deleteBuffer(buffer); gl.deleteProgram(program); shaders.forEach(s => gl.deleteShader(s)); }
    try {
      for (const [type, code] of [[gl.VERTEX_SHADER, vertex], [gl.FRAGMENT_SHADER, fragment]]) {
        const s = gl.createShader(type); shaders.push(s); gl.shaderSource(s, code); gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error('shader compilation failed');
        gl.attachShader(program, s);
      }
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('shader link failed');
      gl.useProgram(program); buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
      const attr = gl.getAttribLocation(program, 'point'); gl.enableVertexAttribArray(attr); gl.vertexAttribPointer(attr, 2, gl.FLOAT, false, 0, 0);
      const locations = {};
      ['resolution','eye','forward','right','up','light','focal','aspect','strength','softness','materialMode','groundEnabled','count','centers[0]','sizes[0]'].forEach(k => locations[k] = gl.getUniformLocation(program, k));
      const centers = new Float32Array(MAX*4), sizes = new Float32Array(MAX*4);
      scene.objects.forEach((o, i) => { centers.set([...o.position, ['box','sphere','cylinder'].indexOf(o.kind)], i*4); sizes.set([...o.size, o.yaw*DEG], i*4); });
      gl.uniform4fv(locations['centers[0]'], centers); gl.uniform4fv(locations['sizes[0]'], sizes);
      gl.uniform1i(locations.count, scene.objects.length);
      return {
        draw(camera, light, strength, interacting, appearance = {material:'plaster',ground:true}) {
          const b = basis(camera), rect = canvas.getBoundingClientRect();
          const [w,h] = resolution(rect.width, rect.height, window.devicePixelRatio);
          if (canvas.width !== w || canvas.height !== h) { canvas.width=w; canvas.height=h; }
          gl.viewport(0,0,w,h); gl.uniform2f(locations.resolution,w,h);
          for (const k of ['eye','forward','right','up']) gl.uniform3fv(locations[k], b[k]);
          gl.uniform3fv(locations.light,light); gl.uniform1f(locations.focal,Math.tan(camera.fov*DEG/2));
          gl.uniform1f(locations.aspect,w/h); gl.uniform1f(locations.strength,strength);
          gl.uniform1f(locations.materialMode,appearance.material==='normal'?2:appearance.material==='matte'?1:0);
          gl.uniform1f(locations.groundEnabled,appearance.ground?1:0);
          gl.uniform1f(locations.softness,interacting?0:1); gl.drawArrays(gl.TRIANGLES,0,6);
        }, dispose
      };
    } catch (e) { dispose(); throw e; }
  }

  function open(host, scene, drawing) {
    Studio.relight.close();
    // Every study opens in the model viewer when the page has it, so solids get its surfaces too;
    // the renderer below stays for pages and tests without it.
    if (Studio.cloudRelight) return Studio.cloudRelight.open(host, scene, drawing);
    const t = k => Studio.i18n.t('relight.'+k);
    function el(tag, cls, text, parent) {
      const node = document.createElement(tag); node.className = cls || ''; if (text) node.textContent=text;
      if (parent) parent.appendChild(node); return node;
    }
    if (!valid(scene)) { el('p','relight-error',t('invalid'),host); return; }
    const isGenerated=scene.method==='single-image-mesh', isPortrait=isGenerated && scene.subject!=='fruit';
    const isStillLife=scene.method==='parametric-still-life', isMesh=isGenerated || isStillLife;
    host.classList.add('relight');host.classList.toggle('relight-mesh',isPortrait);
    const makeRenderer=isMesh ? Studio.mesh.renderer : renderer;
    el('p','relight-note',t(isStillLife?'fruitApproximation':isGenerated?'meshApproximation':'approximation'),host);
    const views = el('div','relight-views','',host);
    const original = el('figure','relight-original','',views);
    el('figcaption','',t('original'),original);
    const img = el('img','','',original); img.alt=t('original'); img.src=drawing.url;
    const stage = el('div','relight-stage','',views);
    const canvas = el('canvas','','',stage); canvas.style.aspectRatio=isPortrait?'1':String(scene.source_aspect);
    canvas.setAttribute('aria-label',t('canvas')); canvas.tabIndex=0;
    const hint = el('p','relight-hint',t('orbitHint'),host);
    const controls = el('div','relight-controls','',host);
    const quick = host.id === 'sketch-workbench' ? el('div','relight-quick','',stage) : controls;
    if (quick !== controls) stage.insertBefore(quick,canvas);
    let camera = JSON.parse(JSON.stringify(scene.camera)), light = scene.light.slice(), strength=1, mode='orbit';
    const appearance={material:'plaster',grayscale:false,ground:true};
    let raf=0, settle=0, autoFrame=0, autoAt=0, auto=false, closed=false, lost=false, dragging=null, gpu;
    try { gpu=makeRenderer(canvas,scene); } catch (e) { controls.remove(); hint.textContent=t('unavailable'); canvas.hidden=true; original.classList.add('is-visible'); return; }
    function draw(interacting) {
      if (closed || lost || document.hidden) return;
      syncStageLamp();
      gpu.draw(camera,light,strength,interacting,appearance);
    }
    function request(interacting) {
      if (closed || lost || document.hidden) return;
      if (!raf) raf=requestAnimationFrame(() => { raf=0; draw(interacting); });
      clearTimeout(settle);
      if (interacting) settle=setTimeout(() => request(false),120);
    }
    function viewState() {
      return {mode,auto,material:appearance.material,grayscale:appearance.grayscale,ground:appearance.ground,
        direction:Math.round(Math.atan2(light[0],light[2])/DEG),
        elevation:Math.round(clamp(Math.atan2(light[1],Math.hypot(light[0],light[2]))/DEG,10,85)),wireAvailable:isMesh,richMaterials:false};
    }
    function report() { Studio.sketchWorkbench?.syncViewer?.(viewState()); }
    function autoTick(time) {
      if (!auto || closed || document.hidden) {autoFrame=0;autoAt=0;return;}
      if (autoAt) camera.azimuth+=(time-autoAt)*.012;
      autoAt=time;request(false);autoFrame=requestAnimationFrame(autoTick);
    }
    function setAuto(next) {
      auto=!!next;
      if (!auto) {cancelAnimationFrame(autoFrame);autoFrame=0;autoAt=0;}
      else if (!autoFrame && !document.hidden) autoFrame=requestAnimationFrame(autoTick);
      report();
    }
    function resetView() {
      camera=JSON.parse(JSON.stringify(scene.camera));light=scene.light.slice();strength=1;
      setAuto(false);fields.forEach(f=>f());request(false);report();
    }
    function control(action,value) {
      if (closed) return;
      if (action==='mode' && ['orbit','light'].includes(value)) {if(value==='light')setAuto(false);setMode(value);}
      else if (action==='reset') {camera=JSON.parse(JSON.stringify(scene.camera));setAuto(false);request(false);}
      else if (action==='align') {scene.camera=JSON.parse(JSON.stringify(camera));request(false);}
      else if (action==='auto') setAuto(!auto);
      else if (action==='zoom') {camera.distance=clamp(camera.distance*(value>0?.9:1.1),5,20);request(false);}
      else if (action==='direction' && Number.isFinite(value)) {
        const radius=Math.max(1,Math.hypot(light[0],light[2])),a=clamp(value,-180,180)*DEG;
        light[0]=clamp(Math.sin(a)*radius,-8,8);light[2]=clamp(Math.cos(a)*radius,-8,8);fields.forEach(f=>f());request(false);
      } else if (action==='elevation' && Number.isFinite(value)) {
        const azimuth=Math.atan2(light[0],light[2]), elevation=clamp(value,10,85)*DEG;
        const radius=clamp(Math.hypot(...light),6,8), horizontal=radius*Math.cos(elevation);
        light[0]=Math.sin(azimuth)*horizontal;light[1]=radius*Math.sin(elevation);light[2]=Math.cos(azimuth)*horizontal;
        fields.forEach(f=>f());request(false);
      } else if (action==='material' && (['plaster','matte','normal'].includes(value) || isMesh && value==='wire')) {appearance.material=value;request(false);}
      else if (action==='grayscale') {appearance.grayscale=!!value;canvas.style.filter=appearance.grayscale?'grayscale(1)':'';}
      else if (action==='ground') {appearance.ground=!!value;request(false);}
      report();
    }
    function button(label, icon, fn, parent=controls) {
      const b=el('button','btn','',parent); b.type='button';
      const glyph=el('span','relight-icon',icon,b); glyph.setAttribute('aria-hidden','true');
      el('span','',t(label),b); b.onclick=fn; return b;
    }
    const orbit=button('orbit','↻',() => setMode('orbit'),quick);
    const place=button('place','☼',() => setMode('light'),quick);
    const compare=button('compare','▧',()=>{original.classList.toggle('is-visible');compare.setAttribute('aria-pressed',String(original.classList.contains('is-visible')));},quick);
    compare.classList.add('relight-compare');
    function setMode(next) {
      mode=next; orbit.setAttribute('aria-pressed',String(mode==='orbit')); place.setAttribute('aria-pressed',String(mode==='light'));
      hint.textContent=t(mode==='orbit'?'orbitHint':'lightHint');report();
    }
    const fields=[];
    // The legacy solid renderer used to put its only light marker in the hidden
    // top-down map. Keep a visible, draggable marker inside the shared viewer.
    const stageLamp=el('button','relight-stage-lamp','',stage);
    stageLamp.type='button';stageLamp.setAttribute('aria-label',t('dragLightHelp'));
    el('span','',t('dragLight'),stageLamp);
    // The marker is the light seen through the current camera, so it stays on the light as the model turns
    // (placed by compass direction alone, it sat front-left while the light was behind the solids).
    function syncStageLamp() {
      const box=canvas.getBoundingClientRect(),parent=stage.getBoundingClientRect();
      const b=basis(camera),f=Math.tan(camera.fov*DEG/2),aspect=box.width/Math.max(box.height,1);
      // A light outside the frame waits at the nearest edge, still there to grab.
      const d=light.map((x,i)=>x-b.eye[i]),z=Math.max(dot(d,b.forward),.1);
      const u=clamp((dot(d,b.right)/(z*f*aspect)+1)/2,.07,.93),v=clamp((1-dot(d,b.up)/(z*f))/2,.12,.95);
      stageLamp.style.left=(box.left-parent.left+box.width*u)+'px';
      stageLamp.style.top=(box.top-parent.top+box.height*v)+'px';
    }
    fields.push(syncStageLamp);
    // Dragging slides the light across the plane facing the camera through where it is now.
    function moveStageLamp(e) {
      const box=canvas.getBoundingClientRect(),b=basis(camera);
      const r=ray(camera,(e.clientX-box.left)/box.width,(e.clientY-box.top)/box.height,box.width/Math.max(box.height,1));
      const along=dot(r.direction,b.forward); if (along<=1e-3) return;
      const t=dot(light.map((x,i)=>x-r.origin[i]),b.forward)/along;
      const p=add(r.origin,mul(r.direction,t));
      light=[clamp(p[0],-8,8),clamp(p[1],3,10),clamp(p[2],-8,8)];
      fields.forEach(f=>f());request(true);report();
    }
    let lampPointer=null;
    stageLamp.onpointerdown=e=>{if(e.button!==0)return;e.stopPropagation();
      lampPointer=e.pointerId;stageLamp.setPointerCapture(e.pointerId);stageLamp.classList.add('is-dragging');
      setAuto(false);};
    stageLamp.onpointermove=e=>{if(lampPointer===e.pointerId){e.stopPropagation();moveStageLamp(e);}};
    stageLamp.onpointerup=stageLamp.onpointercancel=stageLamp.onlostpointercapture=()=>{
      lampPointer=null;stageLamp.classList.remove('is-dragging');request(false);};
    stageLamp.onkeydown=e=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
      e.preventDefault();e.stopPropagation();
      const vertical=e.key==='ArrowUp'||e.key==='ArrowDown';
      const current=viewState();
      control(vertical?'elevation':'direction',current[vertical?'elevation':'direction']+
        (e.key==='ArrowRight'||e.key==='ArrowUp'?5:-5));
    };
    const mapLabel=el('label','relight-map-label',t('map'),controls);
    const map=el('div','relight-map','',mapLabel);
    map.setAttribute('aria-label',t('map'));
    (isGenerated ? [{kind:'mesh',position:[0,scene.mesh.size[1]/2,0],size:scene.mesh.size,yaw:0}] : scene.objects).forEach(o=>{
      const mark=el('span','relight-map-object','',map);
      mark.style.left=((o.position[0]+8)/16*100)+'%';mark.style.top=((o.position[2]+8)/16*100)+'%';
      mark.style.width=(o.size[0]/16*100)+'%';mark.style.height=(o.size[2]/16*100)+'%';
      mark.style.borderRadius=o.kind==='box'?'2px':'50%';mark.style.transform='translate(-50%,-50%) rotate('+(-o.yaw)+'deg)';
    });
    const lamp=el('span','relight-map-lamp','☼',map);lamp.setAttribute('aria-hidden','true');
    fields.push(()=>{lamp.style.left=((light[0]+8)/16*100)+'%';lamp.style.top=((light[2]+8)/16*100)+'%';});
    function mapMove(e){const r=map.getBoundingClientRect();light[0]=clamp((e.clientX-r.left)/r.width*16-8,-8,8);light[2]=clamp((e.clientY-r.top)/r.height*16-8,-8,8);fields.forEach(f=>f());request(true);}
    map.onpointerdown=e=>{map.setPointerCapture(e.pointerId);mapMove(e);};
    map.onpointermove=e=>{if(map.hasPointerCapture(e.pointerId))mapMove(e);};
    map.onpointerup=map.onpointercancel=()=>request(false);
    function slider(key,min,max,step,get,set) {
      const label=el('label','relight-slider','',controls);
      el('span','',t(key),label); const output=el('output','','',label);
      const input=el('input','','',label); input.type='range'; input.min=min; input.max=max; input.step=step;
      input.setAttribute('aria-label',t(key));
      const sync=()=>{input.value=get();output.textContent=Number(get()).toFixed(1);}; fields.push(sync); sync();
      input.oninput=()=>{set(Number(input.value));fields.forEach(f=>f());request(true);};
    }
    slider('leftRight',-8,8,.1,()=>light[0],v=>light[0]=v);
    slider('frontBack',-8,8,.1,()=>light[2],v=>light[2]=v);
    slider('height',3,10,.1,()=>light[1],v=>light[1]=v);
    slider('brightness',0,2,.1,()=>strength,v=>strength=v);
    button('reset','↺',resetView,quick);
    function move(e) {
      const r=canvas.getBoundingClientRect();
      if(mode==='light') {
        const p=floorPoint(camera,(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height,r.width/r.height);
        if(p){light[0]=clamp(p[0],-8,8);light[2]=clamp(p[2],-8,8);fields.forEach(f=>f());}
      }else if(dragging){
        camera.azimuth-=(e.clientX-dragging.x)*.35; camera.elevation=clamp(camera.elevation+(e.clientY-dragging.y)*.25,8,80);
      }
      dragging={x:e.clientX,y:e.clientY,id:e.pointerId};request(true);report();
    }
    canvas.onpointerdown=e=>{if(dragging)return;canvas.setPointerCapture(e.pointerId);dragging={x:e.clientX,y:e.clientY,id:e.pointerId};move(e);};
    canvas.onpointermove=e=>{if(dragging&&dragging.id===e.pointerId)move(e);};
    canvas.onpointerup=canvas.onpointercancel=canvas.onlostpointercapture=()=>{dragging=null;request(false);};
    canvas.onwheel=e=>{e.preventDefault();camera.distance=clamp(camera.distance*Math.exp(e.deltaY*.001),5,20);request(true);};
    canvas.onkeydown=e=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-'].includes(e.key))return;
      e.preventDefault();
      if(e.key==='+'||e.key==='-')camera.distance=clamp(camera.distance+(e.key==='+'?-.5:.5),5,20);
      else if(mode==='light'){
        const axis=e.key==='ArrowLeft'||e.key==='ArrowRight'?0:2;
        light[axis]=clamp(light[axis]+(e.key==='ArrowLeft'||e.key==='ArrowUp'?-.25:.25),-8,8);fields.forEach(f=>f());
      }else if(e.key==='ArrowLeft'||e.key==='ArrowRight')camera.azimuth+=e.key==='ArrowLeft'?-5:5;
      else camera.elevation=clamp(camera.elevation+(e.key==='ArrowUp'?5:-5),8,80);
      request(true);
    };
    const resize=new ResizeObserver(()=>{syncStageLamp();request(false);});resize.observe(canvas);
    function visibility(){if(document.hidden){cancelAnimationFrame(raf);cancelAnimationFrame(autoFrame);raf=autoFrame=0;autoAt=0;clearTimeout(settle);}else{request(false);if(auto&&!autoFrame)autoFrame=requestAnimationFrame(autoTick);}}
    document.addEventListener('visibilitychange',visibility);
    canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true;cancelAnimationFrame(raf);raf=0;hint.textContent=t('unavailable');});
    canvas.addEventListener('webglcontextrestored',()=>{if(closed)return;gpu.dispose();try{gpu=makeRenderer(canvas,scene);lost=false;setMode(mode);request(false);}catch(e){hint.textContent=t('unavailable');}});
    Studio.relight.active={
      canvas,
      control,inspect:viewState,
      view(){return [Math.round(((camera.azimuth+180)%360+360)%360-180),Math.round(clamp(camera.elevation,10,80))];},
      snapshot(){draw(false);return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('empty snapshot')),'image/png'));},
      dispose(){closed=true;cancelAnimationFrame(raf);cancelAnimationFrame(autoFrame);clearTimeout(settle);resize.disconnect();document.removeEventListener('visibilitychange',visibility);gpu.dispose();canvas.width=canvas.height=1;host.classList.remove('relight','relight-mesh');host.replaceChildren();}
    };
    setMode('orbit'); fields.forEach(f=>f()); request(false);
  }
  Studio.relight={open,active:null,close(){const bench=Studio.sketchWorkbench;if(this.active&&bench?.active===this.active){bench.restoreControls();bench.key='';}if(this.active)this.active.dispose();this.active=null;},
    // Pure projection and budget functions are also used by the regression tests.
    basis,ray,floorPoint,resolution,valid};
})();
