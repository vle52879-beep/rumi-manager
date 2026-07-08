'use strict';

(() => {
  const VERSION = '6.4.6';
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  let renderTimer = 0;
  let requestCount = 0;
  let progressTimer = 0;

  /* --------------------------------------------------------------
     Network progress — wraps native fetch without changing payloads.
  -------------------------------------------------------------- */
  const nativeFetch = window.fetch.bind(window);
  function progressNode() {
    let node = document.querySelector('#v6-progress');
    if (!node) {
      node = document.createElement('div');
      node.id = 'v6-progress';
      node.setAttribute('aria-hidden', 'true');
      document.body?.appendChild(node);
    }
    return node;
  }
  function startProgress() {
    requestCount += 1;
    clearTimeout(progressTimer);
    progressTimer = window.setTimeout(() => progressNode()?.classList.add('active'), 90);
  }
  function stopProgress() {
    requestCount = Math.max(0, requestCount - 1);
    if (requestCount !== 0) return;
    clearTimeout(progressTimer);
    const node = document.querySelector('#v6-progress');
    window.setTimeout(() => node?.classList.remove('active'), 180);
  }
  window.fetch = async (...args) => {
    startProgress();
    try { return await nativeFetch(...args); }
    finally { stopProgress(); }
  };

  /* --------------------------------------------------------------
     App shell decorations
  -------------------------------------------------------------- */
  function addAmbient() {
    if (document.querySelector('.v6-ambient')) return;
    const ambient = document.createElement('div');
    ambient.className = 'v6-ambient';
    ambient.setAttribute('aria-hidden', 'true');
    ambient.innerHTML = '<span></span><span></span><span></span><span></span><span></span>';
    document.body.prepend(ambient);
  }

  function setSpotlight() {
    if (reduceMotion || window.innerWidth < 900) return;
    document.addEventListener('pointermove', (event) => {
      const x = Math.round((event.clientX / window.innerWidth) * 100);
      const y = Math.round((event.clientY / window.innerHeight) * 100);
      document.body.style.setProperty('--spot-x', `${x}%`);
      document.body.style.setProperty('--spot-y', `${y}%`);
    }, { passive: true });
  }

  function setupNetworkIndicator() {
    const actions = document.querySelector('.topbar-actions');
    if (!actions || actions.querySelector('.v6-network')) return;
    const node = document.createElement('span');
    node.className = 'v6-network';
    node.textContent = navigator.onLine ? 'TRỰC TUYẾN' : 'MẤT MẠNG';
    const clock = actions.querySelector('.clock');
    if (clock) clock.insertAdjacentElement('afterend', node);
    else actions.prepend(node);
    const update = () => {
      node.textContent = navigator.onLine ? 'TRỰC TUYẾN' : 'MẤT MẠNG';
      node.classList.toggle('offline', !navigator.onLine);
    };
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
  }

  function addAuthArt() {
    const visual = document.querySelector('.auth-visual');
    if (!visual || visual.dataset.v6Enhanced) return;
    visual.dataset.v6Enhanced = '1';
    visual.insertAdjacentHTML('beforeend', `
      <span class="v6-auth-bubble b1" aria-hidden="true"></span>
      <span class="v6-auth-bubble b2" aria-hidden="true"></span>
      <span class="v6-auth-bubble b3" aria-hidden="true"></span>
      <div class="v6-auth-art" aria-hidden="true">
        <span class="v6-orbit o1"></span><span class="v6-orbit o2"></span>
        <span class="v6-cup"></span>
        <span class="v6-pearl p1"></span><span class="v6-pearl p2"></span><span class="v6-pearl p3"></span><span class="v6-pearl p4"></span>
      </div>
      <span class="v6-auth-mini m1"><i></i> Chấm công GPS hợp lệ</span>
      <span class="v6-auth-mini m2"><i></i> Lịch tuần đã được chốt</span>`);
  }

  function addPasswordToggle() {
    document.querySelectorAll('input[type="password"]:not([data-v6-password])').forEach((input) => {
      input.dataset.v6Password = '1';
      const wrap = document.createElement('div');
      wrap.className = 'v6-password-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'v6-password-toggle';
      button.setAttribute('aria-label', 'Hiện mật khẩu');
      button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/></svg>';
      button.addEventListener('click', () => {
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        button.setAttribute('aria-label', show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
        button.classList.toggle('active', show);
      });
      wrap.appendChild(button);
    });
  }

  function addHeroArt() {
    document.querySelectorAll('.hero-card:not([data-v6-hero])').forEach((hero) => {
      hero.dataset.v6Hero = '1';
      hero.insertAdjacentHTML('beforeend', '<div class="v6-hero-art" aria-hidden="true"><span class="ring"></span><span class="cup"></span><span class="pearl p1"></span><span class="pearl p2"></span><span class="pearl p3"></span></div>');
    });
  }

  /* --------------------------------------------------------------
     Micro interactions
  -------------------------------------------------------------- */
  function ripple(event) {
    const target = event.target.closest('.btn,.icon-button,.nav-button,.v5-action,.modal-close');
    if (!target || target.disabled || reduceMotion) return;
    const rect = target.getBoundingClientRect();
    const dot = document.createElement('span');
    dot.className = 'v6-ripple';
    dot.style.left = `${event.clientX - rect.left}px`;
    dot.style.top = `${event.clientY - rect.top}px`;
    target.appendChild(dot);
    window.setTimeout(() => dot.remove(), 700);
  }

  function setupNavGlow() {
    document.querySelectorAll('.nav-button:not([data-v6-glow])').forEach((button) => {
      button.dataset.v6Glow = '1';
      button.addEventListener('pointermove', (event) => {
        const rect = button.getBoundingClientRect();
        button.style.setProperty('--ripple-x', `${event.clientX - rect.left}px`);
        button.style.setProperty('--ripple-y', `${event.clientY - rect.top}px`);
      }, { passive: true });
    });
  }

  function setupTilt() {
    if (reduceMotion || window.innerWidth < 980) return;
    document.querySelectorAll('.stat-card:not([data-v6-tilt]),.v5-action:not([data-v6-tilt])').forEach((card) => {
      card.dataset.v6Tilt = '1';
      card.addEventListener('pointermove', (event) => {
        const rect = card.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - .5;
        const y = (event.clientY - rect.top) / rect.height - .5;
        card.style.transform = `perspective(800px) rotateX(${(-y * 4).toFixed(2)}deg) rotateY(${(x * 5).toFixed(2)}deg) translateY(-5px)`;
      }, { passive: true });
      card.addEventListener('pointerleave', () => { card.style.transform = ''; });
    });
  }

  function animateCounter(node) {
    if (node.dataset.v6Counted || reduceMotion) return;
    const raw = node.textContent.trim();
    const match = raw.match(/^([^\d-]*)(-?\d+(?:[.,]\d+)?)(.*)$/);
    if (!match) return;
    const normalized = match[2].replace(',', '.');
    const value = Number(normalized);
    if (!Number.isFinite(value) || Math.abs(value) > 100000000000) return;
    node.dataset.v6Counted = '1';
    const decimals = (normalized.split('.')[1] || '').length;
    const start = performance.now();
    const duration = 750;
    node.classList.add('v6-counter-pop');
    const tick = (now) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 4);
      const current = value * eased;
      const number = current.toLocaleString('vi-VN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
      node.textContent = `${match[1]}${number}${match[3]}`;
      if (p < 1) requestAnimationFrame(tick);
      else node.textContent = raw;
    };
    requestAnimationFrame(tick);
  }

  function animateCounters() {
    const nodes = document.querySelectorAll('.stat-value,.v5-summary-item strong,.report-number');
    if (!('IntersectionObserver' in window)) return nodes.forEach(animateCounter);
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        animateCounter(entry.target);
        obs.unobserve(entry.target);
      });
    }, { threshold: .4 });
    nodes.forEach((node) => { if (!node.dataset.v6Counted) observer.observe(node); });
  }

  function pageReveal() {
    const page = document.querySelector('#page');
    if (!page) return;
    page.classList.remove('v6-page-enter');
    void page.offsetWidth;
    page.classList.add('v6-page-enter');
    window.setTimeout(() => page.classList.remove('v6-page-enter'), 1100);
  }

  function enhanceCards() {
    document.querySelectorAll('.card:not(.v6-hover)').forEach((card) => card.classList.add('v6-hover'));
  }

  function enhancePage() {
    addHeroArt();
    addPasswordToggle();
    enhanceCards();
    setupTilt();
    setupNavGlow();
    animateCounters();
    updateVersionLabels();
  }

  function scheduleEnhance({ reveal = false } = {}) {
    clearTimeout(renderTimer);
    renderTimer = window.setTimeout(() => {
      enhancePage();
      if (reveal) pageReveal();
    }, 24);
  }

  /* --------------------------------------------------------------
     Celebration for successful updates
  -------------------------------------------------------------- */
  function celebrate(node) {
    if (reduceMotion || !node || node.classList.contains('error')) return;
    const rect = node.getBoundingClientRect();
    const colors = ['#e5ad76','#9b5738','#55745b','#bf665e','#f2d19f'];
    for (let index = 0; index < 14; index += 1) {
      const spark = document.createElement('i');
      const angle = (Math.PI * 2 * index) / 14;
      const distance = 48 + Math.random() * 62;
      spark.className = 'v6-spark';
      spark.style.left = `${rect.left + 38}px`;
      spark.style.top = `${rect.top + rect.height / 2}px`;
      spark.style.setProperty('--dx', `${Math.cos(angle) * distance}px`);
      spark.style.setProperty('--dy', `${Math.sin(angle) * distance}px`);
      spark.style.setProperty('--spark', colors[index % colors.length]);
      document.body.appendChild(spark);
      window.setTimeout(() => spark.remove(), 900);
    }
  }

  function observeUI() {
    const page = document.querySelector('#page');
    if (page) {
      new MutationObserver(() => scheduleEnhance({ reveal: true })).observe(page, { childList: true });
    }
    const auth = document.querySelector('#auth-root');
    if (auth) {
      new MutationObserver(() => {
        window.requestAnimationFrame(() => { addAuthArt(); addPasswordToggle(); });
      }).observe(auth, { childList: true, subtree: true });
    }
    const nav = document.querySelector('#nav');
    if (nav) new MutationObserver(setupNavGlow).observe(nav, { childList: true });
    const modal = document.querySelector('#modal-root');
    if (modal) new MutationObserver(() => scheduleEnhance()).observe(modal, { childList: true, subtree: true });
    const toasts = document.querySelector('#toast-root');
    if (toasts) {
      new MutationObserver((mutations) => mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
        if (node.nodeType === 1 && node.classList.contains('toast')) celebrate(node);
      }))).observe(toasts, { childList: true });
    }
  }

  function updateVersionLabels() {
    document.title = 'RUMI Manager 6.2 — Attendance Alerts & Payroll PDF';
    document.querySelectorAll('.v5-version').forEach((node) => { node.textContent = `V${VERSION}`; });
    const chip = document.querySelector('.store-chip');
    if (chip && !chip.querySelector('.v6-version')) {
      const badge = document.createElement('span');
      badge.className = 'v6-version';
      badge.textContent = 'MOTION UI';
      badge.style.cssText = 'margin-left:auto;padding:4px 7px;border-radius:99px;background:rgba(255,255,255,.08);color:#efc9a8;font-size:7px;font-weight:900;letter-spacing:.1em';
      chip.appendChild(badge);
    }
  }

  let attendanceFingerprint = '';
  async function pollAttendanceAlerts() {
    if (typeof state === 'undefined' || !state.user || document.hidden || typeof api !== 'function') return;
    try {
      const rows = await api('/api/attendance/alerts');
      const fingerprint = (rows || []).map((x) => `${x.id}:${x.status}:${x.minutes_late}`).join('|');
      if (!attendanceFingerprint) {
        attendanceFingerprint = fingerprint;
        return;
      }
      if (fingerprint !== attendanceFingerprint) {
        attendanceFingerprint = fingerprint;
        if (rows?.length) if (typeof toast === 'function') toast(`Có ${rows.length} cảnh báo chấm công cần chú ý`, rows.some((x) => x.severity === 'danger') ? 'error' : 'warning');
        if (['dashboard','attendance'].includes(state.page) && typeof navigate === 'function') navigate(state.page);
      }
    } catch {}
  }

  function setupAttendancePolling() {
    window.setTimeout(pollAttendanceAlerts, 15000);
    window.setInterval(pollAttendanceAlerts, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) pollAttendanceAlerts(); });
  }

  function init() {
    addAmbient();
    addAuthArt();
    addPasswordToggle();
    setupNetworkIndicator();
    setupNavGlow();
    setSpotlight();
    observeUI();
    enhancePage();
    updateVersionLabels();
    setupAttendancePolling();
    document.addEventListener('click', ripple);
    document.documentElement.classList.add('rumi-v6-ready');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
