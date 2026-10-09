// What the child takes home. The document's last box promises the finished work
// leaves the machine — 会动的画、绘本、视频文件 — while only the raw drawings and
// recordings are cleared. Until this module existed the page could export one
// thing: the ledger's JSON.
import test from 'node:test';
import assert from 'node:assert';
import { loadStudio } from './load.mjs';

function studio() {
  return loadStudio({ files: ['src/27d-keepsake.js'] });
}

const PAGES = [
  { art: 'data:image/png;base64,AAA', text: '他们要去找他的妈妈。' },
  { art: 'data:image/png;base64,BBB', text: '路上特别热，所以太阳画得很大。' },
];

test('the book leaves as one file that opens anywhere', () => {
  const S = studio();
  const html = S.keepsake.bookHtml('我的故事', PAGES);
  assert.ok(html.startsWith('<!doctype html>'), 'a file a parent can double-click');
  assert.ok(html.includes('我的故事'));
  for (const page of PAGES) {
    assert.ok(html.includes(page.text), "the child's own words are the point of the file");
    assert.ok(html.includes(page.art));
  }
});

test('nothing in the exported book reaches for the network', () => {
  // The studio promises no fonts, scripts or pictures come from anywhere. A
  // keepsake that only renders while online would break that promise in the one
  // artefact that leaves the building.
  const S = studio();
  const html = S.keepsake.bookHtml('我的故事', PAGES);
  assert.ok(!/https?:\/\//.test(html), 'an http reference would need the network');
  assert.ok(!/<script/i.test(html), 'a keepsake does not need to run code');
  assert.ok(!/src="(?!data:)/.test(html), 'every image must be embedded, not linked');
});

test('a page the child never spoke for still gets its picture', () => {
  // 每一段都可以掉: the child says nothing, the book still holds the drawing.
  const S = studio();
  const html = S.keepsake.bookHtml('我的故事', [{ art: 'data:image/png;base64,CCC', text: '' }]);
  assert.ok(html.includes('data:image/png;base64,CCC'));
});

test('the file is named after the work, not after the machine', () => {
  const S = studio();
  // The studio speaks Chinese only, so a saved file does too.
  assert.match(S.keepsake.filename('book'), /^画里画外.*\.html$/);
  assert.match(S.keepsake.filename('motion'), /^画里画外.*\.webm$/);
  assert.match(S.keepsake.filename('still'), /^画里画外.*\.png$/);
});

test('two exports a minute apart do not carry the same name', () => {
  const S = studio();
  const a = S.keepsake.filename('book', new Date('2026-09-05T14:30:00'));
  const b = S.keepsake.filename('book', new Date('2026-09-05T14:31:00'));
  assert.notEqual(a, b, 'the name carries the time');
});

test('the text a child spoke is escaped, not rendered as markup', () => {
  const S = studio();
  const html = S.keepsake.bookHtml('t', [{ art: 'data:x', text: '<b>龙</b> & 太阳' }]);
  assert.ok(html.includes('&lt;b&gt;龙&lt;/b&gt; &amp; 太阳'),
    'a child who says "<" is not writing markup');
});

test('the blank last page exports as the words alone, with no broken picture', () => {
  // The ending has no drawing: it is what the child said after the story ran
  // out. An <img> with an empty src would show as a broken frame in the file a
  // parent keeps.
  const S = studio();
  const html = S.keepsake.bookHtml('t', [
    { art: 'data:image/png;base64,AAA', text: '从前' },
    { art: '', text: '然后他们就找到妈妈了。' },
  ]);
  assert.ok(html.includes('然后他们就找到妈妈了。'));
  assert.equal((html.match(/<img/g) || []).length, 1, 'one picture, one wordless ending');
  assert.ok(!/src=""/.test(html));
});

test('an ending the child has not given yet is left out of the file, not kept as an empty page', async () => {
  // Before the fix: exported before the child spoke, the book ended on a page with nothing on it but "2 / 2".
  const S = loadStudio({ files: ['src/27d-keepsake.js'], globals: { Blob } }); let saved = null;
  S.keepsake.save = blob => { saved = blob; };
  await S.keepsake.book('t', [{ url: 'data:image/png;base64,AAA', text: '从前' }, { ending: true, url: '', text: '' }]);
  const html = await saved.text();
  assert.equal((html.match(/class="leaf/g) || []).length, 1, 'one page, the one with a drawing');
  assert.ok(html.includes('1 / 1'));
});
