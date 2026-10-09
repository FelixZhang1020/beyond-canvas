// How the book's pictures look, step 3 of the storybook (operator). The child's originals, each page
// its drawing or, where one was made, its clip; or every page redrawn in one picture-book style by FLUX on the
// Spark. For a style the teacher first sees page 1 in all seven and picks one; the rest of the book is then drawn
// in it and the book binds by itself. The drawing itself is 29a-creation.js's job: this names what to send.
(function () {
  const S = Studio, st = S.state, t = (key, vars) => S.i18n.t('creation.' + key, vars);
  const esc = text => String(text || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // skills/drawings-to-storybook/assets/picture-styles.json, in its order (tests/making/test_book_pictures.py holds them together).
  const STYLES = ['watercolour', 'gouache', 'paper', 'clay', 'pencil', 'storybook', 'ink'];
  // pictures[drawing][style] = {url, changed, again}, kept for the sitting whatever the book's order becomes.
  let offered = false, story = '', look = 'original', motion = {}, picked = '', pictures = {}, bindNext = false;
  const drawing = id => st.drawings.find(d => d.id === id);
  const styled = () => look !== 'original';
  function sameStory(ids) { const now = ids.join(','); if (now !== story) { story = now; look = 'original'; motion = {}; picked = ''; bindNext = false; } }
  function missing(ids, style) { return ids.filter(id => !(pictures[id] || {})[style]); }
  function button(key, action, primary, disabled) {
    return '<button type="button" class="btn' + (primary ? ' primary' : '') + '" data-create="' + action + '"' + (disabled ? ' disabled' : '') + '>' + esc(t(key)) + '</button>';
  }
  function choice(value, label, note) {
    return '<button type="button" data-look="' + value + '" aria-pressed="' + ((value === 'styled') === styled()) + '"><strong>'
      + esc(t(label)) + '</strong><span>' + esc(t(note)) + '</span></button>';
  }
  function originals(ids, hasClip) {
    return '<div class="creation-picks book-look-pages">' + ids.map((id, i) => {
      const d = drawing(id), clip = hasClip(id), on = clip && motion[id] !== false;
      const toggle = clip ? '<span class="book-look-motion">'
        + '<button type="button" data-motion="' + esc(id) + '" data-on="0" aria-pressed="' + !on + '">' + esc(t('lookStill')) + '</button>'
        + '<button type="button" data-motion="' + esc(id) + '" data-on="1" aria-pressed="' + on + '">' + esc(t('lookClip')) + '</button></span>'
        : '<small>' + esc(t('lookNoClip')) + '</small>';
      // A page set to its clip plays it here (operator), the drawing showing until it has loaded (attach).
      const picture = on ? '<video class="book-look-clip" data-clip="' + esc(id) + '" muted loop playsinline autoplay'
        + (d ? ' poster="' + esc(d.url) + '"' : '') + '></video>' : d ? '<img src="' + esc(d.url) + '" alt="">' : '';
      return '<div class="creation-pick">' + picture + '<span>' + esc(t('pageN', {n: i + 1})) + '</span>' + toggle + '</div>';
    }).join('') + '</div>';
  }
  function styles(first) {
    const drawn = pictures[first] || {};
    return '<div class="creation-picks book-look-styles">' + STYLES.map(style => {
      const p = drawn[style], name = esc(t('style.' + style));
      if (!p) return '<div class="creation-pick is-missing"><span>' + name + '</span><small>' + esc(t('lookMissing')) + '</small></div>';
      return '<button type="button" class="creation-pick" data-style="' + style + '" aria-pressed="' + (picked === style) + '"><img src="' + esc(p.url)
        + '" alt=""><span>' + name + '</span>' + (p.changed ? '<small class="is-changed">' + esc(t('lookChanged')) + '</small>' : '') + '</button>';
    }).join('') + '</div>';
  }
  // Every style, named and described in the work card, whether or not page 1 has been drawn in it yet
  // (operator: the pictures alone did not say what the choices were). Chosen here or on its picture, the same.
  function list(first, shown) {
    const drawn = pictures[first] || {};
    return '<div class="book-look-list">' + STYLES.map(style => {
      const p = drawn[style], state = !shown ? '' : !p ? t('lookMissing') : p.changed ? t('lookChanged') : '';
      return '<button type="button" data-style="' + style + '" aria-pressed="' + (picked === style) + '"' + (p ? '' : ' disabled')
        + '><strong>' + esc(t('style.' + style)) + '</strong><span>' + esc(t('styleNote.' + style)) + '</span>'
        + (state ? '<small' + (p ? ' class="is-changed"' : '') + '>' + esc(state) + '</small>' : '') + '</button>';
    }).join('') + '</div>';
  }
  S.bookLook = {
    // Offered where the studio has FLUX and the class is a colour class: sketches have no storybook.
    configure(skills) { offered = !!skills && skills.includes('book-pictures'); },
    offered() { return offered && st.settings.entrance === 'colour'; },
    view(ids, hasClip) {
      sameStory(ids);
      if (!S.bookLook.offered()) look = 'original';
      const head = '<div class="book-look-choice">' + choice('original', 'lookOriginal', 'lookOriginalNote')
        + (S.bookLook.offered() ? choice('styled', 'lookStyled', 'lookStyledNote') : '') + '</div>';
      if (!styled()) return { content: head + originals(ids, hasClip), actions: button('back', 'look-back') + button('lookMake', 'look-bind', true) };
      const first = ids[0], shown = Object.keys(pictures[first] || {}).length > 0;
      // A style that did not pass its checks can be drawn again; the ones drawn are kept (book_pictures.py).
      const gaps = shown && STYLES.some(style => !pictures[first][style]);
      return { content: head + '<p>' + esc(t(shown ? 'lookPick' : 'lookFirstNote')) + '</p>' + list(first, shown) + (shown ? styles(first) : ''),
        actions: button('back', 'look-back') + (shown ? (gaps ? button('lookRetry', 'look-first') : '') + button('lookUse', 'look-use', true, !picked)
          : button('lookFirst', 'look-first', true)) };
    },
    // What a press in this step asks for: a request to send ([skill, ids, options]), 'render', or nothing.
    click(data, ids) {
      if (data.look) { look = data.look === 'styled' ? (picked || 'styled') : 'original'; return 'render'; }
      if (data.motion) { motion[data.motion] = data.on === '1'; return 'render'; }
      if (data.style) { picked = data.style; look = picked; return 'render'; }
      if (data.create === 'look-first') return ['book-pictures', ids.slice(0, 1), {styles: STYLES}];
      if (data.create === 'look-use' && picked) {
        // The pages still to draw in her style, and a sample of it the check flagged: samples are drawn once, and
        // the one she picks gets its second try here, beside the rest of the book (book_pictures.py).
        const rest = ids.filter(id => { const p = (pictures[id] || {})[picked]; return !p || (p.changed && !p.again); });
        bindNext = true;
        return rest.length ? ['book-pictures', rest, {styles: [picked]}] : S.bookLook.bind(ids);
      }
      if (data.create === 'look-bind') return S.bookLook.bind(ids);
      return null;
    },
    bind(ids) {
      bindNext = false;
      const options = {pages: st.storyDraft.pages, look: styled() && picked ? picked : 'original'};
      if (options.look === 'original') options.motion = ids.filter(id => motion[id] !== false);
      return ['drawings-to-storybook', ids, options];
    },
    // Once the rest of a style's pages are drawn the book binds by itself (29a-creation.js asks, when idle).
    due(ids) { return bindNext && styled() && !!picked && !missing(ids, picked).length; },
    completed(out) {
      (out.pictures || []).forEach(p => {
        (pictures[p.drawing_id] ||= {})[p.style] = {url: p.url, changed: !!p.changed, again: !!p.again};
      });
    },
    stopped() { bindNext = false; },
    // Each clip playing in step 3 gets its file once the screen is drawn: `clip(id)` promises it (29a-creation.js).
    attach(root, clip) {
      (root.querySelectorAll ? [...root.querySelectorAll('video[data-clip]')] : []).forEach(video => {
        const source = clip(video.dataset.clip);
        if (source) source.then(url => {
          if (!url || video.getAttribute('src') === url) return;
          video.src = url; const play = video.play && video.play(); if (play && play.catch) play.catch(() => {});
        }).catch(() => {});
      });
    },
    // Which pages of the bound book may have changed the child's picture, for the teacher to look at.
    changedPages(ids, out) {
      if (!out || !out.look || out.look === 'original') return [];
      return ids.map((id, i) => ((pictures[id] || {})[out.look] || {}).changed ? i + 1 : 0).filter(Boolean);
    },
  };
})();
