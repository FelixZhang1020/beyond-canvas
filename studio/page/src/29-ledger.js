// The grown-ups' view of what the studio did: four numbers and every ledger line. No glass here.
window.Studio = window.Studio || {};
// NVIDIA's second look as the teacher reads it: the codes of what it flagged, or that it could not look.
// "clear", and lines from before it existed, add nothing.
Studio.secondLookText = function (said, t) {
  if (!said || said === 'clear') return '';
  if (said === 'unavailable') return t('ledger.second_look_unavailable');
  return t('ledger.second_look_flagged', { codes: said.split(',').join(', ') });
};
Studio.ledger = {
  shown: null,
  open: function () {
    const view = document.getElementById('ledger'), t = Studio.i18n.t.bind(Studio.i18n);
    const st = Studio.state, self = this;
    const fromTransport = st.session && st.transport ? st.transport.ledger(st.session).catch(function () { return null; }) : Promise.resolve(null);
    fromTransport.then(function (res) {
      const lines = res && res.lines && res.lines.length ? res.lines : st.ledger;
      // Remember exactly what was drawn, so saving it saves the same rows. The
      // table read the studio's own file and the button exported the events this
      // browser happened to see, which are not the same set.
      self.shown = lines;
      self.render(lines, t); view.hidden = false; view.scrollTop = 0;
    });
  },
  close: function () { document.getElementById('ledger').hidden = true; },
  render: function (lines, t) {
    const sum = Studio.ledgerSummary(lines), tiles = document.getElementById('ledger-tiles'), grid = document.getElementById('ledger-grid');
    tiles.innerHTML = '';
    [[sum.requests, t('ledger.requests')], [sum.gatesPassed + (sum.gatesFailed ? ' / ' + (sum.gatesPassed + sum.gatesFailed) : ''), t('ledger.gates')],
      [sum.tokens, t('ledger.tok')], [Studio.money(sum.cost), t('ledger.spend')],
      [sum.peakMem ? sum.peakMem.toFixed(1) : t('ledger.none'), t('ledger.peak')]].forEach(function (pair) {
      const tile = document.createElement('div'); tile.className = 'tile';
      tile.innerHTML = '<span class="n"></span><span class="l"></span>';
      tile.firstChild.textContent = pair[0]; tile.lastChild.textContent = pair[1]; tiles.appendChild(tile);
    });
    // Why the zeros in the cost column are zeros; empty on a deployment that
    // buys per call, so it appears only where it explains something.
    const footnote = document.getElementById('ledger-billing');
    const key = Studio.costFootnote(Studio.state?.capabilities?.deployment);
    if (footnote) { footnote.textContent = key ? t(key) : ''; footnote.hidden = !key; }
    grid.innerHTML = '';
    const head = document.createElement('div'); head.className = 'ledger-row head';
    ['ledger.time', 'ledger.stage', 'ledger.gate', 'ledger.tokens', 'ledger.cost', 'ledger.wall', 'ledger.mem', 'ledger.reason'].forEach(function (k) {
      const s = document.createElement('span'); s.textContent = t(k); head.appendChild(s);
    });
    grid.appendChild(head);
    if (!lines.length) { const e = document.createElement('div'); e.className = 'ledger-row'; e.innerHTML = '<span></span>'; e.firstChild.textContent = t('ledger.empty'); grid.appendChild(e); return; }
    lines.forEach(function (l) {
      const row = document.createElement('div'); row.className = 'ledger-row';
      const ts = l.ts ? new Date(l.ts).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
      const mem = l.mem_before_gb !== undefined ? l.mem_before_gb + ' → ' + l.mem_after_gb : '';
      [ts, Studio.stageLabel(l.stage), l.gate ? t('status.gate_' + l.gate) : '', l.tokens || 0,
        Studio.money(l.cost), l.wall_s || 0, mem,
        [l.reason_code, Studio.secondLookText(l.second_look, t)].filter(Boolean).join(' · ')].forEach(function (v, i) {
        const s = document.createElement('span'); s.textContent = v;
        if (i === 2 && l.gate) s.className = l.gate === 'pass' ? 'g-pass' : 'g-fail';
        row.appendChild(s);
      });
      grid.appendChild(row);
    });
  },
  exportJson: function () {
    const lines = this.shown && this.shown.length ? this.shown : Studio.state.ledger;
    const blob = new Blob([JSON.stringify({ session: Studio.state.session, lines: lines }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'studio-ledger.json'; a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
  }
};
