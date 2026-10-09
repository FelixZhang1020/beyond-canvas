#!/bin/sh
# Concatenate the source parts into one self-contained page, then check its structure.
set -e
cd "$(dirname "$0")"
{
  # The two icons are the only pictures written into the page. Chrome on an iPhone or iPad fetches a tab icon apart
  # from the page and refuses the class's own certificate there; "Add to Home Screen" fetches its icon without the
  # class password, and the door refuses it. Inside the page there is nothing to fetch (operator).
  python3 - <<'PY'
import base64
from pathlib import Path

head = Path('src/00-head.html').read_text(encoding='utf-8')
for icon in ('assets/brand/tab-icon.png', 'assets/brand/apple-touch-icon.png'):
    if head.count(f'href="{icon}"') != 1:
        raise ValueError(f'Expected the head to ask for {icon} once')
    inline = 'data:image/png;base64,' + base64.b64encode(Path(icon).read_bytes()).decode()
    head = head.replace(f'href="{icon}"', f'href="{inline}"')
print(head, end='')
PY
  echo '<style>'; cat src/01-tokens.css src/02-glass.css src/03-layout.css src/04-components.css src/04b-chat-panel.css src/05-portfolio.css src/05b-review.css src/06-book-reader.css src/07-creation.css src/08-deployments.css | python3 lean.py css; echo '</style>'
  # Write the Chinese labels in, so the page paints in the right language before
  # its script has arrived. See first_paint.py. The entrance photographs stay in
  # their own files and the server sends them from assets/entrance: they used to
  # be written in here as base64, which was 47% of the page and
  # compressed to nothing.
  python3 - <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, '.')
from first_paint import chinese_table, fill

markup = Path('src/10-app.html').read_text(encoding='utf-8')
markup = fill(markup, chinese_table(Path('locales/zh.js').read_text(encoding='utf-8')))
for name in ('colour-painting', 'sketch-study'):
    asset = Path('assets/entrance') / f'{name}.jpg'
    if markup.count(f'src="{asset.as_posix()}"') != 1 or not asset.is_file():
        raise ValueError(f'Expected one entrance illustration, and the file itself: {asset}')
print(markup)
PY
  echo '<script>'
  # Reuse the voice lab's ES modules without adding a second bundle or network imports.
  python3 - <<'PY'
from pathlib import Path
print('window.Studio = window.Studio || {}; (function () {')
for name in ('audio.mjs', 'question-voice.mjs', 'stream-voice.mjs'):
    code = (Path('../voice_lab') / name).read_text()
    print('\n'.join(line.removeprefix('export ') for line in code.splitlines()
                    if not line.startswith('import ')))
print('Studio.StreamingQuestionVoice = StreamingQuestionVoice; })();')
PY
  cat src/20-i18n.js locales/zh.js src/21-state.js src/22-transport-mock.js src/23-transport-http.js \
      src/24-glass.js src/24b-dialogs.js src/24c-portfolio.js src/25-camera.js src/25b-samples.js src/26-companion.js src/26a-pet-drag.js src/26d-chat-panel.js src/26b-classroom-voice.js src/27-media.js src/27b-listen.js \
      src/27c-motion.js src/27d-keepsake.js src/27e-relight.js src/27f-mesh.js src/27g-cloud-relight.js src/27h-showpiece.js src/27i-figure.js \
      src/28-book.js src/28b-book-turn.js src/29-ledger.js src/26c-course-history.js src/26e-remove-drawing.js src/26f-chat-edit.js src/26g-delete-class.js src/26h-course-name.js \
      src/29a-creation.js src/29b-task-status.js src/29c-task-navigation.js src/29d-deployments.js src/29e-prompts.js src/29f-rejoin.js src/29g-text-stream.js src/29h-lanes.js src/29i-microphones.js src/29j-studio-replies.js src/29k-main-button.js src/29l-book-look.js \
      src/30-main.js | python3 lean.py js   # comments stay in the source; see lean.py
  echo '</script>'
} > index.html
python3 check.py index.html
