// apply the saved theme before the first paint, so dark mode never flashes white.
// a file, not inline, so the content security policy can forbid inline scripts.
try { var t = localStorage.getItem('boredroom.theme'); if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t } catch (e) {}
