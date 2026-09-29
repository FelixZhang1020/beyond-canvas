// The child's toy, taken apart, stood up and built again: one button on the light-study viewer
// sends the fitted scene to the showpiece exhibit, where the six skills work on it and the
// dashboard shows every step. The exhibit is its own process on port 7090.
(function () {
  const EXHIBIT = 'http://127.0.0.1:7090';

  function body(scene) {
    return { request: Studio.i18n.t('showpiece.request'), scene: scene, lang: Studio.i18n.lang };
  }

  function attach(host, scene) {
    const controls = host && host.querySelector && host.querySelector('.relight-controls');
    if (!controls || !scene || scene.method !== 'geometric-approximation') return null;
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn showpiece-btn';
    b.textContent = Studio.i18n.t('showpiece.button');
    b.onclick = function () { send(scene); };
    controls.appendChild(b);
    return b;
  }

  async function send(scene) {
    const r = await fetch(EXHIBIT + '/api/runs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body(scene)),
    });
    if (r.ok) window.open(EXHIBIT + '/', '_blank');
    return r.ok;
  }

  const original = Studio.relight && Studio.relight.open;
  if (original) {
    Studio.relight.open = function (host, scene, drawing) {
      const result = original.call(Studio.relight, host, scene, drawing);
      attach(host, scene);
      return result;
    };
  }
  Studio.showpiece = { EXHIBIT: EXHIBIT, body: body, attach: attach, send: send };
})();
