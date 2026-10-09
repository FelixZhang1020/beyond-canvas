// Load the page's pure modules into a sandbox so node can test them without a browser.
import { readFileSync } from 'node:fs';
import { createContext, runInContext } from 'node:vm';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..', 'studio', 'page');
const PURE = ['src/20-i18n.js', 'locales/zh.js', 'src/21-state.js'];

// options.files adds modules after the pure ones; options.globals fakes what they reach for.
export function loadStudio(options) {
  const opts = options || {};
  const sandbox = Object.assign({ console }, opts.globals || {});
  sandbox.window = sandbox;
  createContext(sandbox);
  for (const file of PURE.concat(opts.files || [])) {
    runInContext(readFileSync(join(root, file), 'utf8'), sandbox, { filename: file });
  }
  return sandbox.Studio;
}
