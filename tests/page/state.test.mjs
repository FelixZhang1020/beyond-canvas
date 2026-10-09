import test from 'node:test';
import assert from 'node:assert';
import { loadStudio } from './load.mjs';

function pixels(fill, n) {
  const data = new Uint8ClampedArray(n * 4);
  for (let i = 0; i < n; i++) { const c = fill(i); data[i * 4] = c[0]; data[i * 4 + 1] = c[1]; data[i * 4 + 2] = c[2]; data[i * 4 + 3] = 255; }
  return data;
}

test('the nearest paint is named by colour distance', () => {
  const S = loadStudio();
  assert.equal(S.nearestPaint([255, 111, 97]), 'coral');
  assert.equal(S.nearestPaint([80, 180, 250]), 'sky');
  assert.equal(S.nearestPaint([90, 210, 160]), 'leaf');
});

test('a white page is blank and a crayon page is not', () => {
  const S = loadStudio();
  const blank = S.imageStats(pixels(() => [252, 250, 245], 400));
  assert.equal(S.isBlank(blank), true);
  const drawn = S.imageStats(pixels((i) => (i % 3 === 0 ? [255, 111, 97] : i % 3 === 1 ? [79, 179, 255] : [255, 253, 248]), 900));
  assert.equal(S.isBlank(drawn), false);
  assert.deepEqual(drawn.colours.slice(0, 2), ['coral', 'sky']);
});

test('a colour that covers only a sliver of the ink is not dominant', () => {
  const S = loadStudio();
  const stats = S.imageStats(pixels((i) => (i % 40 === 0 ? [255, 179, 199] : i % 2 ? [255, 111, 97] : [79, 179, 255]), 800));
  assert.deepEqual(stats.dominant, ['coral', 'sky']);
  assert.ok(stats.colours.includes('rose'));
});

test('a photograph is mostly in-between colours with no paper; crayon on paper is not', () => {
  const S = loadStudio();
  let seed = 5; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  const photo = S.imageStats(pixels(() => [60 + rnd() * 120, 70 + rnd() * 100, 50 + rnd() * 110], 900));
  assert.equal(S.looksLikePhoto(photo), true);
  const crayon = S.imageStats(pixels((i) => (i % 4 === 0 ? [255, 111, 97] : i % 4 === 1 ? [79, 179, 255] : [255, 253, 248]), 900));
  assert.equal(S.looksLikePhoto(crayon), false);
});

test('a frame with no light in it is dark, and a normal drawing is not', () => {
  const S = loadStudio();
  assert.equal(S.isDark(S.imageStats(pixels(() => [8, 12, 9], 400))), true);
  assert.equal(S.isDark(S.imageStats(pixels((i) => (i % 2 ? [255, 111, 97] : [255, 253, 248]), 400))), false);
});

test('the ledger summary counts requests, gates, tokens and peak memory', () => {
  const S = loadStudio();
  const lines = [
    { request_id: 'r1', stage: 'studio-safety', gate: 'pass', tokens: 0, wall_s: 0.5, mem_before_gb: 57.1, mem_after_gb: 57.3 },
    { request_id: 'r1', stage: 'art-feedback', gate: 'pass', tokens: 700, wall_s: 2.6, mem_before_gb: 57.3, mem_after_gb: 58.9 },
    { request_id: 'r2', stage: 'studio-safety', gate: 'fail', tokens: 0, wall_s: 0.5, mem_before_gb: 57.1, mem_after_gb: 57.1 }
  ];
  const sum = S.ledgerSummary(lines);
  assert.equal(sum.requests, 2);
  assert.equal(sum.gatesPassed, 2);
  assert.equal(sum.gatesFailed, 1);
  assert.equal(sum.tokens, 700);
  assert.equal(sum.peakMem, 58.9);
  assert.deepEqual(S.ledgerSummary([]), { requests: 0, gatesPassed: 0, gatesFailed: 0, tokens: 0, cost: 0, wall: 0, peakMem: 0 });
});

test('the chosen entrance reaches the harness, and there is no suggestion switch', async () => {
  // This used to assert `entrance === 'colour'` — a default the page
  // contract forbids: the entrance is "made by hand on the class sheet". What
  // the test is actually here to protect is that the retired suggestion switch
  // has not come back and that the choice reaches the harness intact.
  const S = loadStudio();
  assert.equal('suggestions' in S.state.settings, false);
  let sent = null;
  S.state.transport = { createSession: (s) => { sent = s; return Promise.resolve({ session_id: 's1' }); } };
  await S.session.begin({ language: 'en', lessonIntent: '', entrance: 'sketch' });
  assert.equal(sent.entrance, 'sketch');
  assert.equal('suggestions' in sent, false);
});

test('the HTTP transport sends the entrance to the harness, not a suggestion switch', async () => {
  const calls = [];
  const fetch = (url, opts) => { calls.push({ url, opts }); return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ session_id: 's1' }) }); };
  const S = loadStudio({ files: ['src/23-transport-http.js'], globals: { fetch } });
  await S.transports.http.createSession({ language: 'zh', lessonIntent: '', entrance: 'sketch' });
  assert.equal(calls[0].url, '/api/session');
  assert.deepEqual(JSON.parse(calls[0].opts.body), { language: 'zh', lesson_intent: '', entrance: 'sketch' });
});

test('the mock feedback follows the entrance: colour asks into the picture, sketch reads the light and asks about the process', () => {
  const S = loadStudio({ files: ['src/22-transport-mock.js'] });
  const stats = { dominant: ['sky', 'coral'], colours: ['sky', 'coral'] };
  const colour = S.mockFeedback(stats, { language: 'en', lessonIntent: '', entrance: 'colour' }, 0);
  assert.match(colour.question, /happening/);
  assert.equal('suggestion' in colour, false);
  const sketch = S.mockFeedback(stats, { language: 'en', lessonIntent: '', entrance: 'sketch' }, 0);
  assert.match(sketch.text, /light|shadow/i);
  assert.match(sketch.text, /could try/);
  assert.match(sketch.question, /change|hard/i);
  assert.equal('suggestion' in sketch, false);
});

test('the ladder climbs to three and then stops', () => {
  const S = loadStudio();
  assert.equal(S.nextRung(undefined), 2, 'after the opening question, rung two');
  assert.equal(S.nextRung(1), 2);
  assert.equal(S.nextRung(2), 3);
  assert.equal(S.nextRung(3), null, 'there is no fourth rung; the answer is to move on');
});

test('a layer moves only inside its own window, and eases at both ends', () => {
  const S = loadStudio({ files: ['src/27c-motion.js'] });
  const layer = { move: 'drift', start_s: 1, end_s: 3, distance: [0.2, 0] };
  assert.equal(S.motion.progress(layer, 0), 0, 'still before it starts');
  assert.equal(S.motion.progress(layer, 5), 1, 'settled after it ends');
  assert.ok(Math.abs(S.motion.progress(layer, 2) - 0.5) < 0.001, 'halfway at the midpoint');
  assert.ok(S.motion.progress(layer, 1.2) < 0.2, 'eases in rather than jumping');
});

test('every move in the vocabulary produces a position, and nothing leaves the paper', () => {
  const S = loadStudio({ files: ['src/27c-motion.js'] });
  const moves = ['drift', 'sway', 'rise', 'grow', 'enter', 'exit'];
  for (const move of moves) {
    const layer = { box: [.1, .1, .4, .4], move: move, start_s: 0, end_s: 4, distance: [0.2, 0.1] };
    for (const t of [0, 1, 2, 3, 4]) {
      const at = S.motion.at(layer, t);
      assert.ok(Number.isFinite(at.dx) && Number.isFinite(at.dy), move + ' has a position at ' + t);
      assert.ok(Math.abs(at.dx) <= 1 && Math.abs(at.dy) <= 1, move + ' stays on the paper');
      assert.ok(at.alpha >= 0 && at.alpha <= 1, move + ' has a real opacity');
      assert.ok(at.scale >= 1, move + ' never shrinks the child out of view');
    }
  }
});

test('legacy enter and exit plans preserve the artwork and settle back into it', () => {
  const S = loadStudio({ files: ['src/27c-motion.js'] });
  const entering = { box: [.1, .1, .4, .4], move: 'enter', start_s: 0, end_s: 2, distance: [0.3, 0] };
  const leaving = { box: [.1, .1, .4, .4], move: 'exit', start_s: 0, end_s: 2, distance: [0.3, 0] };
  assert.equal(S.motion.at(entering, 0).alpha, 1);
  assert.equal(S.motion.at(entering, 2).alpha, 1);
  assert.equal(S.motion.at(leaving, 2).alpha, 1);
  assert.ok(Math.abs(S.motion.at(leaving, 2).dx) < 1e-8);
  assert.ok(S.motion.at(leaving, 1).dx > 0, 'the old plan still moves locally');
});

test('the recording is re-encoded as the one format every speech model reads', () => {
  const S = loadStudio({ files: ['src/27b-listen.js'], globals: { Blob, ArrayBuffer, DataView, Math } });
  const samples = new Float32Array([0, 0.5, -0.5, 1, -1]);
  const wav = S.listen.encodeWav({ getChannelData: () => samples });
  assert.equal(wav.type, 'audio/wav');
  assert.equal(wav.size, 44 + samples.length * 2, 'a 44 byte header and 16 bits a sample');
});

test('the wav header says 16 kHz, mono, 16 bit', async () => {
  const S = loadStudio({ files: ['src/27b-listen.js'], globals: { Blob, ArrayBuffer, DataView, Math } });
  const wav = S.listen.encodeWav({ getChannelData: () => new Float32Array([0, 0.25]) });
  const view = new DataView(await wav.arrayBuffer());
  const text = (at, n) => String.fromCharCode(...new Uint8Array(view.buffer, at, n));
  assert.equal(text(0, 4), 'RIFF');
  assert.equal(text(8, 4), 'WAVE');
  assert.equal(view.getUint16(22, true), 1, 'mono');
  assert.equal(view.getUint32(24, true), 16000, '16 kHz');
  assert.equal(view.getUint16(34, true), 16, '16 bit');
});

test('a class cannot begin without a hand-picked entrance', async () => {
  // The page shipped entrance: 'colour' as a default and pre-selected it, so a
  // teacher could press Begin without ever choosing. The spec settles this the
  // other way: the entrance is "made by hand on the class sheet; the page never
  // detects it" — and colour forbids correction while sketch expects it, so a
  // silent default is the difference between encouragement and criticism.
  const S = loadStudio();
  assert.equal(S.state.settings.entrance, null, 'the page must not carry a default entrance');

  await assert.rejects(
    () => S.session.begin({ language: 'en', lessonIntent: '' }),
    /entrance/i,
    'beginning without an entrance must be refused before any request is made');
});

test('what is remembered between classes is the language, never the entrance or the lesson note', () => {
  // The kind of class is picked by hand; the lesson note is now too (operator): one typed
  // for a sketch class was carried unseen into colour classes.
  const store = {};
  const S = loadStudio({ globals: { localStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
  } } });

  S.settings.remember({ language: 'en', lessonIntent: 'warm and cool', entrance: 'sketch' });
  const back = S.settings.recall();
  assert.equal(back.language, 'en');
  assert.ok(!('lessonIntent' in back), 'the lesson note must not survive a class');
  assert.ok(!('entrance' in back), 'the entrance must not survive a class');
  assert.ok(!JSON.stringify(store).includes('sketch'), 'and must not be written down at all');
  assert.ok(!JSON.stringify(store).includes('warm and cool'), 'nor the lesson note');
});

test('the studio is in Chinese whatever the browser prefers, and nothing can change it', () => {
  // The customer is a Chinese art centre. The page once read the browser's
  // language, so an English laptop opened an English studio for a Chinese class;
  // then a CN/EN switch replaced that, and teachers pressed it by accident and
  // could not read the panel that would put it back. Both are gone: there is one
  // language, and neither the browser nor anything a browser remembers moves it.
  const remembered = { 'beyond-canvas.class': JSON.stringify({ language: 'en', lessonIntent: '' }) };
  const S = loadStudio({ globals: {
    navigator: { language: 'en-GB' },
    localStorage: { getItem: (k) => (k in remembered ? remembered[k] : null), setItem: () => {} },
  } });
  assert.equal(S.i18n.lang, 'zh');
  assert.equal(S.i18n.t('mode.feedback'), '聊聊你的画');
  assert.equal(typeof S.settings.language, 'undefined', 'a language setting is back');
});

test('the teacher picks the drawings for the book, and never more than eight', () => {
  // 老师挑最多 8 张画. The page sent every drawing of the session, with no
  // selection and no cap, which is a different product: a machine deciding what
  // the book is about.
  const S = loadStudio();
  const drawings = Array.from({ length: 11 }, (_, i) => ({ id: 'd' + i }));

  // The common case is one tap, so the newest eight start chosen — visibly, and
  // changeable. A teacher who must tap eight times before she can begin is a
  // teacher who stops using it.
  const start = S.chooser.initial(drawings, 8);
  assert.equal(start.length, 8);
  assert.deepEqual(start, ['d3', 'd4', 'd5', 'd6', 'd7', 'd8', 'd9', 'd10']);

  const order = drawings.map(function (d) { return d.id; });
  const without = S.chooser.toggle(start, 'd5', 8, order);
  assert.ok(!without.includes('d5'), 'a tap takes one out');
  assert.equal(without.length, 7);

  const back = S.chooser.toggle(without, 'd5', 8, order);
  assert.deepEqual(back, start, 'and a tap puts it back where it was, not at the end');
});

test('the ninth drawing is refused rather than silently swapped in', () => {
  const S = loadStudio();
  const eight = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
  assert.equal(S.chooser.toggle(eight, 'i', 8), null, 'null is the page\'s cue to say why');
  assert.deepEqual(eight, ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'], 'and nothing changed');
});

test('a class of fewer than eight drawings starts with all of them', () => {
  const S = loadStudio();
  assert.deepEqual(S.chooser.initial([{ id: 'x' }, { id: 'y' }], 8), ['x', 'y']);
  assert.deepEqual(S.chooser.initial([], 8), []);
});

test('the book ends on a blank page that belongs to the child', () => {
  // 最后一页留白。结尾不该由机器写。问孩子一句「然后呢？」，把他的回答录下来
  // ——那就是结尾，也是他自己的声音说的最后一句话。
  const S = loadStudio();
  const pages = S.ending.add([{ text: 'a', url: 'u1' }, { text: 'b', url: 'u2' }]);
  assert.equal(pages.length, 3);
  const last = pages[pages.length - 1];
  assert.equal(last.ending, true);
  assert.equal(last.text, '', 'blank until he answers');
  assert.equal(last.url, '', 'and no picture: the ending is his words, not another drawing');
  assert.equal(S.ending.waiting(last), true);
});

test('what the child answers becomes the last page, and only the last page', () => {
  const S = loadStudio();
  const pages = S.ending.answer(S.ending.add([{ text: 'a', url: 'u1' }]), '然后他们就找到妈妈了。');
  assert.equal(pages[0].text, 'a', 'the pages before it are untouched');
  assert.equal(pages[1].text, '然后他们就找到妈妈了。');
  assert.equal(S.ending.waiting(pages[1]), false, 'it is no longer waiting');
});

test('an empty answer leaves the page waiting rather than ending the book on nothing', () => {
  const S = loadStudio();
  const pages = S.ending.answer(S.ending.add([{ text: 'a', url: 'u' }]), '   ');
  assert.equal(S.ending.waiting(pages[1]), true);
});

test('a book that already ends on the child is not given a second ending', () => {
  const S = loadStudio();
  const once = S.ending.add([{ text: 'a', url: 'u' }]);
  assert.equal(S.ending.add(once).length, once.length, 'opening it twice adds one ending, not two');
});

test('the ledger totals what the class spent, not only what it thought', async () => {
  // The backend started sending `cost` on every line. The summary
  // ignored it and the table had no column for it, so the screen built for judges
  // could say a class used 48,476 tokens and stay silent about money. Seen in the
  // browser: the header read 时间 / 步骤 / 检查 / Token / 秒 / 内存 GB / 原因.
  const S = loadStudio();
  const lines = [
    { request_id: 'r1', stage: 'studio-safety', gate: 'pass', tokens: 1906, cost: 0.000939, wall_s: 9.1 },
    { request_id: 'r1', stage: 'art-feedback', gate: 'pass', tokens: 10776, cost: 0.008412, wall_s: 38.7 }
  ];
  const sum = S.ledgerSummary(lines);
  assert.equal(sum.tokens, 12682);
  assert.equal(Number(sum.cost.toFixed(6)), 0.009351);
  assert.equal(S.ledgerSummary([]).cost, 0);
});

test('a stage label can name the kind of thing being made, and falls back when it cannot', async () => {
  // Seen once: "生成了短视频预览" on screen while a STILL was being made. The
  // stage name from the harness is the skill; the page knows the media kind and
  // now asks for the more specific label first. Since the still was retired the
  // skill makes one kind, so the plain label names the clip as well.
  const S = loadStudio();
  assert.equal(S.stageLabel('painting-to-animation', 'video'), S.i18n.t('stage.painting-to-animation.video'));
  assert.equal(S.stageLabel('painting-to-animation'), '生成了短视频预览');
  assert.equal(S.stageLabel('painting-to-animation', 'no-such-kind'), S.stageLabel('painting-to-animation'));
  assert.equal(S.stageLabel('sketch-to-3d', null), S.stageLabel('sketch-to-3d'));
});

test('a zero on the ledger says whether it was prepaid or simply not billed', async () => {
  // StepFun First runs on a subscription, so its reading, speech
  // and hearing report 0 per call. Studio.money prints '0' for that and for a
  // stage that ran on our own GPU machine, which are different facts — one is
  // paid for in advance, the other never cost anything. Without the footnote a
  // teacher reads the plan's zeros as the studio having run free.
  const S = loadStudio();
  assert.equal(S.costFootnote('stepfun'), 'ledger.plan');
  assert.equal(S.costFootnote('current'), '');
  assert.equal(S.costFootnote(undefined), '');
  // And the wording exists in both languages, because the ledger is a screen the
  // teacher reads in Chinese.
  {
    const said = S.i18n.t('ledger.plan');
    assert.notEqual(said, 'ledger.plan', 'no wording for the footnote');
    assert.ok(said.includes('StepFun First'), 'the footnote should name the deployment');
  }
});


test('a lesson note an older page saved in the browser is not carried into a new class', () => {
  const store = { 'beyond-canvas.class': JSON.stringify({ language: 'zh', lessonIntent: '几何体结构与明暗' }) };
  const S = loadStudio({ globals: { localStorage: {
    getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); },
  } } });
  assert.ok(!('lessonIntent' in S.settings.recall()));
});
