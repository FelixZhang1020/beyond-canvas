"""Build the isolated console review from current renderers and synthetic fixtures."""
from pathlib import Path
import json, re

page = Path(__file__).resolve().parents[1] / 'studio/showpiece/page'
def module(name):
    s = (page / name).read_text()
    names = re.findall(r'^export (?:function|const) (\w+)', s, re.M)
    s = re.sub(r'^import .*;\n', '', s, flags=re.M).replace('export ', '')
    return 'const {' + ','.join(names) + '}=(()=>{\n' + s + '\nreturn {' + ','.join(names) + '};})();\n'

shared = (page / 'floating-console.js').read_text().replace('window.self !== window.top || ', '').replace('localStorage', 'reviewStorage')
setup = '''const data=__DATA__; const reviewStorage={getItem:()=>null,setItem(){},removeItem(){}};
const machine={cpu_percent:11.3,memory_used_gb:40.6,memory_total_gb:68.7,gpu:null,host:'review-host'};
const roster=__ROSTER__;
const active=data.state==='running';
const stages=[{name:'studio-safety',status:'gate_pass',seconds:0.5,events:2},{name:'art-feedback',status:active?'running':'done',seconds:active?null:2.6,events:2},{name:'rubric',status:active?'queued':'gate_pass',seconds:active?null:0.4,events:1}];
const sample={id:'classroom:sample',source:'classroom',skill:'art-feedback',status:active?'running':'done',done:!active,processes:active?stages.slice(0,2):stages,events:stages.filter(p=>p.status!=='queued').map(p=>({stage:p.name,status:p.status,seconds:p.seconds})),parts:{request:active?'running':'done',skills:'art-feedback',evals:active?'未报告':'gate_pass'}};
window.fetch=async()=>{if(data.state==='offline')throw Error('offline');return {ok:true,json:async()=>({machine,parts:roster,sources:['classroom','showpiece'],jobs:data.state==='idle'?[]:[sample]})}};

'''.replace('__ROSTER__', json.dumps([{k:s[k] for k in ('id','name')} for s in json.loads((page/'harness-roster.json').read_text())['stations']], ensure_ascii=False))
helpers = '''const $=id=>document.getElementById(id);function el(tag,attrs={},...children){const n=document.createElement(tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);for(const c of children)n.append(c instanceof Node?c:document.createTextNode(String(c)));return n;}
const T=__STRINGS__;const t=k=>data.id==='harness'&&k==='console'?'harness console':T[k]||k;
'''.replace('__STRINGS__', json.dumps(json.loads((page/'strings.json').read_text())['zh'], ensure_ascii=False))
rail = 'function rail() {' + (page/'harness.js').read_text().split('function rail() {', 1)[1].split('\nfunction shell()', 1)[0]
show = '''const ops=makeConsole({el,t,$});window.Backstage.attach(ops.build());ops.stats(machine);
const events=data.state==='replay'?[{kind:'think',step:1,text:'先清点构件，再观察承托与结构。'},{kind:'act',step:2,skill:'model-anatomy',tool:'inventory',seconds:14.2,text:'ANATOMY 8170 pieces',files:[]},{kind:'act',step:3,skill:'structure-tour',tool:'tour',seconds:90.7,text:'TOUR 4 segments',files:['tour.mp4']},{kind:'final',step:4,text:'已完成结构观察。'}]:[];
ops.setRun({request:'查看大殿结构（示意）'});events.forEach(e=>ops.note(e,e.step*2));ops.update({events,elapsed:8,beat:data.state==='running'?{phase:'tool',skill:'structure-tour',tool:'tour',seconds:18}:null});
if(data.state==='replay')window.Backstage.activity={label:'录播',detail:'4 步'};
window.Backstage.context({label:data.state==='running'?'本页实时任务 · 样例':'录播 · 样例',status:data.state==='running'?'running':'idle',done:data.state!=='running',parts:{request:'received',tools:String(events.filter(e=>e.kind==='act').length),skills:'model-anatomy, structure-tour'}});
'''
harness = '''window.Backstage.attach(rail());
const parts=['Request','Agent loop','Tools','Skills','Hook: before a tool','Hook: after a tool','Hook: on stop','Subagent','Permissions','Memory','Transcript','Evals'];
$('parts').replaceChildren(...parts.map((s,i)=>el('p',{class:data.state==='running'&&i===2?'lit':''},s)));
$('log').replaceChildren(el('p',{},'+0:00 ',data.state==='running'?'Tool · vlm.studio → 模型调用（演示）':'按上面的一个技能开始'));
if(data.state==='running')window.Backstage.activity={label:'Harness · 演示',detail:'聊聊你的画 · 3/12 · 工具调用'};
window.Backstage.context({label:'Harness · 演示样例',skill:'art-feedback',status:data.state==='running'?'playing':'idle',done:true,mode:'simulation',parts:Object.fromEntries(roster.map((s,i)=>[s.id,data.state==='running'?(i===2?'current':i<2?'visited':'not_started'):'not_started'])),processes:data.state==='running'?parts.slice(0,3).map((name,i)=>({name,status:i===2?'current':'visited',seconds:null,events:1})):[]});
'''
finish = '''const host=document.querySelector('#backstage-console'),shadow=host.shadowRoot;
const adapt=document.createElement('style');adapt.textContent=':host{position:relative!important;display:block!important;right:auto!important;bottom:auto!important;width:100%!important;max-width:none!important}#panel{width:100%!important;max-height:none!important;height:auto!important}#resize,#move,#close,#toggle{pointer-events:none}';shadow.append(adapt);
const notes=document.createElement('style');notes.textContent=':host([data-gaps]) #panel{outline:2px dashed #5ed6a6;outline-offset:-16px}@media(max-width:600px){:host([data-gaps]) #panel{outline-offset:-12px}}:host([data-gaps]) header,:host([data-gaps]) #metrics,:host([data-gaps]) h3,:host([data-gaps]) #local,:host([data-gaps]) slot{outline:1px dashed #ffad71}';shadow.append(notes);
const light=document.createElement('style');light.textContent='#backstage-console[data-gaps] .console,#backstage-console[data-gaps] .part,#backstage-console[data-gaps] .chead{outline:1px dashed #b59aff}';document.head.append(light);
if(data.gaps)host.setAttribute('data-gaps','');document.documentElement.lang='zh-CN';
window.addEventListener('message',e=>{if(e.source===parent&&e.data?.type==='gaps')host.toggleAttribute('data-gaps',e.data.value)});
new ResizeObserver(()=>parent.postMessage({type:'height',id:data.id,height:host.getBoundingClientRect().height},'*')).observe(host);
'''
css = (page/'style.css').read_text() + '\n' + (page/'harness.css').read_text() + '\nhtml,body{margin:0!important;padding:0!important;height:auto!important;min-height:0!important;overflow:visible!important;background:transparent!important}body{display:block!important}'
base = '<!doctype html><html lang="zh"><meta charset="utf-8"><style>' + css + '</style><body><script>' + setup + shared.replace('timer = setTimeout(poll, 2000)', 'timer = null') + helpers
bundle = '\n'.join(module(n) for n in ['stream.mjs','flow.mjs','ops.mjs','console.mjs'])
frames = {'base':base+finish+'</script></body></html>', 'showpiece':base+bundle+show+finish+'</script></body></html>', 'harness':base+rail+harness+finish+'</script></body></html>'}
html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>后台控制台 · 统一模块审阅</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f1ea;color:#403832;font:14px/1.65 system-ui,sans-serif}main{max-width:1800px;margin:auto;padding:32px 24px}h1{font-size:32px;letter-spacing:-.03em;margin:8px 0}h2{font-size:18px;margin:0}p{color:#786a5d}small{color:#9d6744;letter-spacing:.08em}.notice{background:#fff7df;border-left:3px solid #dca65f;padding:12px 16px}.controls{display:flex;align-items:center;gap:24px;flex-wrap:wrap;position:sticky;top:0;background:#f5f1efee;padding:16px 0;z-index:2}label{display:flex;gap:8px;align-items:center}select,button{font:inherit;background:#fffaf4;color:inherit;border:1px solid #cdbcab;border-radius:8px;padding:7px 10px}.gallery{display:flex;gap:24px;overflow:auto;padding:12px 4px 24px;align-items:flex-start}article{flex:0 0 var(--width,400px);width:var(--width,400px)}article p{min-height:70px;font-size:13px}iframe{width:100%;display:block;border:0;min-height:380px}footer{padding:20px 0;border-top:1px solid #ddcfc0;color:#786a5d}code{font:12px ui-monospace,monospace}
</style><main><small>BEYOND CANVAS / SHARED CONSOLE</small><h1>同一套模块，不同任务上下文。</h1><p>Resources → Execution → Processes → Pipeline → Harness / Parts → Log</p>
<p class="notice">当前共享组件的交互预览，所有数值与任务均为示意数据。点击模块标题独立收起；在面板内切换本页录播 / 演示与课堂任务。Resources 始终表示服务主机。这里解除浮动位置与高度上限，便于完整比较。</p>
<div class="controls"><label>面板宽度 <input id="width" type="range" min="300" max="720" step="20" value="400"><output id="width-label">400px</output></label><label>展示状态 <select id="state"><option value="replay">已有记录</option><option value="running">任务执行 / 演示</option><option value="idle">空闲</option><option value="offline">实时服务断线</option></select></label><label><input id="gaps" type="checkbox">显示间距边界</label></div>
<div class="gallery"><article><small>01 / CLASSROOM & TOOLS</small><h2>课堂与工具页面</h2><p>课堂阶段事件填充进程、流程与日志。部件来自共用 Harness 定义；未接入的观测明确显示「未报告」。</p><iframe id="base" title="课堂与工具控制台"></iframe></article><article><small>02 / SHOWPIECE</small><h2>一梁一柱</h2><p>相同模块，保留渲染 fps、工具调用统计、流程树和日志。用上下文选择器查看同一服务的课堂任务。</p><iframe id="showpiece" title="一梁一柱控制台"></iframe></article><article><small>03 / HARNESS</small><h2>Harness</h2><p>相同模块，用演示轨迹填充 Processes、Pipeline、Parts 和 Log；状态明确标为演示。</p><iframe id="harness" title="Harness 控制台"></iframe></article></div>
<footer>组件定义来自 <code>harness-roster.json</code>。主机指标与任务数据来源独立；未报告表示没有对应观测，不能推断组件未使用。独立工具服务尚未接入任务事件时，仍显示全部模块与空状态。<br>此页从实际渲染代码生成：<code>python3 tools/build_console_review.py</code>。预览不启动模型、不发起任务。</footer></main><script>
const FRAMES=__FRAMES__;const $=id=>document.getElementById(id);
function render(){for(const[id,template]of Object.entries(FRAMES))$(id).srcdoc=template.replace('__DATA__',JSON.stringify({id,state:$('state').value,gaps:$('gaps').checked}))}
$('width').oninput=()=>{document.documentElement.style.setProperty('--width',$('width').value+'px');$('width-label').value=$('width').value+'px'};
$('state').onchange=render;$('gaps').onchange=()=>{for(const id of Object.keys(FRAMES))$(id).contentWindow.postMessage({type:'gaps',value:$('gaps').checked},'*')};
window.addEventListener('message',e=>{if(e.data?.type==='height'&&FRAMES[e.data.id]&&e.source===$(e.data.id).contentWindow)$(e.data.id).style.height=Math.max(380,e.data.height+8)+'px'});render();
</script></html>'''
html = html.replace('__FRAMES__', json.dumps(frames, ensure_ascii=False).replace('</', '<\\/'))
(page/'console-review.html').write_text(html + '\n')
print('Built console-review.html from current shared modules')
