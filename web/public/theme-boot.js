// apply the saved theme before the first paint, so dark mode never flashes white.
// a file, not inline, so the content security policy can forbid inline scripts.
// the status bar's colour too, so an installed app doesn't open with a green strip over a dark sheet.
var t = null
try { t = localStorage.getItem('boredroom.theme'); if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t } catch (e) {}
if (t === 'dark' || (t !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches)) {
  var m = document.querySelector('meta[name="theme-color"]'); if (m) m.setAttribute('content', '#182033')
}
