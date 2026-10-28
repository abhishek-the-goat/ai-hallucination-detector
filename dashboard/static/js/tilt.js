/**
 * tilt.js
 * -------
 * Subtle 3D tilt-on-hover effect for glass-style cards.
 * Uses GPU-accelerated CSS transforms. Never blocks mouse or form interaction.
 */

(function () {
  'use strict';

  const MAX_TILT = 7; // subtle max tilt angle in degrees

  function applyTilt(card) {
    let ticking = false;
    let targetX = 0;
    let targetY = 0;

    function update() {
      card.style.transform = `perspective(900px) rotateX(${targetX}deg) rotateY(${targetY}deg) translateZ(4px)`;
      ticking = false;
    }

    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const px = (x / rect.width) * 2 - 1;
      const py = (y / rect.height) * 2 - 1;

      targetX = -py * MAX_TILT;
      targetY =  px * MAX_TILT;

      if (!ticking) {
        requestAnimationFrame(update);
        ticking = true;
      }
    }, { passive: true });

    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0)';
    }, { passive: true });
  }

  function init() {
    document.querySelectorAll('.tilt-card').forEach(applyTilt);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
