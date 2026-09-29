// The cloud GLB stays in the saved course; the isolated viewer shares the exhibit renderer.
(function () {
  const MAX = 24 * 1024 * 1024;
  function valid(scene) {
    return !!(scene && scene.version === 1 && scene.method === 'cloud-glb' &&
      ['trellis2','pixal'].includes(scene.model) && typeof scene.glb === 'string' &&
      scene.glb.length <= MAX && scene.glb.length > 24 &&
      Number.isInteger(scene.bytes) && scene.bytes > 20 && scene.bytes <= 16 * 1024 * 1024 &&
      /^[a-f0-9]{64}$/.test(scene.sha256));
  }
  // Older studies (measured solids, a fruit still life, a small mesh) open in the same viewer as a GLB.
  function solids(scene) { return !!scene && scene.method !== 'cloud-glb' && !!Studio.relight?.valid?.(scene); }
  function open(host, scene, drawing) {
    const t = key => Studio.i18n.t('cloud3d.' + key);
    const note = document.createElement('p'); note.className='relight-note cloud-opening-note';
    note.textContent=host.id === 'sketch-workbench' ? t('opening') : solids(scene) ? t('approximation')
      : (scene?.model === 'pixal' ? 'Pixal3D' : 'TRELLIS.2') + ' · ' + t('approximation');
    const checked = scene?.camera_calibration?.status;
    if (checked === 'needs_review' || checked === 'teacher' || checked === 'matched')
      note.textContent += ' ' + t(checked === 'teacher' ? 'viewTeacher' : checked === 'matched' ? 'viewEstimated' : 'viewNeedsReview');
    if (!valid(scene) && !solids(scene)) { note.textContent=t('failed'); host.append(note); return; }
    const frame = document.createElement('iframe'); frame.title=t('title');
    frame.src='/viewer/3d/classroom.html'; frame.style.cssText='width:100%;height:var(--study-pane,590px);border:0;border-radius:20px;background:#f7f4ee';
    let closed=false, pending=null, timer=0;
    let studyState={ready:false,mode:'orbit',auto:false,material:'plaster',grayscale:false,ground:true,direction:-45,elevation:50,wireAvailable:true};
    // Still opening at 15 s, failed only at 2 minutes or on the viewer's own error; a late model puts the note back
    // (operator: on the slow link "cannot be shown" stood under a model that had appeared).
    const shown=note.textContent, slowTimer=setTimeout(()=>{note.textContent=t('slow');},15000);
    const readyTimer=setTimeout(()=>{note.textContent=t('failed');},120000);
    const listener = event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
      if (event.data?.type === 'scene-ready' || event.data?.type === 'scene-error') { clearTimeout(readyTimer); clearTimeout(slowTimer); }
      if (event.data?.type === 'scene-ready') {note.textContent=host.id === 'sketch-workbench' ? '' : shown;studyState.ready=true;Studio.sketchWorkbench?.syncViewer?.(studyState);frame.contentWindow.postMessage({type:'study-control',action:'state'},location.origin);}
      if (event.data?.type === 'scene-error') {note.textContent=t('failed');studyState.ready=false;Studio.sketchWorkbench?.syncViewer?.(studyState);}
      if (event.data?.type === 'study-state') {studyState={...studyState,...event.data.state};Studio.sketchWorkbench?.syncViewer?.(studyState);}
      if (event.data?.type === 'snapshot' && pending) {
        clearTimeout(timer); const job=pending; pending=null;
        event.data.blob instanceof Blob ? job.resolve(event.data.blob) : job.reject(new Error('Empty snapshot'));
      }
    };
    window.addEventListener('message',listener);
    frame.onload=()=>{if (!closed) frame.contentWindow.postMessage({type:'classroom-scene',scene,image:new URL(drawing.url, location.href).href,language:Studio.i18n.lang},location.origin);};
    if (host.id !== 'review-output-content') {
      const views=document.createElement('div'); views.className='sketch-pair';
      const original=document.createElement('figure'), caption=document.createElement('figcaption'), img=document.createElement('img');
      caption.textContent=Studio.i18n.t('relight.original'); img.src=drawing.url; img.alt=caption.textContent;
      original.append(caption,img);
      const stage=document.createElement('figure'), label=document.createElement('figcaption');
      label.textContent=t(host.id === 'sketch-workbench' ? 'workbenchTitle' : 'title');
      stage.append(label,frame); if (host.id === 'sketch-workbench') stage.append(note);
      views.append(original,stage); host.append(views);
    } else host.append(frame);
    if (host.id !== 'sketch-workbench') host.append(note);
    Studio.relight.active={
      control(action,value){if(!closed)frame.contentWindow?.postMessage({type:'study-control',action,value},location.origin);},
      inspect(){return {...studyState};},
      // The angle the model is seen from now, in the model's own terms, as the view check saves it.
      view(){
        const orbit=frame.contentDocument?.querySelector('.viewport')?.dataset.orbit?.split(',').map(Number);
        return orbit && orbit.length === 3 && orbit.every(Number.isFinite) ? turned(shownBase(scene), orbit) : null;
      },
      snapshot(){
        if (pending) return Promise.reject(new Error('Snapshot already running'));
        return new Promise((resolve,reject)=>{pending={resolve,reject};frame.contentWindow.postMessage({type:'snapshot'},location.origin);
          timer=setTimeout(()=>{pending=null;reject(new Error('Snapshot timed out'));},5000);});
      },
      dispose(){closed=true;clearTimeout(timer);clearTimeout(readyTimer);clearTimeout(slowTimer);pending?.reject(new Error('Viewer closed'));pending=null;
        window.removeEventListener('message',listener);frame.remove();host.replaceChildren();}
    };
  }
  // What the viewer turns the model by (studio/showcase_3d/viewer.js calibratedBase, whose saved
  // sample angles all sit in their own scenes), and the same camera basis view_calibration.py draws with.
  function shownBase(scene) {
    if (solids(scene)) return [scene.camera.azimuth, 90 - scene.camera.elevation];
    const base=scene.camera_base;
    return Array.isArray(base) && base.length === 2 && base.every(Number.isFinite) ? base : scene.model === 'pixal' ? [180,75] : [45,75];
  }
  // In the classroom the viewer turns the model about the upright only, by the base's yaw, and starts the
  // camera at the base's height (viewer.js loadCard). So a camera orbited to (yaw, polar) sees
  // the model from the base's yaw plus its own, at its own height: saving an untouched view keeps the base.
  function turned(base, orbit) {
    const yaw=((base[0]+orbit[0])%360+540)%360-180;
    return [Math.round(yaw), Math.min(179,Math.max(1,Math.round(orbit[1])))];
  }
  Studio.cloudRelight={valid,solids,open,turned};
})();

// The same compact classroom controls drive either a saved GLB or an older local study.
function sketchViewerControls(stage, active) {
  if (!active?.control) return null;
  const t=key=>Studio.i18n.t('cloud3d.viewer.'+key);
  const make=(tag,cls,parent)=>{const node=document.createElement(tag);node.className=cls;if(parent)parent.append(node);return node;};
  const root=make('div','sketch-viewer-ui',stage);
  let state={ready:true,mode:'orbit',auto:false,material:'plaster',grayscale:false,ground:true,direction:-45,elevation:50,wireAvailable:true,richMaterials:true,...active.inspect?.()};
  const buttons=[];
  function action(parent,key,command,value) {
    const b=make('button','',parent);b.type='button';b.textContent=t(key);b.dataset.action=command;
    b.onclick=()=>{
      const next=command==='auto'?!state.auto:command==='mode'||command==='material'||command==='zoom'?value:null;
      if(command==='mode')state.mode=value;
      if(command==='auto')state.auto=next;
      if(command==='material')state.material=value;
      active.control(command,next);sync(state);
    };
    buttons.push(b);return b;
  }
  // Two view buttons only (operator): dragging the model turns it and dragging the lamp
  // moves the light in either viewer, so the viewer stays in its turning mode and needs no mode switch.
  if(state.mode!=='orbit'){state.mode='orbit';active.control('mode','orbit');}
  // Light on the left, what the model looks like on the right, and the four view actions in one column
  // between them (operator), rather than a loose row under the model.
  const settings=make('div','sketch-viewer-settings',root);
  const light=make('section','sketch-setting-card',settings);light.setAttribute('aria-label',t('lightSection'));
  make('strong','',light).textContent=t('lightSection');
  const fields={};
  for(const [name,min,max] of [['direction',-180,180],['elevation',10,85]]) {
    const label=make('label','sketch-light-slider',light);
    make('span','',label).textContent=t(name);
    const input=make('input','',label);input.type='range';input.min=min;input.max=max;input.step=1;
    const output=make('output','',label);fields[name]={input,output};
    input.oninput=()=>{state[name]=Number(input.value);output.textContent=state[name]+'°';active.control(name,state[name]);};
  }
  const center=make('div','sketch-viewer-center',settings);
  const viewActions=make('div','sketch-view-actions',center);
  action(viewActions,'auto','auto');
  action(viewActions,'reset','reset');
  const checks=make('div','sketch-viewer-checks',center);
  const display=make('section','sketch-setting-card',settings);display.setAttribute('aria-label',t('display'));
  make('strong','',display).textContent=t('display');
  const materials=make('div','sketch-materials',display);materials.setAttribute('role','group');materials.setAttribute('aria-label',t('material'));
  const materialButtons={};
  for(const name of ['plaster','matte','marble','wood','metal','glass','denim','rust','chocolate','normal','wire'])
    materialButtons[name]=action(materials,name,'material',name);
  const toggles={};
  // Two on/off buttons: pressed shows as a tint and a check, the same as the view actions beside them.
  for(const name of ['grayscale','ground']){
    const b=make('button','sketch-toggle',checks);b.type='button';b.dataset.toggle=name;
    make('span','',b).textContent=t(name);toggles[name]=b;
    b.onclick=()=>{state[name]=!state[name];active.control(name,state[name]);sync(state);};
  }
  const foot=make('p','sketch-viewer-foot',root);foot.textContent=t('hint');
  function sync(next) {
    state={...state,...next};
    for(const b of buttons){
      const pressed=b.dataset.action==='mode'?b.textContent===t(state.mode):b.dataset.action==='auto'?state.auto:
        b.dataset.action==='material'?Object.entries(materialButtons).some(([name,node])=>node===b&&name===state.material):false;
      b.setAttribute('aria-pressed',String(pressed));
      b.disabled=state.ready===false;
    }
    for(const [name,button] of Object.entries(materialButtons)){
      const unsupported=state.richMaterials===false && !['plaster','matte','normal','wire'].includes(name);
      button.disabled=state.ready===false || unsupported || name==='wire' && state.wireAvailable===false;
      button.title=unsupported?t('materialUnavailable'):name==='wire' && state.wireAvailable===false?t('wireUnavailable'):'';
    }
    for(const name of ['direction','elevation']){fields[name].input.value=String(state[name]);fields[name].output.textContent=state[name]+'°';fields[name].input.disabled=state.ready===false;}
    for(const name of ['grayscale','ground']){toggles[name].setAttribute('aria-pressed',String(!!state[name]));toggles[name].disabled=state.ready===false;}
  }
  sync(state);
  return {root,sync,viewActions};
}

// Saved results are read on demand; navigation invalidates unfinished reads.
Studio.sketchWorkbench = {
  epoch: 0, key: '', active: null, controls: null, viewerUI: null, loading: null, loadingTimer: 0, hasModelFor: null, reloading: false, refreshError: '', generationError: '', generationProgress: '', selectedActivity: new Map(),
  syncViewer(state) { this.viewerUI?.sync(state); },
  syncHeading() {
    const t=key=>Studio.i18n.t(key);
    document.getElementById('piece-title').textContent=t('picture.title.form');
    document.getElementById('piece-hint').textContent=t('picture.hint.form');
  },
  restoreControls() {
    const buddy=document.getElementById('buddy'), process=document.getElementById('process');
    const choice=document.getElementById('cloud3d-choice'), actions=document.getElementById('buddy-actions');
    if (!buddy || !process || !choice || !actions) return;
    if (choice.parentNode !== buddy) buddy.insertBefore(choice,process);
    if (actions.parentNode !== buddy) buddy.insertBefore(actions,process);
    this.controls=null;this.viewerUI=null;
  },
  mountControls(host, hasModel=false) {
    if (Studio.state.settings.entrance !== 'sketch') return;
    const pair=[...host.children].find(el=>el.className==='sketch-pair' || el.className==='relight-views');
    const stage=pair?.children[1];
    if (!stage) return;
    this.restoreControls();
    stage.classList.add('sketch-viewer-panel');
    if (pair.className === 'relight-views') {
      const label=document.createElement('figcaption'); label.textContent=Studio.i18n.t('cloud3d.workbenchTitle');
      stage.insertBefore(label,stage.children[0]);
      for (const name of ['relight-note','relight-hint','relight-controls']) {
        const item=[...host.children].find(el=>el.className===name);
        // The shared viewer tools replace the old renderer's own; only its note stays.
        if (item && name === 'relight-note') stage.append(item);
        else if (item) host.removeChild(item);
      }
    }
    const controls=document.createElement('div'); controls.className='sketch-controls';
    document.getElementById('btn-open').hidden=true;
    document.getElementById('btn-next').hidden=true;
    controls.append(document.getElementById('buddy-actions')); stage.append(controls);
    this.controls=controls;
    this.viewerUI=sketchViewerControls(stage,this.active);
    if (hasModel) document.getElementById('primary-text').textContent=Studio.i18n.t('cloud3d.regenerate');
    this.syncNotice(host);
  },
  syncNotice(host, message) {
    const pair=[...host.children].find(el=>el.className==='sketch-pair'||el.className==='relight-views');
    const stage=pair?.children[1]; if (!stage) return;
    let notice=[...stage.children].find(el=>el.className==='sketch-generation-status');
    const text=message ?? (this.refreshError || this.generationError || (this.reloading ? Studio.i18n.t('cloud3d.opening')
      : Studio.state.making==='sketch-to-3d' && this.hasModelFor===Studio.session.currentDrawing()?.id
        ? Studio.i18n.t('cloud3d.regenerating') + (this.generationProgress ? ' · ' + this.generationProgress : '') : ''));
    if (!text) { if (notice) stage.removeChild(notice); return; }
    if (!notice) { notice=document.createElement('p'); notice.className='sketch-generation-status';notice.setAttribute('role','status');stage.append(notice); }
    notice.textContent=text;
    if (this.refreshError && !this.reloading) {
      const retry=document.createElement('button');retry.type='button';retry.className='btn quiet';
      retry.textContent=Studio.i18n.t('cloud3d.retryOpen');retry.onclick=()=>this.refreshLatest();notice.append(retry);
    }
  },
  close() {
    this.epoch++; this.key=''; this.hasModelFor=null; this.reloading=false; this.refreshError=''; this.generationError=''; this.generationProgress='';
    clearTimeout(this.loadingTimer); this.loadingTimer=0;
    this.loading?.abort(); this.loading=null;
    this.restoreControls();
    if (this.active && Studio.relight.active === this.active) Studio.relight.close();
    this.active=null;
    const host=document.getElementById('sketch-workbench');
    if (host) { host.hidden=true; host.replaceChildren(); }
    document.getElementById('creation-workspace').classList.remove('has-sketch-workbench','sketch-study');
  },
  beginGeneration() {
    this.generationError=''; this.generationProgress='';
    const host=document.getElementById('sketch-workbench');
    if (this.active && host && !host.hidden) this.syncNotice(host);
    this.watchProgress();
  },
  // The first build has no model to keep on screen, so the empty panel carries the progress itself:
  // what is happening, the seconds, a bar and the usual time, each second until the job ends.
  watchProgress() {
    clearInterval(this.progressTimer);
    let first=true;
    const paint=()=>{
      const panel=document.querySelector('#sketch-workbench .sketch-empty'), running=Studio.state.making==='sketch-to-3d';
      if (!running && !first) { clearInterval(this.progressTimer); this.progressTimer=0; panel?.querySelector('.sketch-progress')?.remove(); return; }
      first=false;
      if (!panel || !Studio.makeStatus) return;
      let box=panel.querySelector('.sketch-progress');
      if (!box) { box=document.createElement('div'); box.className='sketch-progress'; panel.append(box); }
      box.innerHTML=Studio.makeStatus.html();
    };
    paint(); this.progressTimer=setInterval(paint,1000);
  },
  generationTick(line) {
    this.generationProgress=line;
    const host=document.getElementById('sketch-workbench');
    if (this.active && host && !host.hidden) this.syncNotice(host);
  },
  generationFailed(message) {
    const host=document.getElementById('sketch-workbench');
    if (this.active && host && !host.hidden) {
      this.generationError=message;
      this.syncNotice(host);
    } else {
      const drawing=Studio.session.currentDrawing();
      if (drawing) this.waiting(drawing,message);
    }
  },
  refreshLatest() { this.generationError='';this.selectedActivity.delete(this.key); return this.refresh({reload:true}); },
  async refresh({reload=false}={}) {
    const st=Studio.state, drawing=Studio.session.currentDrawing();
    if (st.mode !== 'move' || !drawing || !st.courseId || document.getElementById('app').dataset.courseView !== 'create') { this.close(); return; }
    const key=[st.session,st.courseId,drawing.id,Studio.i18n.lang].join(':');
    if (this.key === key && !reload) {
      const host=document.getElementById('sketch-workbench');
      if (!host.hidden) {
        this.syncHeading();
        const copy=host.children[0]?.className === 'sketch-pair' ? host.children[0].children[1]?.children[1] : null;
        if (copy?.className === 'sketch-empty-copy' && copy.dataset.opening !== '1')
          copy.textContent=st.making === 'sketch-to-3d' ? Studio.i18n.t('cloud3d.generating') : copy.dataset.base;
        this.syncNotice(host);
      }
      return;
    }
    const host=document.getElementById('sketch-workbench');
    const preserve=reload && this.key===key && !!this.active && !host.hidden;
    if (preserve) {
      this.epoch++;clearTimeout(this.loadingTimer);this.loading?.abort();this.loading=null;
      this.reloading=true; this.refreshError='';
      this.syncNotice(host,Studio.i18n.t('cloud3d.opening'));
    } else this.close();
    this.key=key; const epoch=this.epoch;
    const loading=new AbortController(); this.loading=loading;
    this.loadingTimer=setTimeout(()=>loading.abort(),180000);
    if (st.settings.entrance === 'sketch' && !preserve) this.waiting(drawing,Studio.i18n.t('cloud3d.opening'),true);
    try {
      const course=await Studio.portfolio.api('/'+encodeURIComponent(st.courseId),{signal:loading.signal});
      if (epoch !== this.epoch) return;
      const versions=course.activities.filter(a=>a.summary.kind==='relight' && a.drawings.includes(drawing.id));
      const selectedId=this.selectedActivity.get(key);
      const result=versions.find(a=>a.id===selectedId)||versions.at(-1);
      if (!result) {
        if (preserve) { this.refreshError=Studio.i18n.t('cloud3d.refreshFailed');this.syncNotice(host); }
        else if (st.settings.entrance === 'sketch') this.waiting(drawing, '生成立体作品后，就可以在这里转动形体、移动小灯。');
        return;
      }
      const path='/'+encodeURIComponent(st.courseId)+'/activities/'+encodeURIComponent(result.id);
      let saved=this.saved.get(path);
      if (!saved) {
        // A saved 3D result is several megabytes: say it is coming rather than show nothing while it does.
        if (!preserve) this.waiting(drawing, Studio.i18n.t('cloud3d.opening'), true);
        saved=await Studio.portfolio.api(path,{signal:loading.signal});
        if (epoch !== this.epoch) return;
        this.remember(path, saved);
      }
      const scene=saved?.outputs?.scene;
      if (preserve && !(scene?.method==='cloud-glb' ? Studio.cloudRelight.valid(scene) : Studio.relight.valid(scene))) {
        this.saved.delete(path);
        this.refreshError=Studio.i18n.t('cloud3d.refreshFailed');this.syncNotice(host);return;
      }
      this.restoreControls();
      if (preserve) Studio.relight.close();
      host.replaceChildren(); host.hidden=false;
      const workspace=document.getElementById('creation-workspace');
      workspace.classList.add('has-sketch-workbench');
      workspace.classList.toggle('sketch-study',st.settings.entrance === 'sketch');
      this.syncHeading();
      Studio.relight.open(host,scene,drawing); this.active=Studio.relight.active;
      if (!this.active && st.settings.entrance === 'sketch') { this.waiting(drawing,Studio.i18n.t('cloud3d.workbenchFailed')); return; }
      this.hasModelFor=drawing.id;
      this.refreshError='';
      // After a quick solids study, the next "regenerate" offers the actual 3D model by default.
      // The teacher can still choose the quick automatic route explicitly.
      const modelChoice=document.getElementById('cloud3d-model');
      if (scene?.method === 'geometric-approximation' && modelChoice.value === 'auto') modelChoice.value='trellis2';
      this.mountControls(host, true, versions, result.id, scene);
      if (this.active?.view) this.keepView(host, path, saved, epoch);
    } catch (_) {
      if (epoch === this.epoch) {
        if (preserve) { this.refreshError=Studio.i18n.t('cloud3d.refreshFailed');this.syncNotice(host); }
        else if (st.settings.entrance === 'sketch') this.waiting(drawing,Studio.i18n.t('cloud3d.workbenchFailed'),false,true);
        else this.close();
      }
    } finally {
      if (this.loading === loading) {
        clearTimeout(this.loadingTimer); this.loadingTimer=0; this.loading=null;
        if (preserve) { this.reloading=false; if (this.active) this.syncNotice(host); }
      }
    }
  },
  // Coming back to a drawing opens its model at once: the last few are kept, newest last.
  saved: new Map(),
  remember(path, saved) {
    this.saved.delete(path); this.saved.set(path, saved);
    while (this.saved.size > 4) this.saved.delete(this.saved.keys().next().value);
  },
  waiting(drawing, text, opening=false, retry=false) {
    const host=document.getElementById('sketch-workbench'); this.restoreControls(); host.replaceChildren(); host.hidden=false;
    const workspace=document.getElementById('creation-workspace');
    workspace.classList.add('has-sketch-workbench');
    workspace.classList.toggle('sketch-study',Studio.state.settings.entrance === 'sketch');
    this.syncHeading();
    const pair=document.createElement('div'); pair.className='sketch-pair';
    const original=document.createElement('figure'), img=document.createElement('img'), caption=document.createElement('figcaption');
    caption.textContent=Studio.i18n.t('relight.original'); img.src=drawing.url; img.alt=caption.textContent; original.append(caption,img);
    const empty=document.createElement('figure'); empty.className='sketch-empty';
    const label=document.createElement('figcaption'); label.textContent=Studio.i18n.t('cloud3d.workbenchTitle');
    const placeholder=document.createElement('div'); placeholder.className='sketch-empty-copy'; placeholder.textContent=text;
    placeholder.dataset.base=text; placeholder.dataset.opening=opening ? '1' : '0';
    empty.append(label,placeholder);
    if (retry) {
      const button=document.createElement('button'); button.type='button'; button.className='btn quiet';
      button.textContent=Studio.i18n.t('cloud3d.retryOpen');
      button.onclick=()=>{this.close();this.refresh();};
      empty.append(button);
    }
    pair.append(original,empty); host.append(pair);
    if (!opening) this.mountControls(host);
  },
  // The teacher has the last word on which way the model faces: the view check can pick one from behind.
  keepView(host, path, saved, epoch) {
    // The sketch viewer's tools no longer offer "compare from this angle"; it did not work there.
    if (this.viewerUI) return;
    const t=key=>Studio.i18n.t('cloud3d.'+key);
    const button=this.viewerUI?.align || document.createElement('button'); button.type='button'; button.className='btn quiet keep-view';
    button.textContent=t('keepView'); if(!this.viewerUI)(this.controls || host).append(button);
    button.onclick=async()=>{
      const base=this.active?.view(); if (!base) return;
      button.disabled=true;
      try {
        await Studio.portfolio.api(path+'/view', { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({camera_base:base}) });
        const scene=saved.outputs.scene;
        if (scene.method === 'cloud-glb') {
          const check=scene.camera_calibration;
          scene.camera_base=base;
          scene.camera_calibration={status:'teacher', check: check?.status === 'teacher' ? check.check : check};
        } else {
          scene.camera.azimuth=base[0];scene.camera.elevation=base[1];
        }
        if (epoch === this.epoch) { this.close(); this.refresh(); }
      } catch (_) { button.disabled=false; button.textContent=t('keepViewFailed'); }
    };
  }
};
