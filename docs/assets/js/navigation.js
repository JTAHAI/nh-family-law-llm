const toggle = document.querySelector('.nav-toggle');
const nav = document.getElementById('site-nav');
const narrow = window.matchMedia('(max-width: 940px)');

function setMenu(open) {
  toggle.setAttribute('aria-expanded', String(open));
  nav.hidden = !open;
}

function syncMenu() {
  toggle.hidden = !narrow.matches;
  setMenu(!narrow.matches);
}

syncMenu();
narrow.addEventListener('change', syncMenu);
toggle.addEventListener('click', () => setMenu(nav.hidden));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && narrow.matches && !nav.hidden) {
    setMenu(false);
    toggle.focus();
  }
});
