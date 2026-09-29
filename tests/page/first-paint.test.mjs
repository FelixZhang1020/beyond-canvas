// The page must already be Chinese in the bytes the browser paints, before any
// script runs. Over the classroom's public link the script arrives seconds after
// the markup, and those seconds used to be spent showing English.
//
// The build writes the Chinese in with a Python scanner over locales/zh.js.
// This checks the result against the same table JavaScript itself reads, which
// is a different method and can therefore actually disagree with the scanner.
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { loadStudio } from './load.mjs';

const page = readFileSync(new URL('../../studio/page/index.html', import.meta.url), 'utf8');
const markup = page.slice(0, page.indexOf('<script>'));
const plain = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');

function table() {
  const S = loadStudio();
  return (key) => (S.strings.zh[key] !== undefined ? S.strings.zh[key] : S.strings.en[key]);
}

test('every label the browser paints first is already the one the teacher reads', () => {
  const t = table();
  const labels = Array.from(markup.matchAll(/<(\w+)\b[^>]*\bdata-t="([\w.-]+)"[^>]*>([^<]*)<\/\1>/g));
  // A label the pattern cannot read must not pass unseen.
  assert.equal(labels.length, markup.match(/\bdata-t="/g).length);
  assert.ok(labels.length > 100, `only ${labels.length} labels found`);
  for (const [, , key, text] of labels) assert.equal(plain(text), t(key), key);
});

test('every example written into a text box is painted in Chinese too', () => {
  const t = table();
  const hints = Array.from(markup.matchAll(/<\w+\b[^>]*\bdata-t-ph="([\w.-]+)"[^>]*>/g));
  assert.equal(hints.length, markup.match(/\bdata-t-ph="/g).length);
  for (const [tag, key] of hints) {
    const written = tag.match(/\bplaceholder="([^"]*)"/);
    assert.ok(written, `${key} has no placeholder to paint`);
    assert.equal(plain(written[1]), t(key), key);
  }
});

test('the studio names itself in Chinese before a word of script has run', () => {
  // The three a teacher reads first. Named one by one, because a sweep that
  // passes over an empty set passes for the wrong reason.
  const t = table();
  for (const key of ['brand', 'mode.feedback', 'portfolio.back']) {
    assert.ok(markup.includes(`>${t(key)}<`), `${key} is not painted as ${t(key)}`);
  }
  assert.ok(!markup.includes('>Talk about it<'), 'an English label is still painted');
});
