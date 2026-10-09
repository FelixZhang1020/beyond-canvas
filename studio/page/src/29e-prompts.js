// The prompt page in system management: every instruction a model is given, word for word, read only.
// The server reads the wording from where the studio itself reads it (studio/core/prompt_book.py), so this
// page shows what is sent, not a copy. Nothing here writes: there is no route that could take a change.
(function () {
  const S = Studio, $ = function (id) { return document.getElementById(id); };
  const t = function (key, vars) { return S.i18n.t(key, vars); };
  let epoch = 0;

  function element(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  // Labels arrive in both languages; the page's own language picks one.
  function pick(words) { return (words && (words[S.i18n.lang] || words.en)) || ''; }

  function entry(item) {
    const box = element('details', 'prompt-entry'), summary = element('summary');
    summary.append(element('span', 'prompt-label', pick(item.label)), element('code', 'prompt-source', item.source));
    box.append(summary, item.missing
      ? element('p', 'prompt-missing', t('prompts.missing', { source: item.source }))
      : element('pre', 'prompt-text', item.text));
    return box;
  }

  function render(book) {
    const list = $('prompts-list');
    list.replaceChildren();
    for (const group of (book && book.groups) || []) {
      const section = element('section', 'prompt-group'), head = element('h3');
      head.append(element('span', '', pick(group.name)), element('small', '', t('prompts.count', { n: group.entries.length })));
      section.append(head);
      if (group.note) section.append(element('p', 'prompt-note', pick(group.note)));
      group.entries.forEach(function (item) { section.append(entry(item)); });
      list.append(section);
    }
  }

  async function open() {
    const mine = ++epoch, status = $('prompts-status'), transport = S.state.transport;
    $('admin-overlay').hidden = true;
    $('prompts-list').replaceChildren();
    $('prompts-overlay').hidden = false;
    if (!transport || !transport.prompts) { status.textContent = t('prompts.preview'); return; }
    status.textContent = t('prompts.loading');
    try {
      const book = await transport.prompts();
      if (mine !== epoch) return;
      render(book);
      status.textContent = '';
    } catch (_) {
      if (mine === epoch) status.textContent = t('prompts.failed');
    }
  }

  function close() {
    epoch++;
    $('prompts-overlay').hidden = true;
    $('admin-overlay').hidden = false;
  }

  if (typeof document !== 'undefined' && document.getElementById('admin-prompts')) {
    $('admin-prompts').addEventListener('click', open);
    $('prompts-close').addEventListener('click', close);
  }
  S.prompts = { open: open, close: close, render: render };
})();
