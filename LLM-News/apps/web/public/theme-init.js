// Apply the saved or system theme before first paint to avoid a light/dark flash.
// A file rather than an inline script, so the Content-Security-Policy can forbid inline scripts.
;(function () {
  var theme = null
  try { theme = localStorage.getItem('newssense-theme') } catch (e) {}
  var dark = theme ? theme === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches
  document.documentElement.classList.toggle('dark', dark)
})()
