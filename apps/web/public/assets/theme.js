/* Apply the saved/system theme before the workspace paints. */
(function () {
  var saved;
  try { saved = window.localStorage.getItem('sympulse.theme.v1'); } catch (_) {}
  var dark = saved === 'dark' || (saved !== 'light' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', dark ? '#131018' : '#6100DC');
})();
