// Home page: live character count and a loading state while the pipeline runs.
const form = document.getElementById("check-form");
if (form) {
  const box = document.getElementById("answer");
  const count = document.getElementById("count");
  box.addEventListener("input", () => {
    count.textContent = box.value.length + " characters";
    form.classList.toggle("filled", box.value.length > 0); // keeps the island open while it has text
  });
  // 3D tilt: the box leans slightly toward the mouse.
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    form.addEventListener("mousemove", (e) => {
      const r = form.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      form.style.setProperty("--ry", (x * 6) + "deg");
      form.style.setProperty("--rx", (-y * 5) + "deg");
    });
    form.addEventListener("mouseleave", () => {
      form.style.removeProperty("--rx");
      form.style.removeProperty("--ry");
    });
  }
  form.addEventListener("submit", () => {
    const btn = document.getElementById("submit-btn");
    btn.disabled = true;
    btn.textContent = "Checking…";
    document.getElementById("status").hidden = false;
  });
}

// Results page: clicking a claim shows its evidence in the side panel.
const dataEl = document.getElementById("claims-data");
if (dataEl) {
  const claims = JSON.parse(dataEl.textContent);
  const panel = document.getElementById("evidence");
  const buttons = document.querySelectorAll(".claim");

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text; // textContent keeps evidence text from being run as HTML
    return n;
  };

  function show(i) {
    const c = claims[i];
    buttons.forEach((b, j) => b.setAttribute("aria-pressed", j === i));
    const toolbar = el("div", "inspector-toolbar");
    toolbar.append(el("h2", null, "Evidence inspector"));
    const copy = el("button", "copy-claim", "Copy claim");
    copy.type = "button";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(c.text);
        copy.textContent = "Copied ✓";
      } catch (_) {
        const temp = el("textarea"); temp.value = c.text; temp.style.position = "fixed"; temp.style.opacity = "0";
        document.body.append(temp); temp.select();
        try { document.execCommand("copy"); copy.textContent = "Copied ✓"; } catch (err) { copy.textContent = "Copy unavailable"; }
        temp.remove();
      }
      setTimeout(() => { copy.textContent = "Copy claim"; }, 1500);
    });
    toolbar.append(copy);
    panel.replaceChildren(toolbar, el("p", "evidence-claim", c.text), el("p", "muted", `${c.label} · ${c.confidence}% returned confidence`));
    if (!c.evidence.length) {
      panel.append(el("p", "muted", "No evidence passages were returned for this claim."));
      panel.append(el("p", "inspector-note", "This is an evidence gap, not proof that the claim is false."));
      return;
    }
    c.evidence.forEach((ev) => {
      const card = el("div", "ev");
      card.append(el("p", null, ev.text));
      const src = el("p", "ev-src");
      if (/^https?:\/\//.test(ev.source_url || "")) {
        const a = el("a", null, ev.source_title || ev.source_url);
        a.href = ev.source_url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        src.append(a);
      } else {
        src.textContent = ev.source_title || "Unknown source";
      }
      src.append(el("span", "muted", " · relevance " + Math.round((ev.score || 0) * 100) + "%"));
      card.append(src);
      panel.append(card);
    });
  }

  buttons.forEach((b, i) => b.addEventListener("click", () => show(i)));
  if (claims.length) show(0);
}

// Floating quick check: open and close the panel, loading state on submit.
const qcToggle = document.getElementById("qc-toggle");
if (qcToggle) {
  const panel = document.getElementById("qc-panel");
  const answerBox = document.getElementById("qc-answer");
  const qcCount = document.getElementById("qc-count");
  const sampleBtn = document.getElementById("qc-sample");
  const setOpen = (open) => {
    panel.hidden = !open;
    qcToggle.setAttribute("aria-expanded", open);
    qcToggle.classList.toggle("is-open", open);
    if (open) answerBox.focus();
  };
  const updateQuickCount = () => {
    const n = answerBox.value.length;
    qcCount.textContent = n + " characters · " + (n >= 20 ? "ready to scan" : Math.max(0, 20 - n) + " more needed");
    qcCount.classList.toggle("qc-count-ready", n >= 20);
  };
  answerBox.addEventListener("input", updateQuickCount);
  if (sampleBtn) sampleBtn.addEventListener("click", () => {
    answerBox.value = "The Great Wall of China is visible from the Moon with the naked eye. Water boils at 100°C at sea level. The human body has 206 bones in adulthood.";
    answerBox.dispatchEvent(new Event("input", { bubbles: true }));
    answerBox.focus();
  });
  updateQuickCount();
  qcToggle.addEventListener("click", () => setOpen(panel.hidden));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) { setOpen(false); qcToggle.focus(); }
  });
  panel.addEventListener("submit", () => {
    const b = panel.querySelector(".qc-submit");
    b.disabled = true;
    b.querySelector("span:first-child").textContent = "Scanning signals…";
  });
}

// Zoom transition: the clicked link grows into a wave that fills the screen, then the report opens.
try { sessionStorage.removeItem("zoomIn"); } catch (e) {}
document.addEventListener("click", (e) => {
  const link = e.target.closest("a.zoom-link");
  if (!link || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return; // normal navigation
  e.preventDefault();
  const r = link.getBoundingClientRect();
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  const far = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  const ov = document.createElement("div");
  ov.className = "zoom-overlay";
  ov.style.left = x + "px";
  ov.style.top = y + "px";
  ov.style.setProperty("--s", (far / 20) * 1.15); // overlay is 40px wide, so its radius is 20px
  document.body.append(ov);
  link.classList.add("zooming");
  try { sessionStorage.setItem("zoomIn", "1"); } catch (err) {}
  requestAnimationFrame(() => requestAnimationFrame(() => ov.classList.add("go")));
  setTimeout(() => { window.location.href = link.href; }, 650);
});
// Coming back with the Back button: clear the overlay left on the cached page.
window.addEventListener("pageshow", () => {
  document.querySelectorAll(".zoom-overlay").forEach((o) => o.remove());
  document.querySelectorAll(".zooming").forEach((l) => l.classList.remove("zooming"));
});

// Global premium interactions: accessible custom cursor, pointer glow and theme switch.
(() => {
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cursor = document.querySelector('.custom-cursor');
  const glow = document.querySelector('.cursor-glow');
  if (finePointer && !reducedMotion && cursor && glow) {
    document.body.classList.add('has-custom-cursor');
    let x = innerWidth / 2, y = innerHeight / 2;
    document.addEventListener('mousemove', (event) => {
      x = event.clientX; y = event.clientY;
      cursor.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      glow.style.setProperty('--mx', `${x}px`);
      glow.style.setProperty('--my', `${y}px`);
      glow.classList.add('is-visible');
      const target = event.target.closest('a, button, input, textarea, select, .claim, .fingerprint-metric, .ev');
      cursor.classList.toggle('is-hovering', Boolean(target));
      if (target && target.matches('button, a, .claim')) cursor.classList.add('is-action');
      else cursor.classList.remove('is-action');
    }, { passive: true });
    document.addEventListener('mouseleave', () => { cursor.classList.remove('is-hovering'); glow.classList.remove('is-visible'); });
    document.addEventListener('mousedown', () => cursor.classList.add('is-clicking'));
    document.addEventListener('mouseup', () => cursor.classList.remove('is-clicking'));
    document.addEventListener('click', (event) => {
      const ripple = document.createElement('span');
      ripple.className = 'cursor-ripple';
      ripple.style.left = `${event.clientX}px`; ripple.style.top = `${event.clientY}px`;
      document.body.append(ripple);
      setTimeout(() => ripple.remove(), 650);
    });
  } else {
    cursor?.remove(); glow?.remove();
  }

  const themeToggle = document.getElementById('theme-toggle');
  const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    if (themeToggle) {
      themeToggle.innerHTML = theme === 'light' ? '☾ <span>Dark</span>' : '☼ <span>Light</span>';
      themeToggle.setAttribute('aria-label', theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
      themeToggle.title = theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme';
    }
  };
  let savedTheme = 'dark';
  try { savedTheme = localStorage.getItem('hallucination-theme') || 'dark'; } catch (_) {}
  applyTheme(savedTheme);
  themeToggle?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    applyTheme(next);
    try { localStorage.setItem('hallucination-theme', next); } catch (_) {}
  });
})();

// Report: draw a lightweight SVG claim-to-evidence relationship map from returned data.
if (dataEl) {
  const graph = document.getElementById('evidence-network');
  const claims = JSON.parse(dataEl.textContent);
  if (graph) {
    const ns = 'http://www.w3.org/2000/svg';
    const svgEl = (tag, attrs = {}) => {
      const node = document.createElementNS(ns, tag);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
      return node;
    };
    const svg = svgEl('svg', { viewBox: '0 0 900 300', role: 'img', 'aria-label': 'Claims connected to evidence returned by the verification pipeline' });
    const defs = svgEl('defs');
    const gradient = svgEl('linearGradient', { id: 'network-line', x1: '0%', y1: '0%', x2: '100%', y2: '100%' });
    gradient.append(svgEl('stop', { offset: '0%', 'stop-color': '#7c8cff', 'stop-opacity': '.8' }), svgEl('stop', { offset: '100%', 'stop-color': '#44d9ff', 'stop-opacity': '.35' }));
    defs.append(gradient); svg.append(defs);
    const shownClaims = claims.slice(0, 8);
    if (!shownClaims.length) {
      graph.innerHTML = '<p class="muted network-empty">No claims were returned, so there is no relationship map to display.</p>';
    } else {
      const claimX = 150, sourceX = 650;
      const yFor = (i, n) => (n === 1 ? 150 : 35 + i * (230 / (n - 1)));
      shownClaims.forEach((claim, i) => {
        const cy = yFor(i, shownClaims.length);
        const evidences = (claim.evidence || []).slice(0, 2);
        evidences.forEach((ev, j) => {
          const sourceIndex = i * 2 + j;
          const sy = yFor(sourceIndex, Math.max(1, shownClaims.length * 2));
          svg.append(svgEl('path', { d: `M ${claimX + 94} ${cy} C 350 ${cy}, 450 ${sy}, ${sourceX - 90} ${sy}`, class: 'network-edge' }));
        });
        const group = svgEl('g', { class: `network-claim-node ${String(claim.label || 'unverified').toLowerCase()}`, tabindex: '0', role: 'button', 'aria-label': `Inspect claim ${i + 1}: ${claim.text}`, 'data-claim-index': i });
        group.append(svgEl('circle', { cx: claimX, cy, r: 18, class: 'network-node-circle' }));
        const number = svgEl('text', { x: claimX, y: cy + 4, 'text-anchor': 'middle', class: 'network-node-number' }); number.textContent = String(i + 1); group.append(number);
        const label = svgEl('text', { x: claimX + 28, y: cy + 4, class: 'network-node-label' }); label.textContent = `Claim ${i + 1}`; group.append(label);
        const inspect = () => document.querySelectorAll('.claim')[i]?.click();
        group.addEventListener('click', inspect); group.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); inspect(); } });
        svg.append(group);
        evidences.forEach((ev, j) => {
          const sourceIndex = i * 2 + j;
          const sy = yFor(sourceIndex, Math.max(1, shownClaims.length * 2));
          const source = svgEl('g', { class: 'network-source-node', tabindex: '0', role: 'button', 'aria-label': `Evidence source for claim ${i + 1}` });
          source.append(svgEl('rect', { x: sourceX - 88, y: sy - 13, width: 176, height: 26, rx: 8, class: 'network-source-box' }));
          const sourceLabel = svgEl('text', { x: sourceX, y: sy + 4, 'text-anchor': 'middle', class: 'network-source-label' });
          const title = (ev.source_title || 'Evidence passage'); sourceLabel.textContent = title.length > 22 ? title.slice(0, 21) + '…' : title;
          source.append(sourceLabel); svg.append(source);
          const inspect = () => document.querySelectorAll('.claim')[i]?.click();
          source.addEventListener('click', inspect); source.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); inspect(); } });
        });
      });
      if (claims.length > shownClaims.length) {
        const note = svgEl('text', { x: 450, y: 292, 'text-anchor': 'middle', class: 'network-more' });
        note.textContent = `Showing ${shownClaims.length} of ${claims.length} claims`; svg.append(note);
      }
      graph.replaceChildren(svg);
    }
  }
}

// History dashboard: search, verdict-signal filter and sorting without a page reload.
(() => {
  const table = document.getElementById('history-table');
  if (!table) return;
  const tbody = table.querySelector('tbody');
  const search = document.getElementById('history-search');
  const filter = document.getElementById('history-filter');
  const sort = document.getElementById('history-sort');
  const count = document.getElementById('history-count');
  const empty = document.getElementById('history-empty-filter');
  const rows = [...tbody.querySelectorAll('tr')];
  const update = () => {
    const q = search.value.trim().toLowerCase();
    const range = filter.value;
    const mode = sort.value;
    const visible = rows.filter((row) => {
      const score = Number(row.dataset.score);
      const matchesText = (row.dataset.search || '').includes(q);
      const matchesRange = range === 'all' || (range === 'low' && score < 20) || (range === 'medium' && score >= 20 && score < 50) || (range === 'high' && score >= 50);
      row.hidden = !(matchesText && matchesRange);
      return !row.hidden;
    });
    visible.sort((a, b) => {
      if (mode === 'oldest') return a.dataset.date.localeCompare(b.dataset.date);
      if (mode === 'score-high') return Number(b.dataset.score) - Number(a.dataset.score);
      if (mode === 'score-low') return Number(a.dataset.score) - Number(b.dataset.score);
      return Number(b.dataset.id) - Number(a.dataset.id);
    });
    visible.forEach((row) => tbody.append(row));
    count.textContent = `${visible.length} of ${rows.length} reports`;
    empty.hidden = visible.length > 0;
  };
  [search, filter, sort].forEach((control) => control.addEventListener('input', update));
  update();
})();


// ---- Interactive Cursor-Reactive Starfield ----
(() => {
  const canvas = document.getElementById('starfield-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let width = 0;
  let height = 0;
  let dpr = 1;
  let stars = [];
  const mouse = { x: -9999, y: -9999, active: false };

  const resize = () => {
    dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    initStars();
  };

  const initStars = () => {
    const count = Math.max(90, Math.min(220, Math.floor((width * height) / 8500)));
    stars = [];
    for (let i = 0; i < count; i++) {
      const x = Math.random() * width;
      const y = Math.random() * height;
      const baseAlpha = 0.3 + Math.random() * 0.6;
      stars.push({
        x,
        y,
        baseX: x,
        baseY: y,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        radius: 0.75 + Math.random() * 1.35,
        alpha: baseAlpha,
        baseAlpha: baseAlpha,
        twinklePhase: Math.random() * Math.PI * 2,
        twinkleSpeed: 0.015 + Math.random() * 0.025,
      });
    }
  };

  window.addEventListener('resize', resize, { passive: true });
  window.addEventListener('mousemove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    mouse.active = true;
  }, { passive: true });

  window.addEventListener('mouseleave', () => {
    mouse.active = false;
    mouse.x = -9999;
    mouse.y = -9999;
  });

  window.addEventListener('touchmove', (e) => {
    if (e.touches && e.touches[0]) {
      mouse.x = e.touches[0].clientX;
      mouse.y = e.touches[0].clientY;
      mouse.active = true;
    }
  }, { passive: true });

  window.addEventListener('touchend', () => {
    mouse.active = false;
    mouse.x = -9999;
    mouse.y = -9999;
  });

  const INTERACTION_RADIUS = 160;
  const SPRING = 0.04;

  const render = () => {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
    const isDark = document.documentElement.dataset.theme !== 'light';
    const baseColor = isDark ? '255, 255, 255' : '0, 0, 0';

    for (let i = 0; i < stars.length; i++) {
      const s = stars[i];

      if (!reducedMotion) {
        // Natural gentle drift
        s.baseX += s.vx;
        s.baseY += s.vy;
        if (s.baseX < 0) s.baseX = width;
        else if (s.baseX > width) s.baseX = 0;
        if (s.baseY < 0) s.baseY = height;
        else if (s.baseY > height) s.baseY = 0;

        // Cursor reaction: deflection + brightening + constellation link
        if (mouse.active) {
          const dx = s.x - mouse.x;
          const dy = s.y - mouse.y;
          const dist = Math.hypot(dx, dy);

          if (dist < INTERACTION_RADIUS && dist > 0) {
            const force = (1 - dist / INTERACTION_RADIUS);
            const angle = Math.atan2(dy, dx);
            const push = force * 26;
            s.x += Math.cos(angle) * push * 0.2;
            s.y += Math.sin(angle) * push * 0.2;
            s.alpha = Math.min(1.0, s.baseAlpha + force * 0.6);

            // Subtle interactive constellation line to cursor
            ctx.beginPath();
            ctx.moveTo(s.x, s.y);
            ctx.lineTo(mouse.x, mouse.y);
            ctx.strokeStyle = `rgba(${baseColor}, ${force * 0.3})`;
            ctx.lineWidth = 0.85;
            ctx.stroke();
          } else {
            s.alpha += (s.baseAlpha - s.alpha) * 0.08;
          }
        } else {
          s.alpha += (s.baseAlpha - s.alpha) * 0.08;
        }

        // Return smoothly toward base coordinates
        s.x += (s.baseX - s.x) * SPRING;
        s.y += (s.baseY - s.y) * SPRING;

        s.twinklePhase += s.twinkleSpeed;
      }

      const twinkle = Math.sin(s.twinklePhase) * 0.22;
      const currentAlpha = Math.max(0.18, Math.min(1.0, s.alpha + twinkle));

      // Draw crisp dotted star
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${baseColor}, ${currentAlpha})`;
      ctx.fill();

      // Soft glow for bright stars
      if (currentAlpha > 0.65) {
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.radius * 2.5, 0, Math.PI * 2);
        const glowAlpha = isDark ? (currentAlpha - 0.65) * 0.35 : (currentAlpha - 0.65) * 0.18;
        ctx.fillStyle = `rgba(${baseColor}, ${glowAlpha})`;
        ctx.fill();
      }
    }

    // Connect close neighboring stars near the cursor to create a celestial constellation web
    if (mouse.active && !reducedMotion) {
      for (let i = 0; i < stars.length; i++) {
        const s1 = stars[i];
        if (Math.hypot(s1.x - mouse.x, s1.y - mouse.y) > INTERACTION_RADIUS) continue;
        for (let j = i + 1; j < stars.length; j++) {
          const s2 = stars[j];
          const distBetween = Math.hypot(s1.x - s2.x, s1.y - s2.y);
          if (distBetween < 85) {
            const lineAlpha = (1 - distBetween / 85) * (isDark ? 0.25 : 0.2);
            ctx.beginPath();
            ctx.moveTo(s1.x, s1.y);
            ctx.lineTo(s2.x, s2.y);
            ctx.strokeStyle = `rgba(${baseColor}, ${lineAlpha})`;
            ctx.lineWidth = 0.75;
            ctx.stroke();
          }
        }
      }
    }

    if (!reducedMotion) {
      requestAnimationFrame(render);
    }
  };

  resize();
  if (reducedMotion) {
    render();
  } else {
    requestAnimationFrame(render);
  }
})();