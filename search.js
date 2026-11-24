// Ambassador Jobs search/filter. No network calls, no storage, no third-party code.
(() => {
  const q = document.getElementById('q'), st = document.getElementById('st'),
        ty = document.getElementById('ty'), n = document.getElementById('n');
  if (!q || !st || !ty || !n) return;
  const form = q.form;
  if (form) form.addEventListener('submit', ev => ev.preventDefault());
  const cards = [...document.querySelectorAll('.card[data-s]')], groups = [...document.querySelectorAll('.group')];
  const p = new URLSearchParams(location.search);
  if (p.get('q')) q.value = p.get('q').slice(0, 80);
  if (p.get('state') && [...st.options].some(o => o.value === p.get('state'))) st.value = p.get('state');
  if (p.get('type') && [...ty.options].some(o => o.value === p.get('type'))) ty.value = p.get('type');
  function run() {
    const words = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean), s = st.value, y = ty.value;
    let c = 0;
    cards.forEach(a => {
      const ok = words.every(w => a.dataset.s.includes(w)) && (!s || a.dataset.st === s) && (!y || a.dataset.ty === y);
      a.hidden = !ok; if (ok) c++;
    });
    groups.forEach(g => g.hidden = !g.querySelector('.card:not([hidden])'));
    n.textContent = c + ' open job' + (c === 1 ? '' : 's');
    const u = new URLSearchParams();
    if (q.value.trim()) u.set('q', q.value.trim()); if (s) u.set('state', s); if (y) u.set('type', y);
    history.replaceState(null, '', u.toString() ? '?' + u : location.pathname);
  }
  [q, st, ty].forEach(x => x.addEventListener('input', run));
  run();
})();
