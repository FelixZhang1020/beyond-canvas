import { Recorder, toWav } from './audio.mjs';
import { QuestionVoice } from './question-voice.mjs';
import { StreamingQuestionVoice } from './stream-voice.mjs';
const $ = id => document.getElementById(id);
const example = '午后的阳光落在窗边，桌上的茶还冒着一点热气。我放下手里的事情，听见外面有人慢慢走过。\n\n有时候，让一天变得特别的，并不是一个很大的计划，而是这些很小的瞬间。一阵风，一句话，或者一次没有赶时间的散步。\n\n如果明天还能留出一点空闲，我想走一条不常走的路，看看熟悉的城市里，还有什么没有被我发现。';
const state = { session: '', epoch: 0, busy: false, recording: false, generating: false, selected: '', samples: [], draft: null, questionId: 0, speechLoading: false, voices: {}, voiceId: '', cloneLocal: false, cloneReady: false, urls: new Set() };
const voicePreference = 'voice-lab-dialogue-voice';
let recorder = new Recorder();
let questionVoice = new QuestionVoice($('question-audio'),
  (questionId, voiceId) => api('speech', { method: 'POST', body: { question_id: questionId, voice_id: voiceId }, blob: true }),
  updateVoice);
function updateVoice({ loading, streaming, text, failed, firstPlaySeconds, stopped }) {
    if (loading !== undefined) state.speechLoading = loading;
    if (streaming !== undefined) $('stop-voice').hidden = !streaming;
    if (firstPlaySeconds === null) delete $('voice-status').dataset.firstPlaySeconds;
    else if (firstPlaySeconds !== undefined) $('voice-status').dataset.firstPlaySeconds = firstPlaySeconds.toFixed(3);
    if (text !== undefined) $('voice-status').textContent = text;
    else if ((stopped || streaming === false) && /正在准备|正在朗读/.test($('voice-status').textContent)) $('voice-status').textContent = '已暂停，可随时重听问题。';
    if (failed !== undefined) $('replay').textContent = failed ? '重试语音' : '重听问题';
    controls();
  }
let timer, started, poll;

function notice(text = '') { $('notice').textContent = text; $('notice').hidden = !text; }
function pauseAll() { questionVoice.stop(); document.querySelectorAll('audio').forEach(a => a.pause()); }
function speak(questionId) { pauseAll(); void questionVoice.play(questionId, state.voiceId, state.voices[state.voiceId]); }
function showVoice() {
  $('voice-name').textContent = state.voices[state.voiceId];
  $('question-audio').setAttribute('aria-label', state.voices[state.voiceId] + '的问题');
}
function objectUrl(blob) { const url = URL.createObjectURL(blob); state.urls.add(url); return url; }
function revoke(url) { if (url) { URL.revokeObjectURL(url); state.urls.delete(url); } }
function controls() {
  $('record').disabled = state.busy || !!state.draft || !state.session || state.generating;
  $('confirm').disabled = state.busy;
  $('discard').disabled = state.busy;
  $('audio-file').disabled = state.busy || state.recording || !!state.draft || state.generating;
  $('replay').disabled = !state.session || state.recording || state.busy || state.speechLoading || state.generating;
  $('generate').disabled = !state.cloneReady || !state.selected || state.generating || state.busy || state.recording || !validArticle();
  $('article').disabled = state.generating;
  $('example').disabled = state.generating;
  $('reset').disabled = !state.session;
  $('settings').disabled = !state.voiceId || state.recording || state.busy || state.generating;
}
function busy(value, text) { state.busy = value; if (text) $('record-status').textContent = text; controls(); }
function message(text, role, label) {
  const wrap = document.createElement('div'); wrap.className = 'message ' + role;
  const who = document.createElement('small'); who.textContent = label || (role === 'user' ? '你' : '对话伙伴');
  const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = text;
  wrap.append(who, bubble); $('messages').append(wrap); $('messages').scrollTop = $('messages').scrollHeight;
}
async function api(path, { method = 'GET', body, blob = false, raw = false, signal } = {}) {
  const headers = { 'X-Lab-Session': state.session };
  if (body && !(body instanceof Blob)) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(body); }
  if (body instanceof Blob) headers['Content-Type'] = body.type;
  let response;
  try { response = await fetch('/api/' + path, { method, headers, body, signal, cache: 'no-store' }); }
  catch (_) { throw new Error('连接中断，请确认本机工具仍在运行。'); }
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.error || '这一步没有完成，请重试。');
  }
  return raw ? response : blob ? response.blob() : response.json();
}
function validArticle() { const n = Array.from($('article').value.trim()).length; return n > 0 && n <= 500; }
function updateArticle() {
  const count = Array.from($('article').value.trim()).length;
  $('char-count').textContent = `${count} / 500 字`;
  $('cost').textContent = '¥' + (count * 5.8 / 10000).toFixed(3);
  controls();
}

async function start() {
  const epoch = ++state.epoch;
  $('start').disabled = true; notice();
  try {
    const result = await api('session', { method: 'POST' });
    if (epoch !== state.epoch) return;
    state.session = result.session_id; state.questionId = result.question_id;
    $('messages').replaceChildren(); message(result.question, 'assistant');
    $('recorder').hidden = false; $('question-player').hidden = false; controls(); speak(result.question_id);
  } catch (error) { notice(error.message); $('start').disabled = false; }
}

async function acceptRecording(wav, epoch) {
  // Conversion can finish after End and a new session. Check before uploading.
  if (epoch !== state.epoch || !state.session) return;
  if (!wav) throw new Error('没有录到声音，请重试。');
  busy(true, '正在本机转写，并挑选一段清晰的声音…');
  const sample = await api('record', { method: 'POST', body: wav });
  if (epoch !== state.epoch) return;
  const blob = await api('sample/' + sample.id, { blob: true });
  if (epoch !== state.epoch) return;
  sample.url = objectUrl(blob); state.draft = sample;
  $('transcript').value = sample.transcript; $('reference-text').value = sample.reference_text;
  $('draft-audio').src = sample.url;
  $('draft-quality').textContent = `参考片段 ${sample.quality.seconds} 秒 · 转写 ${sample.asr_s} 秒。${sample.quality.reason}`;
  $('draft').hidden = false;
  $('record-status').textContent = '录音已停，请确认上面的文字，也听听参考片段。';
}

async function toggleRecord() {
  const epoch = state.epoch;
  notice();
  if (state.recording) {
    state.recording = false; clearInterval(timer);
    $('record').classList.remove('on'); $('record-label').textContent = '按一下，开始说'; $('level').style.width = '0';
    busy(true, '正在处理这段录音…');
    try { await acceptRecording(await recorder.stop(), epoch); }
    catch (error) { if (epoch === state.epoch) notice(error.message); }
    finally { if (epoch === state.epoch) busy(false); }
    return;
  }
  pauseAll(); busy(true, '正在连接麦克风…');
  // A pending permission request or conversion belongs to its own recorder.
  const activeRecorder = new Recorder(); recorder = activeRecorder;
  try {
    await activeRecorder.start(level => { if (epoch === state.epoch) $('level').style.width = (level * 100) + '%'; });
    if (epoch !== state.epoch) { activeRecorder.release(); return; }
    state.recording = true; started = Date.now();
    $('record').classList.add('on'); $('record-label').textContent = '说完了，写下来';
    $('record-status').textContent = '我在听。自然地说两三句话，最长录制 30 秒。';
    $('timer').textContent = '00:00';
    timer = setInterval(() => {
      const seconds = Math.floor((Date.now() - started) / 1000);
      $('timer').textContent = '00:' + String(seconds).padStart(2, '0');
      if (seconds >= 30) toggleRecord();
    }, 200);
  } catch (error) {
    if (epoch === state.epoch) notice(error.name === 'NotAllowedError' ? '麦克风权限未开启。请允许这个页面使用麦克风，或导入自己的录音。' : error.message);
  } finally { if (epoch === state.epoch) busy(false); }
}

function drawSamples() {
  $('samples').replaceChildren();
  $('sample-empty').hidden = state.samples.length > 0;
  $('sample-count').textContent = state.samples.length ? `${state.samples.length} 段已确认` : '还没有样本';
  state.samples.forEach((sample, index) => {
    const card = document.createElement('div'); card.className = 'sample' + (state.selected === sample.id ? ' selected' : '');
    const label = document.createElement('label');
    const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'sample'; radio.value = sample.id;
    radio.checked = state.selected === sample.id; radio.disabled = !sample.quality.usable || state.generating;
    radio.addEventListener('change', () => { state.selected = sample.id; drawSamples(); controls(); });
    const title = document.createElement('span'); title.textContent = `第 ${index + 1} 段 · ${sample.quality.seconds} 秒${sample.quality.usable ? '' : ' · 建议重录'}`;
    label.append(radio, title);
    const text = document.createElement('p'); text.className = 'summary'; text.textContent = sample.reference_text;
    const audio = document.createElement('audio'); audio.controls = true; audio.src = sample.url; audio.preload = 'metadata';
    audio.setAttribute('aria-label', `第 ${index + 1} 段参考原声`);
    audio.addEventListener('play', () => exclusivePlayback(audio));
    card.append(label, text, audio); $('samples').append(card);
  });
  if (state.selected) {
    $('step-talk').className = 'done'; $('step-voice').className = 'current';
    if (!state.generating) $('generate-status').textContent = '参考声音已就绪。可以继续聊，也可以现在生成朗读。';
  }
}

async function confirm() {
  const sample = state.draft, epoch = state.epoch;
  if (!sample) return;
  const transcript = $('transcript').value.trim(), reference = $('reference-text').value.trim();
  if (!transcript || !reference) { notice('请确认回答和参考片段对应的文字。'); return; }
  busy(true, '对话伙伴正在接着你的回答想下一问…'); notice();
  try {
    const result = await api('turn', { method: 'POST', body: { sample_id: sample.id, text: transcript, reference_text: reference } });
    if (epoch !== state.epoch) return;
    sample.transcript = transcript; sample.reference_text = reference;
    state.samples.push(sample); state.draft = null;
    if (sample.quality.usable && !state.selected) state.selected = sample.id;
    $('draft').hidden = true; $('draft-audio').removeAttribute('src');
    message(transcript, 'user'); message(result.reply, 'assistant', result.mode === 'fallback' ? '备用问题 · 本机对话暂不可用' : `对话伙伴 · ${result.dialog_s} 秒`);
    state.questionId = result.question_id; drawSamples(); speak(result.question_id);
    $('record-status').textContent = '可以继续回答；有一段清晰样本后，也可以直接去听朗读。';
  } catch (error) { if (epoch === state.epoch) notice(error.message); }
  finally { if (epoch === state.epoch) busy(false); }
}

async function discard() {
  if (!state.draft) return;
  try { await api('discard', { method: 'POST', body: { sample_id: state.draft.id } }); }
  catch (error) { notice(error.message); return; }
  revoke(state.draft.url); state.draft = null; $('draft-audio').removeAttribute('src'); $('draft').hidden = true;
  $('record-status').textContent = '准备好了就再说一段。'; controls();
}

async function generate() {
  if (!validArticle() || !state.selected) return;
  const epoch = state.epoch;
  state.generating = true; pauseAll(); notice(); controls(); drawSamples();
  $('result').hidden = true; revoke($('output-audio').src); $('output-audio').removeAttribute('src'); $('download').removeAttribute('href');
  $('generate-status').textContent = state.cloneLocal ? '正在本机用所选参考声音生成朗读…' : '正在上传所选参考片段，开始生成朗读…';
  $('cleanup-warning').hidden = true;
  try {
    await api('generate', { method: 'POST', body: { sample_id: state.selected, article: $('article').value.trim() } });
    if (epoch !== state.epoch) return;
    await watchJob(epoch);
  } catch (error) {
    if (epoch === state.epoch) { notice(error.message); state.generating = false; controls(); drawSamples(); $('generate-status').textContent = '本次生成未完成，没有自动重试。'; }
  }
}

async function watchJob(epoch) {
  if (epoch !== state.epoch) return;
  try {
    const job = await api('job');
    if (epoch !== state.epoch) return;
    $('generate-status').textContent = `已生成 ${job.completed || 0} / ${job.total || 0} 段 · 已用 ${job.elapsed_s || 0} 秒`;
    if (job.status === 'running') { poll = setTimeout(() => watchJob(epoch), 1500); return; }
    $('cleanup-warning').hidden = !job.cleanup_pending;
    $('cleanup-warning').textContent = '云端参考文件删除尚未确认，工具会继续重试。请保持工具运行；强制退出可能需要在阶跃星辰控制台手动清理。';
    if (job.status === 'error') throw new Error(job.error);
    const blob = await api('audio', { blob: true });
    if (epoch !== state.epoch) return;
    const url = objectUrl(blob); $('output-audio').src = url; $('download').href = url; $('result').hidden = false;
    state.generating = false; controls(); drawSamples();
    $('step-voice').className = 'done'; $('step-read').className = 'current';
    $('generate-status').textContent = `朗读已生成 · ${job.elapsed_s} 秒${state.cloneLocal ? ' · 本机合成' : job.cleanup_pending ? '' : ' · 云端参考文件已删除'}`;
    $('output-audio').play().catch(() => { $('generate-status').textContent += '。点击播放器开始听。'; });
  } catch (error) {
    if (epoch === state.epoch) {
      // A polling failure does not prove that a paid job stopped. Keep Generate
      // disabled and retry the read-only status request, never the generation.
      if (error.message.startsWith('连接中断')) {
        $('generate-status').textContent = '暂时读不到进度，正在重新连接；不会重复提交生成。';
        poll = setTimeout(() => watchJob(epoch), 4000);
      } else {
        state.generating = false; controls(); drawSamples(); notice(error.message);
        $('generate-status').textContent = '生成没有完成。请查看提示后再试。';
      }
    }
  }
}

async function end() {
  const token = state.session;
  ++state.epoch; clearInterval(timer); clearTimeout(poll); recorder.release(); pauseAll();
  questionVoice.clear(); $('question-player').hidden = true; $('voice-status').textContent = '';
  state.session = ''; state.recording = false; state.busy = false; state.generating = false;
  state.draft = null; state.samples = []; state.selected = '';
  document.querySelectorAll('audio').forEach(a => { a.removeAttribute('src'); a.load(); });
  state.urls.forEach(url => URL.revokeObjectURL(url)); state.urls.clear();
  $('messages').replaceChildren(); message('这次测试结束了。重新开始时，会重新采集你的声音。', 'assistant');
  const button = document.createElement('button'); button.id = 'start'; button.className = 'primary'; button.textContent = '重新开始聊天'; button.addEventListener('click', start); $('messages').append(button);
  $('recorder').hidden = true; $('draft').hidden = true; $('result').hidden = true; $('download').removeAttribute('href');
  $('transcript').value = ''; $('reference-text').value = ''; $('article').value = example; $('audio-file').value = '';
  $('record').classList.remove('on'); $('record-label').textContent = '按一下，开始说'; $('timer').textContent = '00:00'; $('level').style.width = '0';
  $('step-talk').className = 'current'; $('step-voice').className = ''; $('step-read').className = '';
  drawSamples(); updateArticle(); $('generate-status').textContent = '重新开始聊天后，可以再次试听。';
  try { await api('end', { method: 'POST', body: { session_id: token } }); notice(state.cloneLocal ? '本机录音与对话已清除。进行中的合成会停止并清除参考缓存。' : '本机录音与对话已清除。进行中的云端请求会在结束后请求删除参考文件。'); }
  catch (_) { notice('页面内容已清除，但暂时连不上工具。后台会在闲置 30 分钟后清除本机录音。'); }
}

$('start').addEventListener('click', start); $('record').addEventListener('click', toggleRecord);
$('confirm').addEventListener('click', confirm); $('discard').addEventListener('click', discard);
$('replay').addEventListener('click', () => speak(state.questionId)); $('reset').addEventListener('click', end);
$('stop-voice').addEventListener('click', () => { pauseAll(); $('voice-status').textContent = '已停下，可以回答或重听问题。'; });
$('generate').addEventListener('click', generate); $('article').addEventListener('input', updateArticle);
$('example').addEventListener('click', () => { $('article').value = example; updateArticle(); });
$('settings').addEventListener('click', () => {
  $('voice-choice').value = state.voiceId;
  $('settings-apply').textContent = state.session ? '保存并重听' : '保存设置';
  $('settings-dialog').showModal();
});
$('settings-close').addEventListener('click', () => $('settings-dialog').close());
$('settings-apply').addEventListener('click', () => {
  const voiceId = $('voice-choice').value;
  if (!Object.hasOwn(state.voices, voiceId)) return;
  pauseAll(); questionVoice.clearSource();
  state.voiceId = voiceId; showVoice();
  try { localStorage.setItem(voicePreference, voiceId); }
  catch (_) { notice('当前浏览器无法记住设置，本次选择已生效。'); }
  $('settings-dialog').close();
  if (state.session) speak(state.questionId);
});
$('audio-file').addEventListener('change', async event => {
  const file = event.target.files[0], epoch = state.epoch; if (!file) return;
  pauseAll(); busy(true, '正在读取你的录音…'); notice();
  try { await acceptRecording(await toWav(file), epoch); }
  catch (error) { if (epoch === state.epoch) notice(error.message); }
  finally { if (epoch === state.epoch) { event.target.value = ''; busy(false); } }
});
function exclusivePlayback(audio) {
  if (state.recording || state.busy) { audio.pause(); return; }
  if (audio !== $('question-audio')) questionVoice.stop();
  else if (questionVoice instanceof StreamingQuestionVoice) questionVoice.stopStream();
  document.querySelectorAll('audio').forEach(other => { if (other !== audio) other.pause(); });
}
['draft-audio', 'output-audio', 'question-audio'].forEach(id => $(id).addEventListener('play', () => exclusivePlayback($(id))));
window.addEventListener('pagehide', () => {
  recorder.release(); pauseAll(); questionVoice.clear();
  if (state.session) navigator.sendBeacon('/api/end', new Blob([JSON.stringify({ session_id: state.session })], { type: 'application/json' }));
});
$('article').value = example; updateArticle();
api('status').then(status => {
  if (status.dialogue_streaming) {
    questionVoice.clear();
    questionVoice = new StreamingQuestionVoice($('question-audio'),
      (questionId, voiceId, { signal } = {}) => api('speech-stream', { method: 'POST',
        body: { question_id: questionId, voice_id: voiceId }, raw: true, signal }), updateVoice);
  }
  state.voices = status.dialogue_voices;
  state.cloneLocal = status.clone_local === true;
  state.cloneReady = status.clone_configured;
  const model = status.dialogue_model || 'StepAudio 2.5';
  $('voice-model').textContent = model;
  $('settings-model').textContent = model;
  $('dialogue-note').textContent = status.dialogue_local
    ? '伙伴的声音在这台电脑上生成。可以在设置中切换男女声；重听已生成的问题无需等待合成。'
    : '伙伴的回复文字会交给 Step 云端朗读。同一声音重听已生成的问题无需再次合成。';
  if (status.dialogue_streaming) $('dialogue-note').textContent = '声音已在本机预热，会边生成边播放。可以在设置中切换男女声；录音时会自动停下，重听已生成的问题无需再次合成。';
  $('clone-model').textContent = status.clone_model || 'StepAudio 2.5 · 云端音色试听';
  $('clone-note').textContent = state.cloneLocal
    ? '选出的录音和对应文字只交给本机模型，生成后清除模型中的参考缓存。音色是否像本人，需要与你的原声对照试听。'
    : '点击生成会发送所选录音、对应文字和短文。生成后请求删除上传文件，不创建长期音色。';
  $('cloud-cost').hidden = state.cloneLocal;
  $('privacy-note').textContent = status.dialogue_local && state.cloneLocal
    ? '转写、对话和声音合成都在本机运行。'
    : '对话文字生成和转写在本机运行；云端声音服务的使用方式见上方说明。';
  let saved = '';
  try { saved = localStorage.getItem(voicePreference); } catch (_) { /* Use the default for this page. */ }
  state.voiceId = Object.hasOwn(state.voices, saved) ? saved : status.default_dialogue_voice;
  $('voice-choice').replaceChildren(...Object.entries(state.voices).map(([id, name]) => {
    const option = document.createElement('option'); option.value = id; option.textContent = name; return option;
  }));
  showVoice(); $('start').disabled = false; controls();
  const okay = status.transcription && status.dialogue;
  $('local-status').textContent = okay ? '本机语音已就绪' : '本机服务需要检查';
  $('local-status').classList.toggle('ready', okay);
  if (!status.transcription) notice('Whisper 转写服务没有响应，请先启动本机语音模型。');
  else if (!status.dialogue_voice_configured) notice('对话语音尚未就绪，可以先看问题并录音。');
  else if (!status.clone_configured) notice('可以先录音和对话；音色复刻模型尚未就绪。');
}).catch(error => notice(error.message));
