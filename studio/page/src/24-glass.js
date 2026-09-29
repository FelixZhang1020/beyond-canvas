// Direction A keeps glass still. Only the selected activity pill moves.
window.Studio = window.Studio || {};
Studio.glass = {
  init: function (root) {
    root.querySelectorAll('.seg').forEach(function (seg) { Studio.glass.segment(seg); });
  },
  segment: function (seg) {
    const btns = seg.querySelectorAll('button');
    function move(b) {
      seg.style.setProperty('--l', b.offsetLeft + 'px'); seg.style.setProperty('--w', b.offsetWidth + 'px');
      btns.forEach(function (x) { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
    }
    btns.forEach(function (b) { b.addEventListener('click', function () { move(b); }); });
    seg.select = function (value, attr) {
      const b = Array.from(btns).find(function (x) { return x.dataset[attr] === value; }); if (b) move(b);
    };
    seg.refresh = function () { const on = seg.querySelector('button.on'); if (on) move(on); };
    addEventListener('resize', seg.refresh);
    seg.refresh();
  }
};
