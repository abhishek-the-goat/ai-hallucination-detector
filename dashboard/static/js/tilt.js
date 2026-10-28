/**
 * tilt.js
 * -------
 * High-performance 3D parallax tilt-on-hover with specular dynamic sheen.
 * Leverages CSS custom properties (--tilt-x, --tilt-y, --glare-x, --glare-y)
 * ensuring full 60fps GPU acceleration. Never traps or cancels pointer events.
 */

(function () {
  'use strict';

  const MAX_TILT = 12; // Max rotation in degrees
  const PERSPECTIVE = 1000; // 3D depth in px

  function apply3DTilt(card) {
    let ticking = false;
    let targetRotX = 0;
    let targetRotY = 0;
    let glareX = 50;
    let glareY = 50;

    function update() {
      card.style.transform = `perspective(${PERSPECTIVE}px) rotateX(${targetRotX}deg) rotateY(${targetRotY}deg) translateZ(8px)`;
      card.style.setProperty('--glare-x', `${glareX}%`);
      card.style.setProperty('--glare-y', `${glareY}%`);
      ticking = false;
    }

    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const px = (x / rect.width) * 2 - 1;   // -1 to +1
      const py = (y / rect.height) * 2 - 1;  // -1 to +1

      targetRotX = -py * MAX_TILT;
      targetRotY =  px * MAX_TILT;

      glareX = (x / rect.width) * 100;
      glareY = (y / rect.height) * 100;

      if (!ticking) {
        requestAnimationFrame(update);
        ticking = true;
      }
    }, { passive: true });

    card.addEventListener('mouseleave', () => {
      targetRotX = 0;
      targetRotY = 0;
      card.style.transform = `perspective(${PERSPECTIVE}px) rotateX(0deg) rotateY(0deg) translateZ(0)`;
      card.style.setProperty('--glare-x', `50%`);
      card.style.setProperty('--glare-y', `50%`);
    }, { passive: true });
  }

  function init() {
    document.querySelectorAll('.tilt-card').forEach(apply3DTilt);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
