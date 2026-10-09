// The logo travels beside the page, as the entrance photographs do: the header's Splat and the home screen's logo,
// cut from the video's frames by docs/design/logo/make_logo.py. The two icons are written into the page instead:
// Chrome on an iPhone or iPad never showed the tab icon as a file, and "Add to Home Screen" is refused one.
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync, statSync } from 'node:fs';

const page = readFileSync(new URL('../../studio/page/index.html', import.meta.url), 'utf8');
const brand = name => new URL(`../../studio/page/assets/brand/${name}`, import.meta.url);

test('the header and the home screen each ask for their logo file, and each is there', () => {
  // Named one by one: a sweep that passes over an empty set passes for the wrong reason.
  const wanted = [['header Splat', 'splat-header.png'], ['home screen logo', 'lockup-header.png']];
  for (const [what, name] of wanted) {
    assert.equal(page.split(`="assets/brand/${name}"`).length - 1, 1, `the ${what} is not asked for exactly once`);
    assert.ok(statSync(brand(name)).size > 0, `${name} is missing`);
  }
  assert.ok(!page.includes('"/assets/brand/'), 'an absolute logo path would break under a prefix');
});

test('the tab icon is written into the page, so no certificate stands between a phone and it', () => {
  // Chrome on an iPhone or iPad fetches a tab icon apart from the page and refuses the class's own certificate
  // there; inside the page there is nothing to fetch. It is the same picture as the file make_logo.py writes.
  const icons = [...page.matchAll(/<link rel="icon" href="data:image\/png;base64,([^"]+)"/g)];
  assert.equal(icons.length, 1, 'the page does not carry exactly one tab icon of its own');
  assert.ok(Buffer.from(icons[0][1], 'base64').equals(readFileSync(brand('tab-icon.png'))),
    'the tab icon in the page is not tab-icon.png');
  assert.ok(!/<link rel="icon" href="assets\//.test(page), 'a tab icon a phone cannot fetch is still offered');
});

test('the home-screen icon is written into the page, so the class door has nothing to refuse', () => {
  // "Add to Home Screen" fetches its icon on its own, without the class password, and the door answers 401.
  const icons = [...page.matchAll(/<link rel="apple-touch-icon" href="data:image\/png;base64,([^"]+)"/g)];
  assert.equal(icons.length, 1, 'the page does not carry exactly one home-screen icon of its own');
  assert.ok(Buffer.from(icons[0][1], 'base64').equals(readFileSync(brand('apple-touch-icon.png'))),
    'the home-screen icon in the page is not apple-touch-icon.png');
  assert.ok(!page.includes('"assets/brand/apple-touch-icon.png"'), 'a home-screen icon the door refuses is still asked for');
});

test('the header shows the crayon Splat, not the drawn blob it replaced', () => {
  const home = page.match(/<button class="brand"[^>]*id="btn-home"[^>]*>([\s\S]*?)<\/button>/);
  assert.ok(home, 'no home button in the header');
  assert.ok(home[1].includes('class="brand-mark"'), 'the header has no logo mark');
  assert.ok(!home[1].includes('brand-eye'), 'the old drawn eyes are still in the header');
});

test('the home screen opens with the logo and the slogan right after it', () => {
  const intro = page.match(/<div class="portfolio-intro">([\s\S]*?)<\/div>/);
  assert.ok(intro, 'no title block on the home screen');
  const logo = intro[1].match(/<img class="portfolio-logo"[^>]*>/);
  assert.ok(logo, 'the home screen has no logo');
  assert.ok(intro[1].indexOf(logo[0]) < intro[1].indexOf('<h1'), 'the logo does not come before the slogan');
  assert.match(logo[0], /aria-label="[^"]+"/, 'a screen reader would get no name for the logo');
  const title = intro[1].match(/<h1[^>]*>([^<]*)<\/h1>/);
  assert.ok(title && !title[1].includes('画里画外'), 'the title still repeats the name the logo already shows');
});
