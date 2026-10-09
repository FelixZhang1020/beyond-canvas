// The studio speaks Chinese, and there is no second language to choose.
//
// A CN/EN switch used to sit in the bar, with an English table behind
// it. The operator had it removed: teachers pressed it by accident and then
// could not read the studio well enough to put it back, and a switch that can
// strand its user is worse than no switch. Chinese is not a preference here --
// it is what the art centre speaks.
//
// Chinese lives in locales/zh.js and nowhere else, which is also where the page
// build reads it to write the labels into the markup (first_paint.py), so what
// a browser paints before a line of script has run is already right. A key with
// no Chinese shows as itself; the build refuses a markup label in that state,
// and a test holds the keys the code asks for.
//
// `lang` stays, as a constant. A dozen places ask it which voice to speak with,
// how to write a date, what to call a saved file and what to tell the 3D
// viewer; they keep working and always take the Chinese branch.
window.Studio = window.Studio || {};
Studio.strings = {};
Studio.i18n = {
  lang: 'zh',
  t: function (key, vars) {
    const table = Studio.strings.zh || {};
    let s = table[key] !== undefined ? table[key] : key;
    if (vars) s = s.replace(/\{(\w+)\}/g, function (m, k) { return vars[k] !== undefined ? vars[k] : m; });
    return s;
  },
  apply: function () {
    const t = this.t.bind(this);
    document.title = t('title');
    document.querySelectorAll('[data-t]').forEach(function (el) { el.textContent = t(el.dataset.t); });
    document.querySelectorAll('[data-t-aria]').forEach(function (el) {
      el.setAttribute('aria-label', t(el.dataset.tAria));
    });
    document.querySelectorAll('[data-t-ph]').forEach(function (el) { el.placeholder = t(el.dataset.tPh); });
  }
};
