// The course portfolio sits above the classroom; history never re-runs a model.
window.Studio = window.Studio || {};
Studio.portfolio = {
  version: 0, resultVersion: 0, detail: null, offset: null, busy: false,
  selected: {}, workspace: null,
  showWorkspace(course, view) {
    if (view !== 'create') Studio.sketchWorkbench?.close();
    const previousView = this.el('app').dataset.courseView;
    this.workspace = course;
    this.el('course-space').hidden = false;
    this.el('app').dataset.courseView = view;
    // Hides the storybook tab in a sketch class (02-glass.css).
    const entrance = course.entrance || '', entranceChanged = this.el('app').dataset.entrance !== entrance;
    this.el('app').dataset.entrance = entrance;
    if (view === 'create' && (previousView !== 'create' || entranceChanged)) this.el('mode').refresh?.();
    this.el('space-title').textContent = course.title || Studio.i18n.t('class.' + course.entrance);
    this.el('space-state').textContent = this.t(course.ended_at ? 'ended' : 'saved');
    this.el('space-complete').hidden = !!course.ended_at;
    this.el('space-reopen').hidden = !course.ended_at;
    this.el('creation-workspace').inert = view !== 'create';
  },
  hideWorkspace() {
    Studio.sketchWorkbench?.close();
    this.bookVersion = (this.bookVersion || 0) + 1;
    Studio.book?.closeInline?.();
    this.workspace = null; this.el('course-space').hidden = true;
    this.el('app').dataset.courseView = ''; this.el('app').dataset.entrance = '';
    this.el('creation-workspace').inert = true;
  },
  create(reopen = false) {
    if (this.el('app').dataset.courseView === 'create' && !reopen) return;
    const course = this.workspace || this.detail;
    if (!course || (course.ended_at && !reopen)) return;
    return this.withAction(() => this.actions.editCourse(course, reopen, this.selected[course.id]));
  },
  async api(path, options) {
    const response = await fetch('/api/courses' + path, options);
    if (!response.ok) throw new Error('Course history unavailable');
    return response.status === 204 ? null : response.json();
  },
  el(id) { return document.getElementById(id); },
  t(key, vars) { return Studio.i18n.t('portfolio.' + key, vars); },
  text(tag, value, cls) {
    const element = document.createElement(tag); element.textContent = value;
    if (cls) element.className = cls; return element;
  },
  date(value) {
    return new Intl.DateTimeFormat(Studio.i18n.lang === 'zh' ? 'zh-CN' : 'en-GB',
      { month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(value));
  },
  init(actions) {
    this.actions = actions;
    this.el('space-back').onclick = () => actions.home();
    this.el('space-complete').onclick = () => actions.completeCourse(this.workspace.id);
    this.el('space-reopen').onclick = () => this.create(true);
    ['teacher', 'stage1', 'stage2', 'books', 'originals'].forEach(section => {
      this.el('review-' + section).onclick = () => this.reviewSection(section);
    });
    this.el('review-output-retry').onclick = () => this.loadComparison(this.shownId || this.el('review-output').value);
    this.el('review-book-retry').onclick = () => this.loadBook();
    this.el('portfolio-home').onclick = () => this.open();
    this.el('portfolio-new').onclick = () => actions.newClass();
    this.el('portfolio-first').onclick = () => actions.newClass();
    this.el('course-back').onclick = () => this.open();
    this.el('portfolio-more').onclick = () => this.load(true);
    this.el('portfolio-retry').onclick = () => this.detail ? this.openCourse(this.detail.id) : this.load();
  },
  async withAction(action) {
    if (this.transition) return;
    this.transition = true; this.el('portfolio').inert = true; this.el('course-space').inert = true; this.message('openingEditor');
    try { await action(); }
    catch (_) { this.message('failed', true); }
    finally { this.transition = false; this.el('portfolio').inert = false; this.el('course-space').inert = false; }
  },
  message(key, retry = false) {
    this.el('portfolio-status').textContent = key ? this.t(key) : '';
    this.el('space-status').textContent = key ? this.t(key) : '';
    this.el('portfolio-retry').hidden = !retry;
  },
  open() {
    if (this.transition) return;
    this.disposeComparison();
    this.hideWorkspace();
    this.el('portfolio').setAttribute('aria-labelledby', 'portfolio-title');
    this.el('portfolio').hidden = false; this.el('portfolio-list').hidden = false;
    this.el('course-profile').hidden = true; this.detail = null;
    return this.load();
  },
  close() { this.disposeComparison(); this.bookVersion = (this.bookVersion || 0) + 1; Studio.book?.closeInline?.(); this.version++; this.el('portfolio').hidden = true; },
  async load(more = false) {
    if (more && (this.offset === null || this.busy)) return;
    const version = ++this.version;
    const offset = more ? this.offset : 0;
    if (!more) { this.el('portfolio-grid').replaceChildren(); this.offset = null; }
    this.busy = true; this.el('portfolio-more').hidden = true;
    this.el('portfolio-empty').hidden = true; this.message('loading');
    try {
      const query = new URLSearchParams({ offset });
      const response = await this.api('?' + query);
      if (version !== this.version) return;
      response.items.forEach(course => this.el('portfolio-grid').appendChild(this.card(course)));
      this.offset = response.next_offset; this.el('portfolio-more').hidden = this.offset === null;
      this.el('portfolio-empty').hidden = response.total > 0;
      this.el('portfolio-empty-title').textContent = this.t('emptyTitle');
      this.el('portfolio-empty-note').textContent = this.t('emptyNote');
      this.message('');
    } catch (_) {
      if (version === this.version) { this.detail = null; this.el('portfolio-list').hidden = false; this.message('failed', true); }
    }
    finally { if (version === this.version) this.busy = false; }
  },
  card(course) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'course-card';
    const art = this.text('div', '', 'course-cover');
    if (course.cover_url) {
      const image = new Image(); image.src = course.cover_url; image.alt = ''; image.loading = 'lazy'; art.appendChild(image);
    } else art.appendChild(this.text('span', this.t('noArtwork')));
    button.appendChild(art);
    const copy = this.text('div', '', 'course-card-copy');
    copy.appendChild(this.text('span', Studio.i18n.t('class.' + course.entrance), 'course-tag'));
    const name = copy.appendChild(this.text('h2', course.title)); name.title = course.title;
    copy.appendChild(this.text('p', this.date(course.created_at) + ' · ' + this.t('drawingsCount', { n: course.drawing_count })));
    copy.appendChild(this.text('span', this.t(course.ended_at ? 'ended' : 'saved'), 'course-state'));
    button.appendChild(copy); button.onclick = () => this.openCourse(course.id); return button;
  },
  async openCourse(id) {
    if (this.transition) return;
    this.disposeComparison();
    const version = ++this.version;
    this.hideWorkspace();
    this.el('portfolio').setAttribute('aria-labelledby', 'portfolio-title');
    this.el('portfolio').hidden = false;
    this.detail = { id }; this.el('portfolio-list').hidden = true; this.el('course-profile').hidden = true;
    this.message('loading');
    try {
      const course = await this.api('/' + encodeURIComponent(id));
      if (version !== this.version) return;
      this.detail = course; this.workspace = course;
      const conversations = course.activities.filter(a => a.summary.kind === 'text' && a.skill !== 'teacher-review' && !a.summary.status);
      const results = course.activities.filter(a => a.summary.kind !== 'text' || (a.skill === 'teacher-review' && !a.summary.status));
      const savedBooks = results.filter(a => a.summary.kind === 'book');
      const selectedBook = savedBooks.find(a => a.ending) || savedBooks.at(-1);
      this.bookActivity = selectedBook; this.bookPayload = null;
      this.el('course-drawings').replaceChildren();
      course.drawings.forEach((drawing, i) => {
        const card = this.text('figure', '', 'review-original-card');
        const image = new Image(); image.src = drawing.thumbnail_url || drawing.url; image.alt = this.t('artwork', { n: i + 1 }); image.loading = 'lazy';
        const link = this.text('a', Studio.i18n.t('review.openOriginal'), 'btn quiet');
        link.href = drawing.url; link.target = '_blank'; link.rel = 'noopener';
        card.append(image, this.text('figcaption', image.alt), link);
        this.el('course-drawings').appendChild(card);
      });
      this.el('course-no-art').hidden = course.drawings.length > 0;
      this.el('course-no-results').hidden = !!selectedBook;
      // No book, no storybook tab: a sketch class never makes one, and an empty page read as broken.
      this.el('review-books').hidden = !selectedBook || course.entrance === 'sketch';
      this.el('review-book-title').hidden = !selectedBook;
      this.el('review-book-title').textContent = selectedBook?.summary.title || this.t('result.book');
      this.el('review-book-status').textContent = '';
      this.el('review-book-retry').hidden = true;
      this.message(''); this.el('portfolio').scrollTop = 0;
      if (!course.ended_at) {
        await this.create();
        if (!this.el('portfolio').hidden) {
          this.el('portfolio-list').hidden = false;
          if (this.el('portfolio-retry').hidden) this.message('failed', true);
        }
        return;
      }
      this.reviewSection(this.reviewSections?.[id] || (results.some(a => a.skill === 'teacher-review') ? 'teacher' : conversations.length ? 'stage1' : results.some(a => ['keyframe', 'video', 'relight', 'figure'].includes(a.summary.kind)) ? 'stage2' : selectedBook ? 'books' : 'originals'));
      this.showWorkspace(course, 'review');
      this.el('course-profile').hidden = false;
      this.el('portfolio').setAttribute('aria-labelledby', 'space-title');
    } catch (_) {
      if (version === this.version) { this.hideWorkspace(); this.detail = null; this.el('portfolio-list').hidden = false; this.message('failed', true); }
    }
  },
  disposeComparison() {
    if (this.readingDescription) {
      Studio.voice.stop(); Studio.voice.restore(); this.readingDescription = false;
    }
    this.comparisonVersion = (this.comparisonVersion || 0) + 1;
    if (this.reviewVideo) { this.reviewVideo.pause(); this.reviewVideo.removeAttribute('src'); this.reviewVideo.load(); this.reviewVideo = null; }
    if (this.reviewScene && Studio.relight?.active === this.reviewScene) Studio.relight.close();
    Studio.figureView?.close();
    this.reviewScene = null;
    this.el('review-output-content').replaceChildren();
    this.el('review-child-description').hidden = true;
    this.el('review-child-description-text').textContent = '';
  },
  reviewSection(section) {
    if (!this.detail?.drawings) return;
    if (section === 'books' && this.el('review-books').hidden) section = 'originals';
    this.disposeComparison();
    this.el('review-results').hidden = section !== 'stage2';
    this.bookVersion = (this.bookVersion || 0) + 1;
    if (section !== 'books') Studio.book?.closeInline?.();
    (this.reviewSections ||= {})[this.detail.id] = section;
    const hasMotion = this.detail.activities.some(a => ['keyframe', 'video', 'figure'].includes(a.summary.kind));
    const hasForm = this.detail.activities.some(a => a.summary.kind === 'relight');
    this.el('review-stage2').textContent = Studio.i18n.t(hasForm ? (hasMotion ? 'review.transformBoth' : 'mode.move') : this.detail.entrance === 'sketch' ? 'mode.move' : 'review.transform');
    ['teacher', 'stage1', 'stage2', 'books', 'originals'].forEach(key => this.el('review-' + key).setAttribute('aria-pressed', String(key === section)));
    const comparison = ['teacher', 'stage1', 'stage2'].includes(section);
    this.el('review-comparison').hidden = !comparison;
    this.el('review-book-panel').hidden = section !== 'books';
    this.el('review-original-panel').hidden = section !== 'originals';
    if (section === 'books') return this.loadBook();
    if (!comparison) return;
    // The bring-to-life tab lists drawings, one button each, and the work card offers what each became as result
    // slots (the one-layout rule); the teacher's and the chat's tabs list their one text per drawing.
    const drawn = section === 'stage2';
    const results = section === 'teacher'
      ? this.detail.drawings.map(d => this.detail.activities.filter(a => a.drawings.includes(d.id) && a.skill === 'teacher-review' && !a.summary.status).at(-1)).filter(Boolean)
      : section === 'stage1'
      ? this.detail.drawings.map(d => this.detail.activities.filter(a => a.drawings.includes(d.id) && a.summary.kind === 'text' && a.skill !== 'teacher-review' && !a.summary.status).at(-1)).filter(Boolean)
      : this.detail.drawings.filter(d => this.made(d.id).length);
    const caption = section === 'teacher' ? 'mode.teacher' : section === 'stage1' ? 'mode.feedback' : 'review.output';
    this.el('review-output-caption').textContent = Studio.i18n.t(caption);
    const picker = this.el('review-output'); picker.replaceChildren();
    results.forEach(item => {
      const drawing = drawn ? item : this.detail.drawings.find(d => item.drawings.includes(d.id));
      const became = drawn ? this.made(drawing.id).map(a => ' · ' + this.t('result.' + a.summary.kind)).join('') : '';
      const label = this.t('artwork', { n: this.detail.drawings.indexOf(drawing) + 1 }) + became;
      const option = this.text('button', ''); option.type = 'button';
      option.setAttribute('aria-label', label); option.title = label;
      const image = new Image(); image.src = drawing.thumbnail_url || drawing.url; image.alt = ''; image.loading = 'lazy';
      option.appendChild(image);
      option.value = item.id; option.onclick = () => drawn ? this.showMade(item.id) : this.loadComparison(item.id);
      picker.appendChild(option);
    });
    picker.hidden = !results.length; this.el('review-empty').hidden = !!results.length;
    this.el('review-pair').hidden = !results.length;
    const chosen = this.selected[this.detail.id];
    const selected = results.slice().reverse().find(item => drawn ? item.id === chosen : item.drawings.includes(chosen))
      || results.at(-1);
    if (!selected) return;
    picker.value = selected.id;
    return drawn ? this.showMade(selected.id) : this.loadComparison(selected.id);
  },
  // What a drawing became: its latest clip, figure, 3D study and old still pose, in that order.
  made(did) {
    return ['video', 'figure', 'relight', 'keyframe'].map(kind => this.detail.activities
      .filter(a => a.summary.kind === kind && !a.summary.status && a.drawings.includes(did)).at(-1)).filter(Boolean);
  },
  showMade(did, id) {
    const made = this.made(did), chosen = made.find(a => a.id === id) || made[0];
    const slots = this.el('review-results'); slots.replaceChildren(); slots.hidden = false;
    made.forEach(activity => {
      const slot = this.text('button', this.t('result.' + activity.summary.kind), activity === chosen ? 'on' : '');
      slot.type = 'button'; slot.value = activity.id; slot.setAttribute('aria-pressed', String(activity === chosen));
      slot.onclick = () => this.showMade(did, activity.id); slots.appendChild(slot);
    });
    return this.loadComparison(chosen.id);
  },
  async loadBook() {
    const course = this.detail, activity = this.bookActivity;
    if (!course || !activity) return;
    const version = this.version, epoch = ++this.bookVersion;
    const status = this.el('review-book-status'), retry = this.el('review-book-retry');
    status.textContent = this.t('opening'); retry.hidden = true;
    try {
      const result = this.bookPayload?.id === activity.id ? this.bookPayload.result
        : await this.api('/' + encodeURIComponent(course.id) + '/activities/' + encodeURIComponent(activity.id));
      if (version !== this.version || epoch !== this.bookVersion || this.detail !== course
          || this.reviewSections?.[course.id] !== 'books' || this.el('portfolio').hidden) return;
      if (!Array.isArray(result.outputs?.pages)) throw new Error('Missing storybook pages');
      this.bookPayload = { id: activity.id, result };
      const title = result.outputs.title || activity.summary.title || this.t('result.book');
      this.el('review-book-title').textContent = title;
      Studio.book.open(title, Object.assign({}, result.outputs, { artifact_id: activity.id, ending: result.ending }),
        course.drawings, { courseId: course.id, history: true, readOnly: true, inlineHost: this.el('review-book-reader') });
      status.textContent = '';
    } catch (_) {
      if (version === this.version && epoch === this.bookVersion) { status.textContent = this.t('failed'); retry.hidden = false; }
    }
  },
  async loadComparison(id) {
    this.disposeComparison();
    this.shownId = id;   // what Retry loads again: on the bring-to-life tab the row's value is a drawing, not a result
    const epoch = this.comparisonVersion, course = this.detail, version = this.version;
    const activity = course.activities.find(a => a.id === id);
    const drawing = activity && course.drawings.find(d => activity.drawings.includes(d.id));
    const status = this.el('review-output-status'), host = this.el('review-output-content');
    this.el('review-output-retry').hidden = true;
    if (!drawing) { status.textContent = this.t('noArtwork'); return; }
    const picker = this.el('review-output'); picker.value = id;
    Array.from(picker.children).forEach(button => {
      const on = button.value === id || button.value === drawing.id;
      button.className = on ? 'on' : '';
      button.setAttribute('aria-pressed', String(on));
    });
    this.selected[course.id] = drawing.id;
    this.el('course-original').src = drawing.url;
    this.el('course-original').alt = this.t('artwork', { n: course.drawings.indexOf(drawing) + 1 });
    const kind = activity.summary.kind;
    if (['video', 'figure', 'relight', 'keyframe'].includes(kind)) {
      // What this result shows: the movement a clip was made from, or that a figure is inspired by the drawing.
      // The child's own words stay on the chat tab; here they repeated it word for word (operator).
      // A result with nothing more to say than its slot's name shows no box.
      const shows = ['video', 'keyframe'].includes(kind) ? (activity.summary.scene_description || '').trim() : '';
      this.el('review-child-description-title').textContent = kind === 'figure' ? Studio.i18n.t('figure.title')
        : this.t('result.' + kind);
      this.el('review-child-description-text').textContent = shows;
      this.el('review-child-description-text').hidden = !shows;
      this.el('review-child-description').hidden = !shows && kind !== 'figure';
    }
    if (activity.skill === 'teacher-review') {
      // The card's own heading already names the teacher review.
      const block = this.text('section', '', 'review-reflection');
      block.appendChild(this.text('p', activity.summary.text || ''));
      host.appendChild(block); status.textContent = ''; return;
    }
    if (kind === 'text') {
      // The whole conversation in its order, both voices, as the class saw it (operator; this replaces
      // the earlier rule of the child's words alone, which read as a list with the questions taken out).
      // Each turn names its speaker for a screen reader, as the live chat panel's turns do.
      const messages = course.activities.filter(a => a.drawings.includes(drawing.id) && a.summary.kind === 'text'
        && a.skill !== 'teacher-review' && !a.summary.status);
      const texts = messages.filter(a => a.skill === 'confirmed-words')
        .map(a => a.summary.text || '').filter(text => text.trim());
      const block = this.text('section', '', 'review-reflection'), thread = this.text('div', '', 'review-thread');
      messages.forEach(a => {
        const child = a.skill === 'confirmed-words', said = (a.summary.text || '').trim();
        const question = child ? '' : (a.summary.question || '').trim();
        if (!said && !question) return;
        const turn = this.text('article', '', 'review-turn ' + (child ? 'child' : 'companion'));
        turn.appendChild(this.text('h3', Studio.i18n.t(child ? 'history.answer' : 'history.partner')));
        if (said) turn.appendChild(this.text('p', said));
        if (question) turn.appendChild(this.text('p', question, 'review-question'));
        thread.appendChild(turn);
      });
      if (!thread.children.length) thread.appendChild(this.text('p', Studio.i18n.t('review.noWords')));
      block.appendChild(thread);
      if (texts.length) {
        const read = this.text('button', Studio.i18n.t('review.childRead'), 'btn review-play'); read.type = 'button';
        const voiceHost = this.text('div', '', 'review-voice-host');
        read.onclick = () => {
          if (epoch !== this.comparisonVersion) return;
          this.readingDescription = true;
          Studio.voice.place(voiceHost); Studio.voice.unlock();
          const parts = texts.flatMap(text => {
            const points = Array.from(text), chunks = [];
            for (let i = 0; i < points.length; i += 180) chunks.push(points.slice(i, i + 180).join(''));
            return chunks;
          });
          Studio.voice.playAll(parts, { courseId: course.id, voice: 'soft-child' });
        };
        block.appendChild(read); block.appendChild(voiceHost);
      }
      host.appendChild(block);
      status.textContent = ''; return;
    }
    status.textContent = this.t('opening');
    try {
      const result = await this.api('/' + encodeURIComponent(course.id) + '/activities/' + encodeURIComponent(id));
      if (epoch !== this.comparisonVersion || version !== this.version || this.el('portfolio').hidden) return;
      const out = result.outputs;
      if (activity.summary.kind === 'keyframe') {
        if (!/^data:image\/png;base64,/.test(out.keyframe?.image || '')) throw new Error('Invalid image');
        const image = new Image(); image.src = out.keyframe.image; image.alt = Studio.i18n.t('review.output');
        image.onerror = () => { if (epoch === this.comparisonVersion) status.textContent = this.t('failed'); };
        host.appendChild(image);
      } else if (activity.summary.kind === 'video') {
        // Sent as a file of its own, so it plays as it arrives (studio/server/media_links.py).
        const saved = /^(data:video\/mp4;base64,|\/api\/courses\/[^/]+\/activities\/[^/]+\/media\/)/;
        if (!saved.test(out.video_url || '')) throw new Error('Invalid saved video');
        const video = document.createElement('video'); video.src = out.video_url; video.controls = true; video.playsInline = true; video.autoplay = true; video.loop = true; video.muted = true; video.preload = 'metadata';
        video.onerror = () => { if (epoch === this.comparisonVersion) status.textContent = this.t('failed'); };
        this.reviewVideo = video; host.appendChild(video);
      } else if (activity.summary.kind === 'relight' && out.scene) {
        Studio.relight.open(host, out.scene, drawing); this.reviewScene = Studio.relight.active;
      } else if (activity.summary.kind === 'figure' && out.figure) {
        Studio.figureView.open(host, out.figure, drawing);
      } else throw new Error('Missing output');
      status.textContent = '';
    } catch (_) {
      if (epoch === this.comparisonVersion && version === this.version) {
        status.textContent = this.t('failed'); this.el('review-output-retry').hidden = false;
      }
    }
  },
  async openResult(activity, button) {
    const course = this.detail, version = this.version, resultVersion = ++this.resultVersion;
    button.disabled = true; this.message('opening');
    try {
      const result = await this.api('/' + encodeURIComponent(course.id) + '/activities/' + encodeURIComponent(activity.id));
      if (version !== this.version || resultVersion !== this.resultVersion || this.el('portfolio').hidden) return;
      const out = result.outputs, drawing = course.drawings.find(d => activity.drawings.includes(d.id));
      if (out.pages) Studio.book.open(out.title || this.t('result.book'), Object.assign({}, out, { artifact_id: activity.id, ending: result.ending }), course.drawings, { courseId: course.id, history: true, readOnly: true });
      else Studio.media.open(this.t('result.' + activity.summary.kind), activity.summary.kind, out.scene || out.figure || out.keyframe || out.video_url, drawing);
      this.message('');
    } catch (_) { if (version === this.version && resultVersion === this.resultVersion) this.message('failed'); }
    finally { button.disabled = false; }
  },
  saveEnding(courseId, artifactId, text) {
    return this.api('/' + encodeURIComponent(courseId) + '/activities/' + encodeURIComponent(artifactId) + '/ending',
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
  },
  speak(courseId, text, voice, options) {
    return fetch('/api/courses/' + encodeURIComponent(courseId) + '/speech', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice }), signal: options.signal
    }).then(response => { if (!response.ok) throw new Error('Course speech unavailable'); return response; });
  }
};
