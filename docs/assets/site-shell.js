/* Shared navigation shell. All pages use the same language selection,
   theme control and visible sidebar; page-specific interactions are preserved. */
(() => {
  'use strict';
  const header = document.querySelector('header.topbar');
  const actions = header?.querySelector('.top-actions');
  if (!header || !actions) return;

  const english = (document.documentElement.lang || 'ko').toLowerCase().startsWith('en');
  const locale = english ? 'en' : 'ko';
  const pathname = location.pathname;
  const projectPrefix = '/epl-run-in-lab/';
  const base = pathname.startsWith(projectPrefix) ? projectPrefix : '/';
  let relative = pathname.startsWith(base) ? pathname.slice(base.length) : '';
  if (relative.startsWith('en/')) relative = relative.slice(3);
  const suffix = location.search + location.hash;
  const koPath = base + relative + suffix;
  const enPath = base + 'en/' + relative + suffix;

  const brand = header.querySelector('.brand');
  if (brand) {
    const link = document.createElement('a');
    link.className = 'brand';
    link.href = base + (english ? 'en/' : '');
    link.append(document.createTextNode('EPL '));
    const rest = document.createElement('span');
    rest.textContent = 'Run-in Lab';
    link.append(rest);
    brand.replaceWith(link);
  }

  // Keep the same sidebar sections even on older generated report pages.
  const sidebarNav = document.getElementById('sidebar');
  if (sidebarNav) {
    const existing = Array.from(sidebarNav.querySelectorAll('.nav-btn'));
    const congestionPath = base + (english ? 'en/' : '') + 'congestion.html';
    const hasCongestion = existing.some(el =>
      (el.getAttribute('href') || '').includes('/congestion.html') ||
      (el.textContent || '').includes('일정 혼잡도') ||
      (el.textContent || '').includes('Fixture Congestion')
    );
    if (!hasCongestion) {
      const link = document.createElement('a');
      link.className = 'nav-btn';
      link.href = congestionPath;
      link.textContent = english ? 'Fixture Congestion' : '일정 혼잡도';
      const difficulty = existing.find(el =>
        (el.textContent || '').includes('일정 난이도') ||
        (el.textContent || '').includes('Fixture Difficulty')
      );
      if (difficulty) difficulty.after(link);
      else {
        const about = Array.from(sidebarNav.querySelectorAll('.nav-label'))
          .find(el => (el.textContent || '').trim().toLowerCase() === 'about');
        if (about) about.before(link);
        else sidebarNav.append(link);
      }
    }
  }

  // Retain the existing notice modal, but keep the header as clean as
  // the congestion page. Moving the original node preserves its listener.
  const notice = actions.querySelector('#noticeBtn');
  const sidebar = document.getElementById('sidebar');
  if (notice && sidebar) {
    notice.className = 'nav-btn';
    notice.style.cssText = '';
    notice.textContent = english ? 'Important notice' : '주의사항';
    const about = Array.from(sidebar.querySelectorAll('.nav-label')).find(el =>
      (el.textContent || '').trim().toLowerCase() === 'about'
    );
    // Append in the About section after existing model link.
    sidebar.append(notice);
  }

  const picker = document.createElement('div');
  picker.className = 'site-language-picker';
  picker.id = 'siteLanguagePicker';
  const button = document.createElement('button');
  button.className = 'site-language-trigger';
  button.type = 'button';
  button.id = 'siteLanguageButton';
  button.setAttribute('aria-label', english ? 'Choose language' : '언어 선택');
  button.setAttribute('aria-haspopup', 'true');
  button.setAttribute('aria-expanded', 'false');
  button.setAttribute('aria-controls', 'siteLanguageOptions');
  button.textContent = english ? 'Language ▾' : '언어 ▾';
  const menu = document.createElement('div');
  menu.className = 'site-language-options';
  menu.id = 'siteLanguageOptions';
  menu.setAttribute('aria-label', english ? 'Display language' : '표시 언어');
  menu.hidden = true;
  const entries = [
    { code:'ko', label: english ? 'Korean' : '한국어', url:koPath },
    { code:'en', label: english ? 'English' : '영어', url:enPath }
  ];
  entries.forEach(entry => {
    const link = document.createElement('a');
    link.href = entry.url;
    link.lang = entry.code;
    link.dataset.lang = entry.code;
    if (locale === entry.code) link.setAttribute('aria-current', 'page');
    const mainLabel = document.createElement('span');
    mainLabel.textContent = entry.label;
    const check = document.createElement('span');
    check.className = 'site-language-check';
    check.textContent = '✓';
    check.setAttribute('aria-hidden', 'true');
    link.append(mainLabel, check);
    link.addEventListener('click', () => {
      try { localStorage.setItem('runin-lang', entry.code); } catch (e) {}
    });
    menu.append(link);
  });
  picker.append(button, menu);

  function closeLanguage(focusButton = false) {
    menu.hidden = true;
    button.setAttribute('aria-expanded','false');
    if (focusButton) button.focus();
  }
  button.addEventListener('click', () => {
    menu.hidden = !menu.hidden;
    button.setAttribute('aria-expanded',String(!menu.hidden));
  });
  document.addEventListener('pointerdown', e => {
    if (!picker.contains(e.target)) closeLanguage();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !menu.hidden) closeLanguage(true);
  });

  const theme = document.createElement('button');
  theme.type = 'button';
  theme.className = 'site-theme';
  theme.id = 'siteThemeButton';
  function updateThemeLabel() {
    const dark = document.body.classList.contains('dark');
    theme.textContent = english
      ? (dark ? 'Light mode' : 'Dark mode')
      : (dark ? '라이트모드' : '다크모드');
    theme.setAttribute('aria-label', english
      ? (dark ? 'Switch to light mode' : 'Switch to dark mode')
      : (dark ? '라이트모드로 전환' : '다크모드로 전환'));
    theme.setAttribute('aria-pressed',String(dark));
  }
  try { if (localStorage.getItem('runin-theme') === 'dark') document.body.classList.add('dark'); }
  catch (e) {}
  updateThemeLabel();
  theme.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    try { localStorage.setItem('runin-theme', document.body.classList.contains('dark') ? 'dark' : 'light'); }
    catch (e) {}
    updateThemeLabel();
  });
  actions.replaceChildren(picker, theme);
})();
