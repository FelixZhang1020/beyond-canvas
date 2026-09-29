import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

// The grown-ups' ledger view: what NVIDIA's second look said about a drawing or a made picture, as
// codes only, in the reason column beside any refusal reason. "clear" and older lines add nothing.
function page() {
  const made = [];
  const el = () => { const e = { children: [], className: '', textContent: '', hidden: false, innerHTML: '',
    firstChild: { textContent: '' }, lastChild: { textContent: '' },
    appendChild(c) { this.children.push(c); return c; } }; made.push(e); return e; };
  const ids = { 'ledger-tiles': el(), 'ledger-grid': el(), 'ledger-billing': el() };
  const S = loadStudio({ files: ['src/29-ledger.js'],
    globals: { document: { getElementById: id => ids[id], createElement: el } } });
  S.ledgerSummary = () => ({ requests: 1, gatesPassed: 1, gatesFailed: 0, tokens: 0, cost: 0, peakMem: 0 });
  S.money = () => ''; S.stageLabel = s => s; S.costFootnote = () => '';
  return { S, grid: ids['ledger-grid'] };
}
const reason = row => row.children[7].textContent;

test('the teacher reads what the second look flagged, and when it could not look', () => {
  const { S } = page(), t = S.i18n.t.bind(S.i18n);
  assert.equal(S.secondLookText('violence,weapons', t), 'NVIDIA 安全检查：violence, weapons');
  assert.equal(S.secondLookText('unavailable', t), 'NVIDIA 安全检查：未运行');
  assert.equal(S.secondLookText('clear', t), '');
  assert.equal(S.secondLookText(undefined, t), '');
});

test('the codes stand in the reason column beside a refusal reason', () => {
  const { S, grid } = page(), t = S.i18n.t.bind(S.i18n);
  S.ledger.render([
    { stage: 'studio-safety', gate: 'pass', second_look: 'violence' },
    { stage: 'studio-safety', gate: 'fail', reason_code: 'unsafe_image', second_look: 'sexual' },
    { stage: 'studio-safety', gate: 'pass', second_look: 'clear' },
  ], t);
  const rows = grid.children.slice(1);
  assert.equal(reason(rows[0]), 'NVIDIA 安全检查：violence');
  assert.equal(reason(rows[1]), 'unsafe_image · NVIDIA 安全检查：sexual');
  assert.equal(reason(rows[2]), '');
});

test('the Chinese page says it in Chinese', () => {
  const { S } = page(); S.i18n.lang = 'zh'; const t = S.i18n.t.bind(S.i18n);
  assert.equal(S.secondLookText('violence', t), 'NVIDIA 安全检查：violence');
  assert.equal(S.secondLookText('unavailable', t), 'NVIDIA 安全检查：未运行');
});
