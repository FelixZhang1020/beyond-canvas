// Shared keyboard behaviour for the studio sheets. Hidden panels never retain focus.
window.Studio = window.Studio || {};
Studio.dialogs = {
  init: function (root) {
    const panels = Array.from(root.querySelectorAll('.overlay, #ledger'));
    const closeButtons = { 'sheet-overlay': 'start-back', 'lesson-overlay': 'lesson-close',
      'switch-class-overlay': 'switch-class-close', 'end-class-overlay': 'end-class-cancel', 'camera-overlay': 'cam-close', 'viewer-overlay': 'viewer-close',
      'remove-drawing-overlay': 'remove-drawing-cancel', 'delete-class-overlay': 'delete-class-cancel', 'chat-clear-overlay': 'chat-clear-cancel',
      'admin-overlay': 'admin-close', 'board-overlay': 'board-close', 'prompts-overlay': 'prompts-close', 'samples-overlay': 'samples-close',
      ledger: 'ledger-back' };
    let active = null, returnTo = null;
    function controls(panel) {
      return Array.from(panel.querySelectorAll('a[href], button, input, textarea, select, summary, [tabindex]'))
        .concat(window.Backstage?.controls() || [])
        .filter(function (el) { return !el.disabled && el.tabIndex >= 0 && el.getClientRects().length && !el.closest('[hidden]'); });
    }
    function sync() {
      const shown = panels.filter(function (panel) { return !panel.hidden; }).pop() || null;
      const previous = active;
      if (shown && !previous) returnTo = document.activeElement;
      active = shown;
      if (shown !== previous) window.Backstage?.dock(shown);
      const portfolio = document.getElementById('portfolio');
      Array.from(root.children).forEach(function (el) {
        el.inert = shown ? el !== shown && el.id !== 'toast'
          : el.id === 'creation-workspace' && !portfolio.hidden;
      });
      if (shown === previous) return;
      if (shown) {
        const first = controls(shown)[0]; if (first) first.focus({ preventScroll: true });
      } else if (previous) {
        const target = returnTo && returnTo !== document.body && returnTo.isConnected && returnTo.getClientRects().length && !returnTo.closest('[hidden]')
          ? returnTo : document.getElementById('btn-upload');
        if (target) target.focus({ preventScroll: true });
        returnTo = null;
      }
    }
    new MutationObserver(sync).observe(root, { subtree: true, attributes: true, attributeFilter: ['hidden'] });
    document.addEventListener('keydown', function (event) {
      if (!active) return;
      if (event.key === 'Escape') {
        const id = closeButtons[active.id];
        const button = id && document.getElementById(id);
        if (button && button.getClientRects().length && !button.closest('[hidden]')) { event.preventDefault(); button.click(); }
        return;
      }
      if (event.key !== 'Tab') return;
      const items = controls(active), first = items[0], last = items[items.length - 1];
      if (!first) { event.preventDefault(); return; }
      const focused = document.activeElement?.shadowRoot?.activeElement || document.activeElement;
      if (!active.contains(document.activeElement) || (event.shiftKey && focused === first)) {
        event.preventDefault(); (event.shiftKey ? last : first).focus();
      } else if (!event.shiftKey && focused === last) {
        event.preventDefault(); first.focus();
      }
    });
    sync();
  }
};
