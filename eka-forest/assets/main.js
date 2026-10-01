// EKA Forest v1 — tiny enhancements (site works without JS)
document.getElementById('y').textContent = new Date().getFullYear();
// FAQ: opening a question closes the others in the same column
document.querySelectorAll('.faq__col').forEach(col => {
  col.addEventListener('toggle', e => {
    if (e.target.open) col.querySelectorAll('details[open]').forEach(d => { if (d !== e.target) d.open = false; });
  }, true);
});

// Map facade: load the Google Maps iframe only when asked (keeps the page fast)
const facade = document.querySelector('.map-facade');
if (facade) facade.addEventListener('click', e => {
  e.preventDefault();
  const f = document.createElement('iframe');
  f.src = facade.dataset.embed; f.title = 'Map of Vattavada, Kerala'; f.loading = 'lazy';
  f.referrerPolicy = 'no-referrer-when-downgrade'; f.allowFullscreen = true;
  facade.replaceWith(f);
});
