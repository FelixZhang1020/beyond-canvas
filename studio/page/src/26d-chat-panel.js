// The conversation panel's small behaviours, kept apart from 30-main.js, which is
// over the 500-line limit and cannot be written to. Nothing here sends anything:
// it grows the field, times a recording, says so when a round ends without the
// partner answering what the child said, and offers Stop in the thread while the
// partner thinks.
window.Studio = window.Studio || {};
Studio.chatPanel = {
  el(id) { return document.getElementById(id); },
  init() {
    const field = this.el('heard-text');
    // A transcript is written into the field by code, which fires no input event.
    ['input', 'focus'].forEach(name => field.addEventListener(name, () => this.fit()));
    new MutationObserver(() => this.timeRecording()).observe(this.el('btn-listen'), { attributes: true, attributeFilter: ['class'] });
    new MutationObserver(() => { this.showStop(); this.checkRound(); }).observe(this.el('splat'), { attributes: true, attributeFilter: ['class'] });
    // Switching tabs mid-task changes where Stop belongs too (review): without this, Stop
    // stayed in a conversation the teacher had left, or the big one came back under Record.
    new MutationObserver(() => this.showStop()).observe(this.el('app'), { attributes: true, attributeFilter: ['data-mode'] });
    // The same stop as the big button, which stays out of the conversation while it thinks.
    this.el('chat-stop').addEventListener('click', () => { if (Studio.state.busy) this.el('btn-primary').click(); });
    // A turn arriving adds itself above Stop; the thread follows it down unless the teacher
    // has scrolled up to read.
    new MutationObserver(() => { if (!this.el('chat-stop').hidden) this.follow(); })
      .observe(this.el('history-messages'), { childList: true });
    Studio.bus.on('unsent', () => { this.unsent = true; });
    Studio.bus.on('hearing', ({ on }) => this.showHearing(on));
  },
  // While a recording is on its way to words, the empty box says so instead of asking what the
  // child said (the wait used to show only a greyed-out Record, and read as nothing happening).
  // Counted, because a recording and an uploaded file can be on their way at once; and the story's
  // last page has its own box, which says it too.
  showHearing(on) {
    this.hearings = Math.max(0, (this.hearings || 0) + (on ? 1 : -1));
    ['heard-text', 'ending-text'].forEach(id => {
      const field = this.el(id);
      if (!field || !field.dataset) return;
      if (this.hearings && field.dataset.idle === undefined) {
        field.dataset.idle = field.placeholder; field.placeholder = Studio.i18n.t('chat.hearing');
      } else if (!this.hearings && field.dataset.idle !== undefined) {
        field.placeholder = field.dataset.idle; delete field.dataset.idle;
      }
    });
  },
  showStop() {
    const thinking = this.el('splat').classList.contains('thinking');
    const hidden = !(thinking && Studio.state.mode === 'feedback' && !this.el('course-history').hidden);
    const shown = this.el('chat-stop').hidden && !hidden;
    this.el('chat-stop').hidden = hidden;
    // On a narrow screen the thread is a short scrolling box, and Stop sits under its last turn:
    // on the Spark it was found scrolled out of sight the moment it appeared.
    if (shown) this.follow(true);
  },
  follow(always) {
    const box = this.el('buddy-dialogue');
    if (always || box.scrollHeight - box.scrollTop - box.clientHeight < 120) box.scrollTop = box.scrollHeight;
  },
  fit() {
    const field = this.el('heard-text');
    field.style.height = 'auto';
    field.style.height = Math.min(field.scrollHeight + 2, 120) + 'px';
  },
  timeRecording() {
    const on = this.el('btn-listen').classList.contains('on'), clock = this.el('rec-time');
    clearInterval(this.ticking);
    if (!on) return;
    const since = Date.now();
    const tick = () => {
      const s = Math.floor((Date.now() - since) / 1000);
      clock.textContent = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
    };
    tick(); this.ticking = setInterval(tick, 500);
  },
  // A round that answered redraws the column at once, which removes the pending
  // words; one that stopped leaves them. Checked after the current task, so the
  // redraw has already happened. Words the studio accepted are saved either way, so the
  // note says the partner did not answer, not that they were lost; words it never
  // accepted (the transport says 'unsent') were not, and the note says only that they
  // did not go (found with a Send while the studio was down). They also go back in the
  // field, so Send asks again without retyping them; the studio does not save the
  // same unanswered words twice. The quick echo said while the studio looked is never
  // saved (studio/conversation/bridge.py) and only a redraw removes it, so a stopped round left it
  // standing under "did not answer" as if the partner had: it goes too.
  checkRound() {
    if (this.el('splat').classList.contains('thinking')) { this.unsent = false; return; }
    const unsent = this.unsent; this.unsent = false;
    setTimeout(() => {
      const words = this.el('history-messages').querySelector('.said-pending:not(.said-unanswered)');
      if (!words || this.el('splat').classList.contains('thinking')) return;
      this.el('history-messages').querySelectorAll('.course-message.bridge').forEach(line => line.remove());
      words.classList.add('said-unanswered');
      const note = document.createElement('p');
      note.className = 'said-note';
      note.textContent = unsent ? Studio.i18n.t('chat.notReached') : Studio.i18n.t('chat.notSent');
      words.after(note);
      const field = this.el('heard-text'), said = words.querySelector('p');
      if (said && !field.value.trim()) { field.value = said.textContent; this.fit(); }
      this.el('buddy-dialogue').scrollTop = this.el('buddy-dialogue').scrollHeight;
    }, 0);
  }
};
// Scripts run at the end of the page, so the panel is already there.
if (document.getElementById('heard-text')) Studio.chatPanel.init();
