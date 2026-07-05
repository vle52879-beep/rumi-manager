'use strict';
(() => {
  const nav = document.querySelector('.nav-wrap');
  const onScroll = () => nav?.classList.toggle('scrolled', window.scrollY > 16);
  onScroll(); window.addEventListener('scroll', onScroll, { passive: true });

  const reveal = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('visible');
      reveal.unobserve(entry.target);
    });
  }, { threshold: .14 });
  document.querySelectorAll('.reveal').forEach((node, index) => {
    node.style.transitionDelay = `${Math.min(index % 4, 3) * 70}ms`;
    reveal.observe(node);
  });

  const stage = document.querySelector('.hero-stage');
  const shell = document.querySelector('.mock-shell');
  if (stage && shell && !matchMedia('(prefers-reduced-motion: reduce)').matches && innerWidth > 900) {
    stage.addEventListener('pointermove', (event) => {
      const rect = stage.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - .5;
      const y = (event.clientY - rect.top) / rect.height - .5;
      shell.style.transform = `rotateY(${(-7 + x * 7).toFixed(2)}deg) rotateX(${(3 - y * 5).toFixed(2)}deg) translateY(-3px)`;
    }, { passive: true });
    stage.addEventListener('pointerleave', () => { shell.style.transform = ''; });
  }

  document.addEventListener('click', (event) => {
    const button = event.target.closest('.btn');
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const ripple = document.createElement('i');
    ripple.style.cssText = `position:absolute;left:${event.clientX-rect.left}px;top:${event.clientY-rect.top}px;width:10px;height:10px;border-radius:50%;background:rgba(255,255,255,.5);transform:translate(-50%,-50%) scale(0);pointer-events:none;animation:landingRipple .65s ease-out forwards`;
    button.appendChild(ripple); setTimeout(() => ripple.remove(), 700);
  });
  const style = document.createElement('style');
  style.textContent = '@keyframes landingRipple{to{transform:translate(-50%,-50%) scale(20);opacity:0}}';
  document.head.appendChild(style);
})();
