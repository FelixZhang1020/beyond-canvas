/* One console outside each page's app shell. Read-only polling, no model calls. */
(() => {
  if (window.self !== window.top || window.Backstage) return;
  const host = document.createElement('aside');
  host.id = 'backstage-console';
  const root = host.attachShadow({mode: 'open'});
  // Apply the same dark scrollbar to the shadow panel and its slotted logs.
  const scrollbars = selector => `
    ${selector}{color-scheme:dark;scrollbar-width:thin;scrollbar-color:#756354 transparent}
    ${selector}::-webkit-scrollbar{width:6px;height:6px}
    ${selector}::-webkit-scrollbar-track{background:transparent;margin-block:14px}
    ${selector}::-webkit-scrollbar-thumb{background:#756354;border-radius:99px}
    ${selector}::-webkit-scrollbar-thumb:hover{background:#a18a75}
    ${selector}::-webkit-scrollbar-corner{background:transparent}
    @supports selector(::-webkit-scrollbar){${selector}{scrollbar-width:auto;scrollbar-color:auto}}
  `;
  root.innerHTML = `<style>
    :host{position:fixed;right:16px;bottom:16px;z-index:2147483000;color:#f1e9dd;font:13px/1.5 system-ui,sans-serif;max-width:calc(100% - 24px)}
    *{box-sizing:border-box}button{font:inherit;color:inherit;cursor:pointer;border:1px solid #64574a;background:#302923;border-radius:12px;min-height:44px;padding:10px 16px}
    button:focus-visible{outline:3px solid #ffb66b;outline-offset:3px}button:hover{background:#493c31}
    #toggle{float:right;box-shadow:0 8px 28px #0003}#panel{width:520px;max-width:100%;max-height:70dvh;overflow:auto;overscroll-behavior:contain;margin-bottom:8px;background:#2b2622;border:1px solid #64574a;border-radius:18px;box-shadow:0 18px 65px #0005;padding:16px}
    #frame{position:relative}#resize{position:absolute;top:3px;left:3px;z-index:1;width:28px;min-height:28px;padding:0;border:0;border-radius:12px 0 8px 0;background:transparent;color:#a18a75;cursor:nwse-resize;touch-action:none;-webkit-user-select:none;user-select:none}
    #resize:hover,#resize:focus-visible{color:#ffc085;background:#493c31}header{padding-left:12px}
    @media(pointer:coarse){#resize{width:40px;min-height:40px}header{padding-left:24px}}
    [hidden]{display:none!important}header{display:flex;align-items:center;justify-content:space-between;gap:12px}h2{font-size:15px;margin:0}h3{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#c1b0a0;margin:16px 0 8px}
    #toggle{cursor:grab;touch-action:none;-webkit-user-select:none;user-select:none}#toggle.moving{cursor:grabbing}#move{cursor:grab;touch-action:none;-webkit-user-select:none;user-select:none}#move.moving{cursor:grabbing}#move:focus-visible{outline:2px solid #ffb66b;outline-offset:3px;border-radius:8px}
    #connection{font-size:11px;color:#cabaaa;margin:6px 0}#metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.metric{padding:10px;background:#393029;border-radius:10px;font-variant-numeric:tabular-nums}.metric small{display:block;color:#cabaaa;font-size:10px}
    progress{width:100%;height:5px;accent-color:#ffc085}p{margin:5px 0;overflow-wrap:anywhere}.job{border-top:1px solid #594b40;padding:9px 0}.trail{font:11px/1.7 ui-monospace,monospace;color:#c9b9a9;white-space:pre-wrap}.tag{color:#ffc085;font-size:11px}#local{border-top:1px solid #594b40;margin-top:12px;padding-top:10px}slot{display:block;margin-top:12px}
    @media(max-width:600px){:host{right:12px;bottom:12px}#panel{max-height:65dvh;padding:12px}}
    :host{font:12px/1.6 ui-monospace,Menlo,monospace}header{border-bottom:1px solid #51463d;padding-bottom:10px}#machine-host{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#aa9b8b}h2{white-space:nowrap;font:600 15px/1.5 system-ui,sans-serif}details{margin-top:16px}summary{cursor:pointer;color:#aa9b8b;text-transform:uppercase;letter-spacing:.12em;font-size:11px;min-height:32px}summary:focus-visible{outline:2px solid #ffc085}#metrics{display:block}.metric{display:grid;grid-template-columns:30px minmax(30px,1fr) auto;gap:8px;padding:2px 0;background:none;border-radius:0}.bar{color:#ff9f43;overflow:hidden;white-space:nowrap}.value{text-align:right}.label{color:#aa9b8b}slot{margin-top:0}slot[name=clock]{color:#aa9b8b;margin-left:auto}#panel{margin-bottom:0}
    select{width:100%;max-width:100%;font:inherit;background:#302923;color:#e8ddd0;border:1px solid #64574a;border-radius:7px;padding:7px;margin-bottom:8px}#context-label,.module-note{color:#aa9b8b;font-size:10px}.module-note{margin-bottom:8px}.data-table{width:100%;table-layout:fixed;border-collapse:collapse}.data-table th,.data-table td{padding:4px 3px;border-bottom:1px dashed #51463d;text-align:left;overflow-wrap:anywhere;font-weight:400}.data-table th{color:#aa9b8b}.data-table{font-size:11px}.data-table th:first-child{width:40%}.data-table th:nth-child(2){width:28%}.data-table th:nth-child(n+3){width:16%}.data-table td:last-child{text-align:right}.lines{white-space:pre-wrap;overflow-wrap:anywhere;color:#cabaaa}.log-lines{background:#241f1b;border-radius:10px;padding:10px}.module-empty{color:#aa9b8b}details:not([open])>summary{color:#d9cbbd}#connection{font-size:10px}.metric .bar{font-size:11px;letter-spacing:-.5px}#services{margin-top:10px}.service{padding:2px 0;color:#cabaaa;overflow-wrap:anywhere}.service.live{color:#ffc085}#chip{margin-top:10px}.chip-head{color:#d9cbbd;margin-top:8px}.chip-row{padding:2px 0;color:#cabaaa;white-space:pre-wrap;overflow-wrap:anywhere}.chip-row.live{color:#ffc085}.chip-row.stuck{color:#ff8a7a}
    .data-table.parts-table th:first-child{width:58%}.data-table.parts-table th:nth-child(2){width:42%}.parts-table td:last-child{text-align:left}
    ${scrollbars('#panel')}
  </style><div id="frame"><button id="resize" type="button" aria-controls="panel">↖</button><section id="panel" role="region" aria-labelledby="title"><header id="move" tabindex="0"><h2 id="title"></h2><span id="machine-host"></span><slot name="clock"></slot><button id="close" type="button">−</button></header><p id="connection" role="status"></p><details open data-module="resources"><summary>Resources</summary><div id="metrics"></div><div id="services"></div><div id="chip"></div><slot name="resource-extra"></slot></details><details open data-module="execution"><summary id="jobs-title"></summary><label id="context-label" for="context"></label><select id="context"></select><div id="jobs"></div><div id="local" hidden></div></details>${['processes','pipeline','parts','log'].map(id => `<details open data-module="${id}"><summary>${id === 'parts' ? 'Harness / Parts' : id}</summary><slot name="${id}"></slot><div id="${id}-content"></div></details>`).join('')}</section></div><button id="toggle" type="button" aria-controls="panel" aria-expanded="true"></button>`;
  document.body.append(host);
  // Page renderers supply module contents only; layout and headings belong to this shell.
  const style = document.createElement('style');
  style.textContent = `body:has(#backstage-console) .stage.hv-stage{grid-template-columns:minmax(0,1fr)}
    html.backstage-interacting,html.backstage-interacting *{-webkit-user-select:none!important;user-select:none!important}
    @media(min-width:1400px){body:has(#backstage-console) .stage:has(> .centre + .side){grid-template-columns:minmax(0,5fr) minmax(0,6fr)}}
    #backstage-console>[hidden]{display:none!important}
    #backstage-console>[slot]{font:12px/1.6 ui-monospace,Menlo,monospace;color:#cabaaa;min-width:0}
    #backstage-console .ps{width:100%;table-layout:fixed;border-collapse:collapse}
    #backstage-console .ps th,#backstage-console .ps td{padding:4px 3px;border-bottom:1px dashed #51463d;overflow-wrap:anywhere;white-space:normal;text-align:left;font-weight:400}
    #backstage-console .ps{font-size:11px}#backstage-console .ps th:first-child{width:40%}#backstage-console .ps th:nth-child(2){width:28%}#backstage-console .ps th:nth-child(n+3){width:16%}#backstage-console .ps small{display:none}
    #backstage-console .ps .r{text-align:right}
    #backstage-console .log{background:#241f1b;border-radius:10px;padding:10px;max-height:none;overflow:visible}
    #backstage-console .log p,#backstage-console .tree p{white-space:pre-wrap;overflow-wrap:anywhere;margin:3px 0}
    #backstage-console [slot=resource-extra]{display:grid;grid-template-columns:30px minmax(30px,1fr) auto;gap:8px}
    #backstage-console [slot=resource-extra] .hist{display:none}#backstage-console [slot=resource-extra] .bar{overflow:hidden;color:#ff9f43}
    #backstage-console [slot=resource-extra] .v{text-align:right}`;
  document.head.append(style);
  const $ = id => root.getElementById(id);
  const en = () => document.documentElement.lang.startsWith('en');
  const words = (zh, english) => en() ? english : zh;
  let selectedContext = '', pageContext = null;
  const supplied = new Map();
  const pageModules = ['processes','pipeline','log']; // Parts always uses the shared renderer.
  let open = true, snapshot = null, failed = false, updated = null, timer, suspended = false, lastAsked = 0;
  try { open = localStorage.getItem('backstage.open') !== 'false'; } catch (_) {}
  function setOpen(value) {
    open = value; $('toggle').hidden = open; $('frame').hidden = !open; $('panel').hidden = !open; $('toggle').setAttribute('aria-expanded', String(open));
    try { localStorage.setItem('backstage.open', String(open)); } catch (_) {}
    applySize(); applyPosition();
  }
  // The lower-right corner stays anchored; drag the upper-left corner outward to grow.
  let preferredSize = null, drag = null;
  try {
    const saved = JSON.parse(localStorage.getItem('backstage.size'));
    if (saved && Number.isFinite(saved.width) && Number.isFinite(saved.height) && saved.width > 0 && saved.height > 0) preferredSize = saved;
  } catch (_) {}
  function fitSize(size) {
    const maxWidth = Math.max(1, document.documentElement.clientWidth - 32);
    const maxHeight = Math.max(1, window.innerHeight - 92);
    return {width:Math.min(maxWidth, Math.max(300, size.width)), height:Math.min(maxHeight, Math.max(240, size.height))};
  }
  function applySize() {
    const panel = $('panel');
    // Explicit host width prevents fixed-position shrink-to-fit when moved left.
    host.style.width = open ? `${fitSize(preferredSize || {width:520, height:240}).width}px` : '';
    panel.style.width = '100%';
    if (!preferredSize) { panel.style.height = ''; panel.style.maxHeight = ''; return; }
    const size = fitSize(preferredSize);
    panel.style.height = `${size.height}px`;
    panel.style.maxHeight = 'calc(100dvh - 92px)';
  }
  function saveSize() {
    try {
      if (preferredSize) localStorage.setItem('backstage.size', JSON.stringify(preferredSize));
      else localStorage.removeItem('backstage.size');
    } catch (_) {}
  }
  function startInteraction() {
    document.getSelection()?.removeAllRanges();
    document.documentElement.classList.add('backstage-interacting');
  }
  function stopInteraction() {
    document.documentElement.classList.remove('backstage-interacting');
  }
  document.addEventListener('selectstart', event => {
    if (drag || moving) event.preventDefault();
  });
  const grip = $('resize');
  grip.onpointerdown = event => {
    if (event.button !== 0 || !event.isPrimary) return;
    const rect = $('panel').getBoundingClientRect();
    drag = {id:event.pointerId, x:event.clientX, y:event.clientY, width:rect.width, height:rect.height};
    startInteraction(); grip.setPointerCapture(event.pointerId); event.preventDefault();
  };
  grip.onpointermove = event => {
    if (!drag || event.pointerId !== drag.id) return;
    preferredSize = fitSize({width:drag.width + drag.x - event.clientX, height:drag.height + drag.y - event.clientY});
    applySize();
  };
  function endResize(event) {
    if (!drag || event.pointerId !== drag.id) return;
    drag = null; stopInteraction(); saveSize();
    if (grip.hasPointerCapture(event.pointerId)) grip.releasePointerCapture(event.pointerId);
  }
  grip.onpointerup = grip.onpointercancel = grip.onlostpointercapture = endResize;
  grip.onkeydown = event => {
    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key)) return;
    event.preventDefault(); event.stopPropagation();
    const rect = $('panel').getBoundingClientRect(), step = event.shiftKey ? 40 : 16;
    preferredSize = event.key === 'Home' ? null : fitSize({
      width:rect.width + (event.key === 'ArrowLeft' ? step : event.key === 'ArrowRight' ? -step : 0),
      height:rect.height + (event.key === 'ArrowUp' ? step : event.key === 'ArrowDown' ? -step : 0)
    });
    applySize(); saveSize();
  };
  let preferredPosition = null, moving = null;
  try {
    const saved = JSON.parse(localStorage.getItem('backstage.position'));
    if (saved && Number.isFinite(saved.right) && Number.isFinite(saved.bottom)) preferredPosition = saved;
  } catch (_) {}
  function applyPosition() {
    if (!preferredPosition) { host.style.right = ''; host.style.bottom = ''; return; }
    const rect = host.getBoundingClientRect();
    host.style.right = `${Math.max(12, Math.min(preferredPosition.right, document.documentElement.clientWidth - rect.width - 12))}px`;
    host.style.bottom = `${Math.max(12, Math.min(preferredPosition.bottom, window.innerHeight - rect.height - 12))}px`;
  }
  function savePosition() {
    try {
      if (preferredPosition) localStorage.setItem('backstage.position', JSON.stringify(preferredPosition));
      else localStorage.removeItem('backstage.position');
    } catch (_) {}
  }
  // The title bar moves the open panel; the closed toggle moves too, and only a drag past a few
  // pixels counts as one, so a plain tap still opens it.
  const titlebar = $('move');
  let tapBlockedUntil = 0;
  function movable(handle, tapToo) {
    handle.onpointerdown = event => {
      if (event.button !== 0 || !event.isPrimary || (!tapToo && event.target.closest('button'))) return;
      const rect = host.getBoundingClientRect();
      moving = {id:event.pointerId, handle, started:!tapToo, x:event.clientX, y:event.clientY,
        right:document.documentElement.clientWidth - rect.right, bottom:window.innerHeight - rect.bottom};
      handle.setPointerCapture(event.pointerId);
      if (!tapToo) { startInteraction(); handle.classList.add('moving'); event.preventDefault(); }
    };
    handle.onpointermove = event => {
      if (!moving || event.pointerId !== moving.id) return;
      if (!moving.started) {
        if (Math.hypot(event.clientX - moving.x, event.clientY - moving.y) < 6) return;
        moving.started = true; startInteraction(); handle.classList.add('moving');
      }
      const rect = host.getBoundingClientRect();
      preferredPosition = {
        right:Math.max(12, Math.min(document.documentElement.clientWidth - rect.width - 12, moving.right + moving.x - event.clientX)),
        bottom:Math.max(12, Math.min(window.innerHeight - rect.height - 12, moving.bottom + moving.y - event.clientY))
      };
      applyPosition();
    };
    handle.onpointerup = handle.onpointercancel = handle.onlostpointercapture = endMove;
  }
  function endMove(event) {
    if (!moving || event.pointerId !== moving.id) return;
    const {handle, started} = moving;
    moving = null;
    if (started) { stopInteraction(); handle.classList.remove('moving'); savePosition(); tapBlockedUntil = performance.now() + 400; }
    if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
  }
  movable(titlebar, false);
  movable($('toggle'), true);
  window.addEventListener('blur', () => {
    if (drag) endResize({pointerId:drag.id});
    if (moving) endMove({pointerId:moving.id});
  });
  titlebar.onkeydown = event => {
    if (event.target !== titlebar || !['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key)) return;
    event.preventDefault(); event.stopPropagation();
    const rect = host.getBoundingClientRect(), step = event.shiftKey ? 40 : 16;
    preferredPosition = event.key === 'Home' ? null : {
      right:document.documentElement.clientWidth - rect.right + (event.key === 'ArrowLeft' ? step : event.key === 'ArrowRight' ? -step : 0),
      bottom:window.innerHeight - rect.bottom + (event.key === 'ArrowUp' ? step : event.key === 'ArrowDown' ? -step : 0)
    };
    applyPosition(); savePosition();
  };
  window.addEventListener('resize', () => { applySize(); applyPosition(); });
  new ResizeObserver(applyPosition).observe(host);
  applySize();
  $('toggle').onclick = () => { if (performance.now() >= tapBlockedUntil) setOpen(!open); };
  $('close').onclick = () => { setOpen(false); $('toggle').focus(); };
  host.addEventListener('keydown', event => { if (event.key !== 'Tab') event.stopPropagation(); if (event.key === 'Escape') { setOpen(false); $('toggle').focus(); } });
  function node(tag, text, cls) { const n = document.createElement(tag); n.textContent = text; if (cls) n.className = cls; return n; }
  const number = value => Number.isFinite(value) ? value.toFixed(1) : '—';
  function paint() {
    const title = words('后台控制台', 'Backend console');
    $('title').textContent = title;
    const active = failed ? 0 : snapshot?.jobs.filter(j => !j.done).length || 0;
    $('toggle').textContent = `${failed ? '○' : '●'} ${title}${active ? ` · ${active}` : ''}`;
    $('toggle').title = words('点按打开；拖动可移到页面任意位置', 'Tap to open; drag to move it anywhere');
    titlebar.title = words('拖动标题栏移动；方向键微调，Home 回到右下角', 'Drag the title bar to move; arrow keys adjust, Home returns to bottom right');
    titlebar.setAttribute('aria-label', words('移动控制台', 'Move console'));
    grip.title = words('拖动左上角调整大小；方向键微调，Home 恢复默认', 'Drag this corner to resize; arrow keys adjust, Home resets');
    grip.setAttribute('aria-label', words('调整控制台大小', 'Resize console'));
    $('close').setAttribute('aria-label', words('收起控制台', 'Minimize console'));
    $('connection').textContent = failed ? words('连接中断 · 等待重连，指标已失效', 'Disconnected · retrying; metrics unavailable') : updated ? words('每 2 秒更新 · ', 'Updates every 2s · ') + updated.toLocaleTimeString() : words('正在连接…', 'Connecting…');
    const m = !failed && snapshot?.machine || {};
    $('machine-host').textContent = m.host || '';
    $('metrics').replaceChildren(...[
      ['cpu', number(m.cpu_percent) + '%', m.cpu_percent, words('CPU · 1分钟负载 / 核数', 'CPU · 1m load / cores')],
      ['mem', `${number(m.memory_used_gb)} / ${number(m.memory_total_gb)} G`, m.memory_total_gb ? m.memory_used_gb / m.memory_total_gb * 100 : null, words('服务主机内存', 'Server memory')],
      ['gpu', !m.gpu ? words('不可用', 'Unavailable') : Number.isFinite(m.gpu.util_percent) ? number(m.gpu.util_percent) + '%' : words('未报告', 'Not reported'), m.gpu?.util_percent, words('服务主机 GPU · 与系统共用内存时不单独报告显存', 'Server GPU · no separate memory to report when it shares the system pool')]
    ].map(([label, value, percent, description]) => {
      const n = node('div', '', 'metric'); n.title = description;
      const count = Number.isFinite(percent) ? Math.round(Math.max(0, Math.min(100, percent)) / 5) : 0;
      const bar = node('span', '█'.repeat(count) + '░'.repeat(20-count), 'bar'); bar.setAttribute('aria-hidden', 'true');
      n.append(node('span', label, 'label'), bar, node('span', value, 'value')); return n;
    }));
    paintServices();
    paintChip();
    $('jobs-title').textContent = words('执行 / 编排进度', 'Execution / orchestration');
    paintModules();
  }
  function spell(seconds) {
    if (!Number.isFinite(seconds)) return '';
    seconds = Math.round(seconds);     // before splitting, or 179.6 s reads "2m 60s"
    const minutes = Math.floor(seconds / 60), rest = seconds % 60;
    return minutes ? `${minutes}m ${rest}s` : `${rest}s`;
  }
  function serviceLine(service) {
    const name = service.slots.join(' / ');
    if (!service.answering) return `${name} · ${words('无应答', 'not answering')}`;
    const model = service.model || '?';
    if (service.busy || (service.phase && service.phase !== 'standby')) return `${name} · ${model} · ${service.phase || words('忙碌', 'busy')}`;
    return `${name} · ${model} · ${words('待命', 'standby')}`;
  }
  // The Spark's terminal monitor and this panel read the same code (deploy/spark/dashboard_jobs.py)
  // and say the same things in the same order: the panel used to name a two-day-old
  // finished job as the last one while the monitor showed the latest cancellation.
  function chipNowLine(row) {
    const running = Number.isFinite(row.running_s) ? row.running_s : 0;
    // Clock times are the Spark's own, written there, as its terminal shows them: the page is often
    // opened an hour away, and its own clock put the same job at 13:15 beside the terminal's 12:15.
    const facts = [(row.started_clock ? `${words('开始于', 'started')} ${row.started_clock}, ` : '') +
      `${row.group === 'service' ? words('已开启', 'up') : words('已运行', 'running')} ${spell(running)}`];
    if (Number.isFinite(row.usual_s)) {
      const left = row.usual_s - running;
      facts.push(left > 0 ? `${words('通常', 'usually')} ${spell(row.usual_s)}, ${words('约剩', 'about')} ${spell(left)}${words('', ' left')}`
        : `${words('已超出通常的', 'longer than the usual')} ${spell(row.usual_s)} ${words('约', 'by about')} ${spell(-left)}`);
    } else if (row.group !== 'service' && row.group !== 'program') {
      facts.push(Number.isFinite(row.reported_s_ago) ? `${words('上次报告于', 'last reported')} ${spell(row.reported_s_ago)}${words('前', ' ago')}`
        : words('尚未报告', 'has reported nothing yet'));
    }
    if (row.held_gb >= 0.5) facts.push(`${words('占用', 'holding')} ${Math.round(row.held_gb)} G`);
    if (row.stuck) facts.push(words('看起来卡住：芯片已 10 分钟无动作', 'looks stuck: the chip has done nothing for 10 min'));
    return `${row.group} · ${row.what}\n   ${facts.join(' · ')}`;
  }
  const ENDED = {done:['完成，用时', 'done in'], cancelled:['已取消，运行了', 'was cancelled after'],
    refused:['被拒：服务正忙', 'turned away, the service was busy'], failed:['未完成，运行了', 'started but did not finish after'],
    stopped:['被停止，运行约', 'was stopped after about'], error:['出错停止，运行约', 'stopped with an error after about'],
    unknown:['运行约', 'ran for about']};
  function chipFinishedLine(row) {
    const [zh, en] = ENDED[row.outcome] || ENDED.unknown;
    const took = row.outcome === 'refused' || !Number.isFinite(row.seconds) ? '' : ` ${spell(row.seconds)}`;
    return `${row.clock} · ${row.group} · ${row.what} · ${words(zh, en)}${took}`;
  }
  function chipTodayLines(today) {
    const lines = (today?.jobs || []).map(k => `${k.what} · ${k.done} ${words('完成', 'done')} · ${k.refused} ${words('被拒', 'turned away')} · ` +
      `${k.cancelled} ${words('取消', 'cancelled')} · ${k.failed} ${words('未完成', 'did not finish')}`);
    const tests = today?.tests;
    // Docker forgets how runs ended within minutes, so these two can only ever undercount: "including".
    const known = [[tests?.stopped, words('被停止', 'stopped')], [tests?.error, words('出错', 'with an error')]]
      .filter(([count]) => count).map(([count, what]) => `${count} ${what}`);
    if (tests?.finished) lines.push(`${words('测试与检查', 'Tests and checks')} · ${tests.finished} ${words('已结束', 'finished')}` +
      (known.length ? ` · ${words('其中', 'including')} ${known.join(words('，', ' and '))}` : ''));
    return lines;
  }
  function paintChip() {
    const chip = !failed && snapshot ? snapshot.chip : undefined;
    if (chip === undefined) { $('chip').replaceChildren(); return; }
    if (!chip) { $('chip').replaceChildren(node('p', words('芯片上的工作暂时读不到', 'The work on the chip cannot be read just now'), 'module-empty')); return; }
    const now = chip.now || [], done = chip.finished || [], today = chipTodayLines(chip.today);
    $('chip').replaceChildren(
      node('p', words('芯片上的工作 · 与 Spark 终端监视器同一份数据', 'Work on the chip · the same reading as the Spark\'s terminal monitor'), 'module-note'),
      node('div', words('正在进行', 'Working on now'), 'chip-head'),
      ...(now.length ? now.map(row => node('div', chipNowLine(row), row.stuck ? 'chip-row stuck' : row.group === 'service' ? 'chip-row' : 'chip-row live'))
        : [node('div', words('无：没有视频或 3D 任务在运行', 'nothing: no video or 3D job is running'), 'chip-row')]),
      node('div', words('最近结束（最新在前）', 'Finished lately (newest first)'), 'chip-head'),
      ...(done.length ? done.map(row => node('div', chipFinishedLine(row), 'chip-row')) : [node('div', words('暂无记录', 'nothing recorded yet'), 'chip-row')]),
      ...(today.length ? [node('div', words('今天', 'Today so far'), 'chip-head'), ...today.map(line => node('div', line, 'chip-row'))] : []));
  }
  function paintServices() {
    // These belong to the machine, not to this page: a clip another class started, or one whose
    // class has ended, keeps rendering here after its request has gone from the list below.
    const services = (!failed && snapshot?.services) || [];
    $('services').replaceChildren(...(services.length ? [
      node('p', words('本机模型服务 · 所有班级共用一块芯片', 'Model services on this machine · every class shares one chip'), 'module-note'),
      ...services.map(service => {
        const busy = service.answering && (service.busy || (service.phase && service.phase !== 'standby'));
        return node('div', serviceLine(service), busy ? 'service live' : 'service');
      })
    ] : []));
  }
  function table(headers, rows) {
    const t = node('table', '', 'data-table'), head = node('tr', '');
    headers.forEach(h => head.append(node('th', h)));
    const thead = node('thead', ''); thead.append(head); t.append(thead);
    const body = node('tbody', '');
    rows.forEach(row => { const tr = node('tr', ''); row.forEach(value => tr.append(node('td', String(value ?? '—')))); body.append(tr); });
    t.append(body); return t;
  }
  function paintModules() {
    const jobs = snapshot?.jobs || [];
    const options = pageContext ? [{id:'page', label:pageContext.label}, ...jobs.map(j => ({id:j.id, label:`${j.source} · ${j.skill} · ${j.status}`}))] : jobs.map(j => ({id:j.id, label:`${j.source} · ${j.skill} · ${j.status}`}));
    if (!options.some(o => o.id === selectedContext)) selectedContext = options[0]?.id || '';
    const selector = $('context');
    const signature = JSON.stringify(options);
    if (selector.dataset.options !== signature) {
      selector.replaceChildren(...options.map(o => { const n = node('option', o.label); n.value = o.id; return n; }));
      selector.dataset.options = signature;
    }
    selector.value = selectedContext; selector.hidden = options.length < 2;
    $('context-label').textContent = words('数据上下文 · 同一服务内的任务', 'Context · tasks in this service');
    const local = selectedContext === 'page';
    const job = local ? pageContext : failed ? null : jobs.find(j => j.id === selectedContext);
    const empty = failed ? words('实时连接中断；等待重连', 'Live connection lost; retrying') : snapshot?.sources?.length ? words('暂无任务记录；运行任务后显示', 'No task records; populated when a task runs') : words('此服务尚未接入任务事件', 'Task events are not connected for this service');
    $('jobs').replaceChildren(node('p', job ? `${job.label || job.skill} · ${job.status || ''}` : empty, 'tag'));
    if (job && !job.done && Number.isFinite(job.percent)) { const bar = node('progress', ''); bar.max = 100; bar.value = job.percent; bar.setAttribute('aria-label', job.skill || job.label); $('jobs').append(bar); }
    const activity = local ? window.Backstage.activity : null;
    $('local').hidden = !activity;
    if (activity) $('local').replaceChildren(node('p', activity.detail || activity.label, 'trail'));
    const processes = job?.processes || [], events = job?.events || [];
    const rows = processes.map(p => [p.name, p.status, Number.isFinite(p.seconds) ? `${p.seconds.toFixed(1)}s` : '—', p.events]);
    const eventNote = words('按已报告阶段；耗时为最近一次报告，次数为事件数', 'Reported stages; latest reported duration; counts are events');
    $('processes-content').replaceChildren(node('p', eventNote, 'module-note'), rows.length ? table(['name','state','time','count'], rows) : node('p', empty, 'module-empty'));
    $('pipeline-content').replaceChildren(node('div', processes.length ? [job.skill || job.label, ...processes.map((p,i) => `${i === processes.length-1 ? '└' : '├'}─ ${p.name} · ${p.status}`)].join('\n') : empty, 'lines'));
    const observed = job?.parts || {};
    const missing = words('未报告', 'Not reported');
    const parts = snapshot?.parts || [];
    const states = {not_started:words('待开始', 'Not started'), current:words('当前步骤', 'Current step'), visited:words('已经过', 'Visited')};
    const partNote = job?.mode === 'simulation' ? words('演示轨迹状态 · 非真实调用', 'Simulation journey states · not live calls') : words('组件名称共用 Harness 定义；未报告不表示未使用', 'Shared Harness definitions; not reported does not mean unused');
    const partTable = parts.length ? table(['component','observation'], parts.map(p => {
      const value = observed[p.id] || (p.id === 'request' && job ? job.status : p.id === 'skills' && processes.length ? String(processes.length) + words(' 个阶段', ' stages') : missing);
      return [p.name, states[value] || value];
    })) : node('p', words('等待组件定义', 'Waiting for component definitions'), 'module-empty');
    partTable.classList.add('parts-table');
    $('parts-content').replaceChildren(node('p', partNote, 'module-note'), partTable);
    $('log-content').replaceChildren(node('div', events.length ? events.map(e => `${e.stage || 'request'} · ${e.status}${Number.isFinite(e.seconds) ? ` · ${e.seconds.toFixed(1)}s` : ''}`).join('\n') : empty, 'lines log-lines'));
    for (const id of pageModules) {
      const custom = supplied.get(id);
      if (custom) custom.slot = local ? id : 'inactive';
      $(id+'-content').hidden = local && !!custom;
    }
    const clock = host.querySelector('[data-console-clock]'), fps = host.querySelector('[data-console-fps]');
    if (clock) clock.slot = local ? 'clock' : 'inactive';
    if (fps) fps.slot = local ? 'resource-extra' : 'inactive';
  }
  async function poll() {
    // Closed, the panel shows a dot and a count, so it asks every 15 s rather than every 2: on a slow
    // classroom link each ask competes with the page (18,260 asks in one day, links at 5 KB/s).
    if (!document.hidden && (open || Date.now() - lastAsked >= 15000)) {
      lastAsked = Date.now();
      try {
        const response = await fetch('/api/console', {signal: AbortSignal.timeout(5000)});
        if (!response.ok) throw new Error('console unavailable');
        snapshot = await response.json(); failed = false; updated = new Date();
      } catch (_) { failed = true; }
      paint();
    }
    if (!suspended) timer = setTimeout(poll, 2000);
  }
  $('context').onchange = () => { selectedContext = $('context').value; paintModules(); };
  for (const module of root.querySelectorAll('details[data-module]')) {
    const key = 'backstage.module.' + module.dataset.module;
    try { module.open = localStorage.getItem(key) !== 'false'; } catch (_) {}
    module.addEventListener('toggle', () => { try { localStorage.setItem(key, String(module.open)); } catch (_) {} });
  }
  window.Backstage = {activity:null, context(data) { pageContext = data; paintModules(); }, dock(panel) { (panel || document.body).append(host); }, controls() {
    return Array.from(root.querySelectorAll('button, [tabindex], summary, select')).filter(control => control.getClientRects().length);
  }, attach(detail) {
    const rail = detail.parentElement, extras = [];
    supplied.clear();
    for (const [id, slot] of [['console-clock','clock'],['res-fps','resource-extra']]) {
      const value = detail.querySelector('#'+id);
      if (value) { value.slot = slot; value.dataset[id === 'console-clock' ? 'consoleClock' : 'consoleFps'] = ''; extras.push(value); }
    }
    for (const part of detail.querySelectorAll('.part')) {
      const name = part.querySelector('.sect')?.textContent.toLowerCase();
      if (!pageModules.includes(name)) continue;
      part.querySelector('.sect').remove();
      part.slot = name; supplied.set(name, part); extras.push(part);
    }
    // Retain hidden legacy data targets for existing page renderers; no nested shell.
    detail.hidden = true; detail.slot = 'inactive'; host.replaceChildren(detail, ...extras);
    if (rail?.classList.contains('rail')) rail.remove();
    if (!pageContext) pageContext = {label:words('本页', 'This page'), status:words('等待记录', 'Waiting for records')};
    paintModules();
  }};
  new MutationObserver(paint).observe(document.documentElement, {attributes:true, attributeFilter:['lang']});
  window.addEventListener('pagehide', () => { suspended = true; clearTimeout(timer); });
  window.addEventListener('pageshow', event => { if (event.persisted) { suspended = false; poll(); } });
  setOpen(open); paint(); poll();
})();
