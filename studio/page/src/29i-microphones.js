// The three ways the child's words come in by voice: the answer in the chat, the ending in the book, and a recording
// made before the class. Moved out of 30-main.js when that file was 780 lines against the 500 limit and
// the size guard refused any change to it. What was heard always lands in a field; the chat's answer is then sent at
// once (operator: a press of Send after every recording was one too many), while the book's ending and a file wait for
// the teacher to confirm them.
// `generation` counts each letting-go of the microphone, so an answer that arrives after it is dropped.
(function () {
  const $ = function (id) { return document.getElementById(id); }, S = Studio, st = S.state;
  const t = function (k, v) { return S.i18n.t(k, v); }, main = function () { return S.main; };   // 30-main.js
  let generation = 0;
  S.microphones = {
    release: function () {
      generation++;
      S.listen.release();
      ['btn-listen', 'ending-listen'].forEach(function (id) {
        const button = $(id), label = button.querySelector('span');
        button.classList.remove('on'); button.disabled = false;
        label.textContent = t('listen'); label.dataset.t = 'listen';
      });
      $('btn-said-file').disabled = false;
    },
    // The child says it out loud and it goes into the conversation as the child's answer, through the same send as
    // a typed one; one misheard is taken back with the chat's Take back, and said again. Before the companion has
    // opened the drawing it waits in the field behind the big button, as typed words do: the studio refuses an
    // answer with no opening, and the child saw the refusal (review). Recording is refused while the companion
    // answers, and an answer that comes back after another round began is dropped below.
    toggle: function () {
      if (st.busy || main().changing()) return;
      const button = $('btn-listen'), label = button.firstChild, toast = main().toast;
      if (!S.listen.on) S.microphones.release();
      const epoch = generation, sessionId = st.session, drawingId = st.current;
      if (S.listen.on) {
        button.classList.remove('on'); label.textContent = t('listen'); label.dataset.t = 'listen';
        button.disabled = true;
        // The reply is spoken after no tap of its own now, so this tap readies the voice (iPad Safari, review).
        if (S.voice.unlock) S.voice.unlock();
        return S.listen.stop().then(function (blob) {
          if (epoch !== generation || st.session !== sessionId || st.current !== drawingId) return;
          if (!blob) { button.disabled = false; toast(t('listen.nothing')); return; }
          return st.transport.hear(sessionId, blob).then(function (res) {
            if (epoch !== generation || st.session !== sessionId || st.current !== drawingId) return;
            button.disabled = false;
            // The studio holds this recording until the answer is sent; the first sent about a drawing reads its
            // storybook page in the child's voice (studio/voice/child_voice.py). Only the chat's microphone gives one.
            st.heardSample = res && res.sample && { drawing: drawingId, id: res.sample };
            if (res && res.text) {
              $('heard-text').value = res.text;
              if (st.feedback[drawingId]) $('heard').dispatchEvent(new Event('submit', { cancelable: true }));
              else $('heard-text').focus();
            } else { toast(t('listen.nothing')); $('heard-text').focus(); }
          });
        }).catch(function () { if (epoch === generation && st.session === sessionId && st.current === drawingId) { button.disabled = false; toast(t('msg.unavailable')); } });
      }
      if (S.voice.stop) S.voice.stop();
      button.disabled = true;
      return S.listen.start().then(function (started) {
        if (started === false) return;
        button.disabled = false;
        if (epoch !== generation || st.session !== sessionId || st.current !== drawingId) { return; }
        button.classList.add('on'); label.textContent = t('listen.stop'); label.dataset.t = 'listen.stop';
      }).catch(function () { if (epoch === generation && st.session === sessionId && st.current === drawingId) { button.disabled = false; toast(t('listen.none')); } });
    },
    // The same listening path, pointed at the book's last page. What was heard lands in
    // the field rather than in the book: a misheard sentence would become the child's last word.
    ending: function () {
      const button = $('ending-listen'), label = button.firstChild, toast = main().toast;
      if (!S.listen.on) S.microphones.release();
      const epoch = generation, sessionId = st.session, drawingId = st.current;
      if (S.listen.on) {
        label.textContent = t('listen'); label.dataset.t = 'listen';
        button.classList.remove('on'); button.disabled = true;
        return S.listen.stop().then(function (blob) {
          if (epoch !== generation || st.session !== sessionId || st.current !== drawingId) return;
          button.disabled = false;
          if (!blob) { toast(t('listen.nothing')); return; }
          return st.transport.hear(sessionId, blob).then(function (res) {
            if (epoch !== generation || st.session !== sessionId || st.current !== drawingId) return;
            if (res && res.text) { $('ending-text').value = res.text; $('ending-text').focus(); }
            else toast(t('listen.nothing'));
          });
        }).catch(function () { if (epoch === generation && st.session === sessionId && st.current === drawingId) { button.disabled = false; toast(t('msg.unavailable')); } });
      }
      if (S.voice.stop) S.voice.stop();
      button.disabled = true;
      return S.listen.start().then(function (started) {
        if (started === false) return;
        button.disabled = false;
        if (epoch !== generation || st.session !== sessionId || st.current !== drawingId) { return; }
        button.classList.add('on'); label.textContent = t('listen.stop'); label.dataset.t = 'listen.stop';
      }).catch(function () { if (epoch === generation && st.session === sessionId && st.current === drawingId) { button.disabled = false; toast(t('listen.none')); } });
    },
    // A recording the teacher made before the class opened. It lands in the field and waits there, unlike a live
    // answer: what was heard in a file made earlier is the teacher's to confirm.
    fromFile: function (file) {
      S.microphones.release();
      const button = $('btn-said-file'), toast = main().toast;
      const epoch = generation, sessionId = st.session, drawingId = st.current;
      if (S.voice.stop) S.voice.stop();
      button.disabled = true;
      return S.listen.fromFile(file)
        .then(function (wav) { if (epoch === generation && st.session === sessionId && st.current === drawingId) return st.transport.hear(sessionId, wav); })
        .then(function (res) {
          if (epoch !== generation || st.session !== sessionId || st.current !== drawingId) return;
          // A file is never the child's voice for the book.
          button.disabled = false; st.heardSample = null;
          if (res && res.text) { $('heard-text').value = res.text; $('heard-text').focus(); }
          else toast(t('listen.nothing'));
        })
        .catch(function () { if (epoch === generation && st.session === sessionId && st.current === drawingId) { button.disabled = false; toast(t('listen.fileBad')); } });
    }
  };
})();
