// The companion panel displays and reads dialogue only.
window.Studio = window.Studio || {};
Studio.courseHistory = {
  version: 0,
  // What was just sent for this drawing and is not in the saved course yet.
  // The column is drawn from the course the studio has saved, and a round takes
  // the model 25 to 113 seconds (measured), so without this the
  // teacher watched an empty column and wondered whether Send had worked. When
  // a round is cancelled or fails, this is also the only thing that keeps the
  // words on screen: they ARE saved, but nothing redraws the column.
  said: null,
  el(id) { return document.getElementById(id); },
  t(key, vars) { return Studio.i18n.t('history.' + key, vars); },
  init() {
    this.el('history-retry').onclick = () => this.refresh();
    Studio.bus.on('current', () => this.refresh());
    Studio.bus.on('ended', () => this.refresh());
    Studio.bus.on('said', payload => this.showSaid(payload.drawing, payload.text));
  },
  // Shown at once, asking the server for nothing.
  showSaid(drawingId, text) {
    if (!drawingId || !String(text || '').trim()) return;
    this.said = { drawing: drawingId, text: String(text) };
    if (Studio.state.current === drawingId) this.appendSaid();
  },
  appendSaid() {
    const list = this.el('history-messages');
    // The same words sent again after a round that did not answer take the place of the unanswered
    // copy and its note, instead of stacking a second one under it (operator: three
    // sends of one question left three copies, each saying the partner did not answer).
    list.querySelectorAll('.said-unanswered').forEach(words => {
      if (words.querySelector('p')?.textContent !== this.said.text) return;
      const note = words.nextElementSibling;
      if (note?.classList.contains('said-note')) note.remove();
      words.remove();
    });
    // Marked until the saved course replaces it; 26d-chat-panel.js says so when a round ends without that.
    const item = Studio.portfolio.text('article', '', 'course-message child-words said-pending');
    item.appendChild(Studio.portfolio.text('h3', this.t('answer')));
    item.appendChild(Studio.portfolio.text('p', this.said.text));
    list.appendChild(item);
  },
  // The partner's newest turn, added the moment its checked words arrive: whole, where the
  // typing was, like a message in a chat (operator). Nothing unchecked is ever
  // put here. It stays until the saved conversation is drawn again, so nothing jumps.
  draft: null,
  saved: 0,
  settleDraft(text, question) {
    if (this.el('course-history').hidden) return;
    const list = this.el('history-messages');
    list.querySelectorAll('.bridge').forEach(line => line.remove());
    list.querySelector('.history-empty')?.remove();
    this.draft = Studio.portfolio.text('article', '', 'course-message');
    this.fill(this.draft, this.t('partner'), text, question);
    list.appendChild(this.draft);
    this.draft.settled = true; this.keep = true;
    this.count(1);
    // The child's words this turn answers are answered: the column now stays up while it
    // reloads, and 26d-chat-panel.js would otherwise read them as a round that failed.
    list.querySelectorAll('.said-pending').forEach(words => words.classList.remove('said-pending'));
  },
  fill(item, label, text, question) {
    item.replaceChildren(Studio.portfolio.text('h3', label));
    if (text) item.appendChild(Studio.portfolio.text('p', text));
    if (question) item.appendChild(Studio.portfolio.text('p', question, 'course-question'));
  },
  count(extra) {
    this.el('history-count').textContent = this.t('counts', { messages: this.saved + (this.said ? 1 : 0) + extra });
  },
  // The quick line, as the partner typing (studio/conversation/bridge.py): it says the child was heard, and
  // the checked answer replaces it (settleDraft), or a stop takes it away (26d-chat-panel.js).
  showBridge(text) {
    if (this.el('course-history').hidden) return;
    const item = Studio.portfolio.text('article', '', 'course-message bridge typing');
    item.appendChild(Studio.portfolio.text('h3', this.t('partner')));
    item.appendChild(Studio.portfolio.text('p', text));
    this.el('history-messages').appendChild(item);
  },
  // The newest turn is no longer new; it stays until the saved conversation is drawn again.
  clearDraft() { this.draft = null; },
  current(version, sid, did) {
    return this.version === version && Studio.state.session === sid && Studio.state.current === did;
  },
  async playConversation() {
    Studio.voice.stop();
    Studio.voice.restore();
    Studio.voice.unlock();
    const token = Studio.voice.queueToken;
    const { session: sid, current: did, courseId: cid } = Studio.state;
    if (!sid || !cid || !did) return;
    this.el('history-status').textContent = this.t('loading');
    try {
      const course = await Studio.portfolio.api('/' + encodeURIComponent(cid));
      if (Studio.voice.queueToken !== token || Studio.state.session !== sid || Studio.state.current !== did) return;
      const texts = course.activities
        .filter(a => a.drawings.includes(did) && a.summary.kind === 'text' && a.skill !== 'teacher-review' && !a.summary.status)
        .map(a => ({ text: [a.summary.text || a.summary.message, a.summary.question].filter(Boolean).join(' '),
          voice: a.skill === 'confirmed-words' ? 'soft-child' : Studio.voice.selected() }))
        .filter(item => item.text.trim());
      this.el('history-status').textContent = texts.length ? '' : this.t('empty');
      Studio.voice.playAll(texts, { courseId: cid });
    } catch (_) {
      if (Studio.voice.queueToken === token) this.el('history-status').textContent = this.t('failed');
    }
  },
  async refresh() {
    const st = Studio.state, sid = st.session, did = st.current, cid = st.courseId;
    const version = ++this.version;
    // Words belong to the drawing they were said about, and to no other.
    if (this.said && this.said.drawing !== did) this.said = null;
    // A turn that just settled stays on screen until the saved copy replaces it in one
    // step, so it does not vanish and come back. Every other redraw starts empty: a
    // conversation the teacher just cleared must not linger while the course loads.
    if (this.drawn !== did || !this.keep) { this.el('history-messages').replaceChildren(); this.el('history-count').textContent = this.t('loading'); }
    this.drawn = did; this.keep = false;
    this.el('history-sample').hidden = true;
    this.el('history-retry').hidden = true;
    this.el('course-history').hidden = !sid || !cid || !did || st.transport?.name === 'mock';
    if (this.el('course-history').hidden) { this.el('history-messages').replaceChildren(); this.drawn = null; return; }
    this.el('history-status').textContent = '';
    try {
      const course = await Studio.portfolio.api('/' + encodeURIComponent(cid));
      if (!this.current(version, sid, did)) return;
      const messages = course.activities.filter(a => a.drawings.includes(did) && a.summary.kind === 'text' && a.skill !== 'teacher-review' && !a.summary.status);
      // Once the saved course holds them, the saved copy is the one on screen.
      if (this.said && messages.some(a => a.skill === 'confirmed-words' && a.summary.text === this.said.text)) this.said = null;
      this.saved = messages.length; this.count(0);
      this.el('history-sample').hidden = !messages.some(a => a.summary.beat === 'sample');
      const items = [];
      if (!messages.length && !this.said) items.push(Studio.portfolio.text('p', this.t('empty'), 'history-empty'));
      messages.forEach(a => {
        const item = Studio.portfolio.text('article', '', 'course-message' + (a.skill === 'confirmed-words' ? ' child-words' : ''));
        const label = a.skill === 'confirmed-words' ? this.t('answer') : this.t('partner');
        item.appendChild(Studio.portfolio.text('h3', label));
        if (a.summary.text || a.summary.message) item.appendChild(Studio.portfolio.text('p', a.summary.text || a.summary.message));
        if (a.summary.question) item.appendChild(Studio.portfolio.text('p', a.summary.question, 'course-question'));
        const play = Studio.portfolio.text('button', this.t('playTurn'), 'btn quiet turn-play');
        play.type = 'button';
        play.onclick = () => {
          if (!this.current(version, sid, did)) return;
          Studio.voice.restore(); Studio.voice.unlock();
          Studio.voice.playAll([{ text: [a.summary.text || a.summary.message, a.summary.question].filter(Boolean).join(' '),
            voice: a.skill === 'confirmed-words' ? 'soft-child' : Studio.voice.selected() }], { courseId: cid });
        };
        item.appendChild(play);
        items.push(item);
      });
      this.el('history-messages').replaceChildren(...items); this.draft = null;
      if (this.said) this.appendSaid();
      const scroll = this.el('buddy-dialogue'); if (st.mode === 'feedback') scroll.scrollTop = scroll.scrollHeight;
    } catch (_) {
      if (!this.current(version, sid, did)) return;
      this.el('history-messages').replaceChildren(); this.draft = null;
      // The course could not be read, which is no reason to take the child's words off the screen.
      if (this.said) this.appendSaid();
      this.el('history-count').textContent = this.t('failed'); this.el('history-retry').hidden = false;
    }
  }
};
