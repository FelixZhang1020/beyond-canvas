// The real harness over HTTP, following docs/specs/studio-page-contract.md.
window.Studio = window.Studio || {};
Studio.transports = Studio.transports || {};
(function () {
  // A refusal, with the studio's own name for it. The body carries a `code` the page can act on
  // (session_gone); a body that is not JSON must not replace the status the refusal already has.
  function refused(r) {
    const error = new Error('HTTP ' + r.status); error.httpStatus = r.status;
    return r.json().catch(function () { return {}; }).then(function (body) {
      error.code = body && body.code; throw error;
    });
  }
  // A call that belongs to the class the teacher is in. The studio keeps one editor per course, so
  // any of these can come back "that class is not open here any more" the moment the same course is
  // opened somewhere else — and then the page takes it back rather than leaving the teacher to
  // repeat an id the studio has forgotten. Deliberately not the calls that LEAVE a class
  // (forgetSession, completeCourse, editCourse): reopening what the teacher is closing is the one
  // thing worse than the refusal.
  function owned(work) {
    return work.catch(function (error) {
      if (error && error.code === 'session_gone' && Studio.rejoin) Studio.rejoin.start();
      throw error;
    });
  }
  function json(url, opts) {
    return fetch(url, opts).then(function (r) {
      if (!r.ok) return refused(r);
      return r.status === 204 ? null : r.json();
    });
  }
  function post(url, body) {
    return json(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  }
  Studio.transports.http = {
    name: 'http',
    deployments: function (sid) { return json('/api/deployments' + (sid ? '?session_id=' + encodeURIComponent(sid) : '')); },
    checkDeployment: function (name) { return post('/api/deployments/check', { deployment: name }); },
    selectDeployment: function (name) { return post('/api/deployments', { deployment: name }); },
    prompts: function () { return json('/api/prompts'); },
    health: function () {
      const ctrl = new AbortController(), timer = setTimeout(function () { ctrl.abort(); }, 5000);
      return json('/api/health', { signal: ctrl.signal }).finally(function () { clearTimeout(timer); });
    },
    createSession: function (settings) {
      const body = { language: settings.language, lesson_intent: settings.lessonIntent || '', entrance: settings.entrance };
      if (settings.title) body.title = settings.title;
      return post('/api/session', body);
    },
    forgetSession: function (sid) { return json('/api/session/' + encodeURIComponent(sid), { method: 'DELETE' }); },
    saveDrafts: function (sid, drafts) {
      return owned(json('/api/session/' + encodeURIComponent(sid) + '/drafts', {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ drafts: drafts })
      }));
    },
    deleteCourse: function (courseId) { return json('/api/courses/' + encodeURIComponent(courseId), { method: 'DELETE' }); },
    completeCourse: function (courseId) { return post('/api/courses/' + encodeURIComponent(courseId) + '/complete', {}); },
    editCourse: function (courseId, reopen) { return post('/api/courses/' + encodeURIComponent(courseId) + (reopen ? '/reopen' : '/edit'), {}); },
    updateSettings: function (sid, settings) {
      return owned(json('/api/session/' + encodeURIComponent(sid), { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: settings.language, lesson_intent: settings.lessonIntent || '' }) }));
    },
    speak: function (sid, text, voice, opts) {
      return owned(fetch('/api/session/' + encodeURIComponent(sid) + '/speech', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, voice: voice }), signal: opts.signal
      }).then(function (response) { return response.ok ? response : refused(response); }));
    },
    addDrawing: function (sid, blob) {
      const form = new FormData(); form.append('image', blob, 'drawing.jpg');
      return owned(json('/api/session/' + encodeURIComponent(sid) + '/drawings', { method: 'POST', body: form }));
    },
    // `which` is 'conversation' (clear it for good) or 'last-round' (take back the last answer).
    forgetChat: function (sid, did, which) {
      return owned(json('/api/session/' + encodeURIComponent(sid) + '/drawings/' + encodeURIComponent(did) + '/' + which, { method: 'DELETE' }));
    },
    removeDrawing: function (sid, did) {
      return owned(json('/api/session/' + encodeURIComponent(sid) + '/drawings/' + encodeURIComponent(did), { method: 'DELETE' }));
    },
    hear: function (sid, blob) {
      function send(audio) {
        const kind = /webm/.test(audio.type) ? 'webm' : /ogg/.test(audio.type) ? 'ogg' : 'wav';
        const form = new FormData(); form.append('audio', audio, 'said.' + kind);
        return fetch('/api/session/' + encodeURIComponent(sid) + '/heard', { method: 'POST', body: form })
          .then(function (r) {
            // 503 means the recording could not be turned into words, which the
            // contract calls not fatal: typing always works. Reporting it as "Splat
            // needs a rest" told the teacher the studio was broken, and reporting it
            // as "no microphone" (as it once was) blamed a microphone that worked.
            if (r.status === 503) return { text: '', listening: false };
            if (!r.ok) return refused(r);
            return r.json();
          });
      }
      // Said while the words are on their way, so the teacher sees it working.
      if (Studio.bus) Studio.bus.emit('hearing', { on: true });
      return owned(send(blob).catch(function (error) {
        // The studio could not unpack the browser's own recording (studio/voice/audio_in.py): its
        // failing, not the child's. Unpacked here and sent once more, as every recording used to
        // go, rather than asking a child to say it again into the same wall.
        if (error && error.code === 'unreadable_audio' && Studio.listen && !/wav/.test(blob.type)) {
          return Studio.listen.toWav(blob).then(send);
        }
        throw error;
      }).finally(function () { if (Studio.bus) Studio.bus.emit('hearing', { on: false }); }));
    },
    request: function (sid, skill, drawingIds, options, onEvent) {
      let source = null, live = true, requestId = null, resent = false;
      // The words are the teacher's to see the moment she sends them, not when the
      // model has finished answering a minute later. The studio saves them as it
      // accepts the request, so this only says out loud what was just sent.
      if (options && options.transcript && Studio.bus) {
        Studio.bus.emit('said', { drawing: drawingIds[0], text: options.transcript });
      }
      function cancel() {
        if (requestId) json('/api/session/' + encodeURIComponent(sid) + '/requests/' + encodeURIComponent(requestId), { method: 'DELETE' }).catch(function () {});
      }
      // A child's words the teacher already sent go once more to the class taken back, when the studio
      // had forgotten it: after every restart the first Send said it did not go (operator).
      // Only chat words, which the Spark answers for nothing; a photograph or a creation task is still
      // hers to press again (29f-rejoin.js).
      const resendable = skill === 'art-feedback' && !!(options && options.transcript);
      function submit() {
        post('/api/session/' + encodeURIComponent(sid) + '/requests', { skill: skill, drawing_ids: drawingIds, options: options || {} })
          .then(function (res) {
            requestId = res.request_id;
            if (!live) { cancel(); return; }
            onEvent({ stage: skill, status: 'submitted', request_id: requestId });
            source = new EventSource('/api/requests/' + encodeURIComponent(res.request_id) + '/events');
            source.addEventListener('stage', function (e) { if (live) onEvent(JSON.parse(e.data)); });
            source.addEventListener('done', function (e) { if (!live) return; live = false; source.close(); onEvent(Object.assign({ status: 'done' }, JSON.parse(e.data))); });
            source.onerror = function () {
              if (!live) return;
              live = false; source.close();
              onEvent({ stage: skill, status: 'stopped', message: Studio.i18n.t('task.connection_lost'), reason_code: 'connection_lost' });
            };
          })
          .catch(function (error) {
            if (!live) return;
            const gone = error && error.code === 'session_gone';
            if (gone && resendable && !resent && !requestId && Studio.rejoin) {
              resent = true;
              return Studio.rejoin.start({ quiet: true }).then(function (took) {
                if (took && live && Studio.state && Studio.state.session) { sid = Studio.state.session; submit(); }
                else fail(error);
              });
            }
            if (gone && Studio.rejoin) Studio.rejoin.start();
            fail(error);
          });
      }
      function fail(error) {
        if (!live) return;
        live = false;
        const reason = requestId ? 'connection_lost' : error.code === 'session_gone' ? 'session_gone'
          : error.httpStatus ? 'submission_failed' : 'server_unreachable';
        // No request id: the studio almost certainly never took the words (a reply lost on its
        // way back is the rare exception, and a resend is not saved twice). Said before the round
        // ends, so the note under them does not claim they were saved (once, a Send while
        // the studio was down was told the child's words had been saved).
        if (!requestId && options && options.transcript && Studio.bus) Studio.bus.emit('unsent', { drawing: drawingIds[0] });
        onEvent({ stage: skill, status: 'stopped', message: Studio.i18n.t('task.' + reason), reason_code: reason });
      }
      submit();
      return { abort: function () { live = false; if (source) source.close(); cancel(); } };
    },
    ledger: function (sid) { return json('/api/session/' + encodeURIComponent(sid) + '/ledger'); }
  };
})();
