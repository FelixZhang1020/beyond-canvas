// The classroom companion can be moved without changing the chat card's layout, and so can the
// home page's jelly buddy; each remembers its own place under its own key.
window.Studio = window.Studio || {};
Studio.pet = {
  key: 'beyond-canvas.pet-position-v1',
  init(face, key = this.key) {
    if (!face) return;
    const edge = 12;
    const bounds = () => ({
      maxX: Math.max(edge, window.innerWidth - (face.offsetWidth || 56) - edge),
      maxY: Math.max(edge, window.innerHeight - (face.offsetHeight || 56) - edge)
    });
    const place = (x, y) => {
      const { maxX, maxY } = bounds();
      face.classList.add('floating');
      face.style.left = Math.max(edge, Math.min(x, maxX)) + 'px';
      face.style.top = Math.max(edge, Math.min(y, maxY)) + 'px';
    };
    const save = () => {
      try { window.localStorage.setItem(key, JSON.stringify({ x: parseFloat(face.style.left), y: parseFloat(face.style.top) })); }
      catch (_) { /* Moving still works when browser storage is unavailable. */ }
    };
    const reset = () => {
      face.classList.remove('floating');
      face.style.removeProperty('left'); face.style.removeProperty('top');
      try { window.localStorage.removeItem(key); } catch (_) {}
    };
    try {
      const saved = JSON.parse(window.localStorage.getItem(key));
      if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) place(saved.x, saved.y);
    } catch (_) {}
    let drag = null, dropped = false;
    face.addEventListener('pointerdown', event => {
      if (!event.isPrimary || event.button !== 0) return;
      dropped = false;
      const rect = face.getBoundingClientRect();
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY,
        offsetX: event.clientX - rect.left, offsetY: event.clientY - rect.top, moved: false };
      face.setPointerCapture(event.pointerId);
    });
    face.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      if (!drag.moved && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
      drag.moved = true;
      face.classList.add('is-dragging');
      place(event.clientX - drag.offsetX, event.clientY - drag.offsetY);
    });
    const finish = event => {
      if (!drag || drag.id !== event.pointerId) return;
      face.classList.remove('is-dragging');
      // Only a real release is followed by a click; a cancelled drag leaves nothing to swallow.
      if (drag.moved) { save(); dropped = event.type === 'pointerup'; }
      drag = null;
    };
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(name => face.addEventListener(name, finish));
    // Letting go after a drag is also a click, and it is not a poke.
    face.addEventListener('click', event => {
      if (!dropped) return;
      dropped = false;
      event.stopImmediatePropagation();
    }, true);
    face.addEventListener('dblclick', reset);
    face.addEventListener('keydown', event => {
      const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
      if (event.key === 'Home') { event.preventDefault(); reset(); return; }
      if (!delta) return;
      event.preventDefault();
      const rect = face.getBoundingClientRect(), step = event.shiftKey ? 32 : 12;
      place(rect.left + delta[0] * step, rect.top + delta[1] * step);
      save();
    });
    window.addEventListener('resize', () => {
      if (!face.classList.contains('floating')) return;
      place(parseFloat(face.style.left), parseFloat(face.style.top));
      save();
    });
  }
};
