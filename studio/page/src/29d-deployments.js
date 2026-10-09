// Preview readiness for the selected setup; applying preserves existing editors.
(function () {
  const S=Studio, st=S.state, $=id=>document.getElementById(id), t=(k,v)=>S.i18n.t('deployment.'+k,v);
  let report=null, data=null, target=null, saving=false, checking=false, epoch=0, initialized=false;
  function setupName(id) { const key='deployment.'+id, label=S.i18n.t(key); return label===key ? (data?.options?.find(x=>x.id===id)?.name || id) : label; }
  function render() {
    const toggle=$('deployment-options'); toggle.replaceChildren();
    for(const option of (data?.options || [])) {
      const name=option.id, button=element('button','',setupName(name));
      button.id='deployment-'+name; button.type='button';
      button.addEventListener('click',()=>choose(name)); toggle.append(button);
      button.setAttribute('aria-pressed',String(name===target));
      button.disabled=saving || !data;
    }
    // One deployment (StepFun First): with nothing to choose
    // between, the switch and Apply are hidden and the panel is a status board.
    // Driven by what the service lists, so a second option would bring them back.
    const single=(data?.options || []).length<2;
    toggle.hidden=single; $('deployment-apply').hidden=single;
    $('deployment-check').disabled=saving || checking || !data;
    $('deployment-apply').disabled=saving || checking || !data || target===data.selected;
    $('deployment-active').textContent=data?t('active',{name:setupName(data.selected)}):'';
    $('deployment-detail').textContent=t('description.'+target);
    $('deployment-session').textContent=st.session && st.capabilities?.deployment ? t('session',{name:setupName(st.capabilities.deployment)}) : '';
    renderCheck();
  }
  const groups=[
    {id:'understand',slots:['vlm.front','vlm.studio','vlm.sketch']},
    {id:'safety',slots:['vlm.director','safety.image','safety.reader','vlm.figure.look','vlm.teacher']},
    {id:'create',slots:['vlm.creation','video.online','video.animation','mesh.portrait','mesh.portrait.trellis2','vlm.figure','image.book']},
    {id:'voice',slots:['tts.studio','tts.child','speech.in']}
  ];
  function element(tag, cls, text) {
    const el=document.createElement(tag); if(cls) el.className=cls;
    if(text!==undefined) el.textContent=text;
    return el;
  }
  function renderCheck() {
    const list=$('deployment-checks'), overview=$('deployment-overview');
    list.replaceChildren(); overview.replaceChildren();
    const components=report?.components || [];
    overview.hidden=!components.length;
    if(!components.length) return;
    const counts={ready:0,unavailable:0,unknown:0};
    components.forEach(c=>counts[c.status in counts?c.status:'unknown']++);
    for(const status of ['total','ready','unavailable','unknown']) {
      const tile=element('div','deployment-stat'); tile.dataset.status=status;
      tile.append(element('span','',t(status==='total'?'total':'check.'+status)),
        element('strong','',String(status==='total'?components.length:counts[status])));
      overview.append(tile);
    }
    const known=groups.flatMap(group=>group.slots);
    const icons={understand:'chat',safety:'check',create:'spark',voice:'voice',other:'settings'};
    for(const group of groups.concat([{id:'other',slots:components.filter(c=>!known.includes(c.slot)).map(c=>c.slot)}])) {
      const members=components.filter(c=>group.slots.includes(c.slot));
      if(!members.length) continue;
      const section=element('li','deployment-group'); section.dataset.group=group.id;
      const header=element('div','deployment-group-head');
      const icon=element('span','deployment-group-icon'); icon.setAttribute('aria-hidden','true');
      icon.innerHTML='<svg><use href="#i-'+icons[group.id]+'"/></svg>';
      const heading=element('h4','',t('group.'+group.id));
      const ready=members.filter(c=>c.status==='ready').length;
      const count=element('span','deployment-group-count',t('groupCount',{ready,total:members.length}));
      header.append(icon,heading,count);
      const meter=element('div','deployment-meter'); meter.setAttribute('aria-hidden','true');
      members.forEach(c=>{const segment=element('span');segment.dataset.status=c.status;meter.append(segment);});
      const rows=element('ul','deployment-components');
      for(const component of members) {
        const baseSlot=component.slot.startsWith('mesh.portrait')?'mesh.portrait':component.slot;
        const row=element('li'); row.dataset.status=component.status;
        const top=element('div','deployment-component-head');
        top.append(element('strong','',t('slot.'+baseSlot)+(component.optional?' · '+t('optional'):'')),element('span','deployment-badge',t('check.'+component.status)));
        const purpose=element('p','deployment-purpose',t('purpose.'+(known.includes(component.slot)?baseSlot:'other')));
        const model=element('small','deployment-model',component.model);
        const details=element('details','deployment-component-details');
        const summary=element('summary','',t('moreInfo'));
        const impact=element('p','deployment-impact',t('impactPrefix')+t('impact.'+(known.includes(component.slot)?baseSlot:'other')));
        const note=element('small','',t('reason.'+component.reason));
        details.append(summary,impact,note);
        const provenance=[component.provider,component.location,component.source].filter(Boolean);
        if(provenance.length) details.append(element('p','deployment-provenance',provenance.join(' · ')));
        if(report.checked_at) details.append(element('small','',String(report.checked_at)));
        row.append(top,purpose,model,details);
        const caution=component.model==='VoxCPM2'?'voice':component.provider==='fal.ai' && component.model==='pixal'?'pixal':null;
        if(caution) row.append(element('p','deployment-purpose',t('caution.'+caution)));
        rows.append(row);
      }
      section.append(header,meter,rows); list.append(section);
    }
  }
  async function check() {
    if(saving || !data || !st.transport.checkDeployment) return;
    const token=++epoch, selected=target, sid=st.session;
    checking=true; report=null; render();
    $('deployment-status').textContent=t('checking');
    try {
      const result=await st.transport.checkDeployment(selected);
      if(token!==epoch || target!==selected) return;
      report={...result, checked_at:result.checked_at || new Date().toLocaleString()};
      $('deployment-status').textContent=t(report.ready?'checked':'notReady')+' '+t('checkedAt',{time:report.checked_at});
      if(sid && st.transport.deployments) {
        const current=await st.transport.deployments(sid);
        if(token!==epoch || target!==selected || sid!==st.session) return;
        if(current.session) {st.capabilities=current.session; S.voice?.configure(current.session); S.bus.emit('capabilities');}
      }
    } catch(_) { if(token===epoch) $('deployment-status').textContent=t('failed'); }
    finally { if(token===epoch) {checking=false;render();} }
  }
  async function choose(name) {
    if(saving || !data || name===target || !data.options?.some(x=>x.id===name)) return;
    target=name; report=null; await check(); render();
  }
  async function refresh() {
    if(saving || checking) return;
    const token=++epoch, sid=st.session;
    try {
      const result=await st.transport.deployments(sid);
      if(token!==epoch || sid!==st.session) return;
      data=result; target=target || data.selected;
      if(result.session) {st.capabilities=result.session; S.voice?.configure(result.session);}
      render();
    } catch(_) {if(token===epoch) $('deployment-status').textContent=t('failed');}
  }
  async function apply() {
    if(saving || checking || !data || target===data.selected) return;
    const selected=target;
    saving=true; ++epoch; report=null; render(); $('deployment-status').textContent=t('checking');
    try {
      data=await st.transport.selectDeployment(selected);
      report=data.check || null;
      $('deployment-status').textContent=t(data.switched===false?'blocked':'saved');
    } catch(_) { $('deployment-status').textContent=t('failed'); }
    finally {saving=false;render();}
  }
  async function open() {await refresh(); await check();}
  S.deployments={refresh,apply,render,choose,check,open,init(){
    if(initialized || !st.transport?.deployments) return;
    initialized=true; $('deployment-panel').hidden=false;
    $('deployment-apply').addEventListener('click',apply);
    $('deployment-check').addEventListener('click',check);
    S.bus.on('session',()=>{if(st.capabilities) S.voice?.configure(st.capabilities); refresh();});
    S.bus.on('ended',refresh); S.bus.on('language',render);
    refresh();
  }};
})();
