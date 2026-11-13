// ============================================================
// Frontend app.js — static Vercel frontend for the
// AI Hallucination Detector Render backend.
//
// Relative API paths ensure Vercel rewrites proxy transparently
// to the backend without hardcoding any origin.
// ============================================================

const API_BASE = "/api";

// ------------------------------------------------------------
// Theme switcher
// ------------------------------------------------------------
(function () {
  const themeToggle = document.getElementById("theme-toggle");
  const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    if (themeToggle) {
      themeToggle.innerHTML = theme === "light" ? "☾ <span>Dark</span>" : "☼ <span>Light</span>";
      themeToggle.setAttribute("aria-label", theme === "light" ? "Switch to dark theme" : "Switch to light theme");
      themeToggle.title = theme === "light" ? "Switch to dark theme" : "Switch to light theme";
    }
  };
  let savedTheme = "dark";
  try {
    savedTheme = localStorage.getItem("hallucination-theme") || "dark";
  } catch (_) {}
  applyTheme(savedTheme);

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      applyTheme(next);
      try { localStorage.setItem("hallucination-theme", next); } catch (_) {}
    });
  }
})();

// ------------------------------------------------------------
// Custom cursor & mouse glow (optional polish from dashboard)
// ------------------------------------------------------------
(function () {
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cursor = document.querySelector(".custom-cursor");
  const glow = document.querySelector(".cursor-glow");
  if (finePointer && !reducedMotion && cursor && glow) {
    document.body.classList.add("has-custom-cursor");
    document.addEventListener("mousemove", (event) => {
      const x = event.clientX, y = event.clientY;
      cursor.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      glow.style.setProperty("--mx", `${x}px`);
      glow.style.setProperty("--my", `${y}px`);
      glow.classList.add("is-visible");
      const target = event.target.closest("a, button, input, textarea, select, .claim, .ev");
      cursor.classList.toggle("is-hovering", Boolean(target));
    }, { passive: true });
    document.addEventListener("mouseleave", () => {
      cursor.classList.remove("is-hovering");
      glow.classList.remove("is-visible");
    });
  } else {
    cursor?.remove();
    glow?.remove();
  }
})();

// ------------------------------------------------------------
// DOM helpers
// ------------------------------------------------------------
function esc(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

// ------------------------------------------------------------
// Render Pipeline Results
// ------------------------------------------------------------
function renderResults(resultData, container) {
  if (!container) return;
  container.innerHTML = "";
  container.style.display = "block";

  // Normalize data across response shapes
  const rawScore = resultData.hallucination_score !== undefined
    ? Number(resultData.hallucination_score)
    : (resultData.data && resultData.data.score !== undefined ? Number(resultData.data.score) : 0);
  const score = Math.round(rawScore * 100) / 100;

  const verdicts = resultData.verdicts || [];
  const message = resultData.message || (resultData.data && resultData.data.message) || "";

  // Normalize claims
  let claims = [];
  if (resultData.data && Array.isArray(resultData.data.claims) && resultData.data.claims.length > 0) {
    claims = resultData.data.claims.map((c, i) => ({
      id: c.id !== undefined ? String(c.id) : String(i),
      text: c.text || `Claim ${i + 1}`,
      label: (c.label || "UNVERIFIED").toUpperCase(),
      confidence: c.confidence <= 1.0 ? Math.round(c.confidence * 100) : Math.round(c.confidence),
      evidence: c.evidence || []
    }));
  } else if (verdicts.length > 0) {
    claims = verdicts.map((v, i) => {
      const conf = Number(v.confidence || 0);
      return {
        id: v.claim_id !== undefined ? String(v.claim_id) : String(i),
        text: v.claim_text || v.text || `Claim ${i + 1}`,
        label: (v.label || "UNVERIFIED").toUpperCase(),
        confidence: conf <= 1.0 ? Math.round(conf * 100) : Math.round(conf),
        evidence: v.evidence || []
      };
    });
  }

  const supportedCount = claims.filter(c => c.label === "SUPPORTED").length;
  const contradictedCount = claims.filter(c => c.label === "CONTRADICTED").length;
  const unverifiedCount = claims.filter(c => c.label === "UNVERIFIED").length;
  const totalClaims = claims.length;

  // 1. Summary section
  const summarySec = el("section", "summary");

  const scoreDiv = el("div", "score score-with-gauge");
  const gaugeDiv = el("div", "score-gauge");
  gaugeDiv.style.setProperty("--score", score);
  gaugeDiv.setAttribute("role", "img");
  gaugeDiv.setAttribute("aria-label", `${score} percent hallucination signal`);
  const scoreNum = el("span", "score-num");
  scoreNum.innerHTML = `${score}<small>%</small>`;
  gaugeDiv.append(scoreNum);

  const scoreLabel = el("span", "score-label");
  scoreLabel.innerHTML = `Hallucination signal<br><span class="muted">${score}% of claims were not marked supported</span>`;
  scoreDiv.append(gaugeDiv, scoreLabel);
  summarySec.append(scoreDiv);

  if (claims.length === 0 && message) {
    const notice = el("p", "no-claims-notice", message);
    notice.style.marginTop = "1rem";
    notice.style.fontSize = "1.05rem";
    notice.style.fontWeight = "500";
    summarySec.append(notice);
  }

  const barDiv = el("div", "bar");
  barDiv.setAttribute("role", "img");
  barDiv.setAttribute("aria-label", `${supportedCount} supported, ${contradictedCount} contradicted, ${unverifiedCount} unverified`);

  const segSup = el("span", "seg supported");
  segSup.style.flex = supportedCount;
  const segCon = el("span", "seg contradicted");
  segCon.style.flex = contradictedCount;
  const segUnv = el("span", "seg unverified");
  segUnv.style.flex = unverifiedCount;
  barDiv.append(segSup, segCon, segUnv);
  summarySec.append(barDiv);

  const countsList = el("ul", "counts");
  countsList.innerHTML = `
    <li><span class="badge supported">Supported</span> ${supportedCount}</li>
    <li><span class="badge contradicted">Contradicted</span> ${contradictedCount}</li>
    <li><span class="badge unverified">Unverified</span> ${unverifiedCount}</li>
  `;
  summarySec.append(countsList);

  container.append(summarySec);

  // 2. Report section (claims + evidence inspector)
  const reportDiv = el("div", "report");

  const claimsSec = el("section");
  claimsSec.setAttribute("aria-label", "Claims");
  const claimsHeading = el("h2");
  claimsHeading.innerHTML = `Claims <span class="muted">(${totalClaims})</span>`;
  claimsSec.append(claimsHeading);

  if (totalClaims === 0) {
    const emptyMsg = el("p", "muted", message || "No factual claims were found in this answer.");
    claimsSec.append(emptyMsg);
  } else {
    const claimsList = el("ol", "claims");
    claims.forEach((c, index) => {
      const li = el("li");
      li.style.setProperty("--i", index);

      const btn = el("button", `claim ${c.label.toLowerCase()}`);
      btn.type = "button";
      btn.dataset.index = index;
      btn.setAttribute("aria-pressed", index === 0 ? "true" : "false");

      const claimText = el("span", "claim-text", c.text);
      const claimMeta = el("span", "claim-meta");
      claimMeta.innerHTML = `<span class="badge ${c.label.toLowerCase()}">${esc(c.label)}</span> ${c.confidence}% confidence`;

      btn.append(claimText, claimMeta);
      li.append(btn);
      claimsList.append(li);
    });
    claimsSec.append(claimsList);
  }
  reportDiv.append(claimsSec);

  // Evidence panel
  const aside = el("aside", "evidence");
  aside.id = "evidence";
  aside.setAttribute("aria-live", "polite");
  aside.setAttribute("aria-label", "Evidence inspector");

  function showEvidenceForClaim(c, btnElement) {
    // Update button states
    const allBtns = reportDiv.querySelectorAll(".claim");
    allBtns.forEach(b => b.setAttribute("aria-pressed", "false"));
    if (btnElement) btnElement.setAttribute("aria-pressed", "true");

    aside.innerHTML = "";

    const toolbar = el("div", "inspector-toolbar");
    toolbar.append(el("h2", null, "Evidence inspector"));

    const copyBtn = el("button", "copy-claim ghost", "Copy claim");
    copyBtn.type = "button";
    copyBtn.style.fontSize = "0.8rem";
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(c.text);
        copyBtn.textContent = "Copied ✓";
      } catch (_) {
        copyBtn.textContent = "Copy error";
      }
      setTimeout(() => { copyBtn.textContent = "Copy claim"; }, 1500);
    });
    toolbar.append(copyBtn);
    aside.append(toolbar);

    aside.append(el("p", "evidence-claim", c.text));
    aside.append(el("p", "muted", `${c.label} · ${c.confidence}% returned confidence`));

    const evidenceList = c.evidence || [];
    if (!evidenceList.length) {
      aside.append(el("p", "muted", "No evidence passages were returned for this claim."));
      aside.append(el("p", "inspector-note", "This is an evidence gap, not proof that the claim is false."));
      return;
    }

    evidenceList.forEach(ev => {
      const card = el("div", "ev");
      card.style.background = "var(--surface)";
      card.style.border = "1px solid var(--line)";
      card.style.borderRadius = "6px";
      card.style.padding = "0.75rem";
      card.style.marginTop = "0.75rem";

      card.append(el("p", null, ev.text || ""));

      const srcP = el("p", "ev-src");
      srcP.style.fontSize = "0.85rem";
      srcP.style.marginTop = "0.4rem";

      const url = ev.source_url || "";
      const title = ev.source_title || url || "Evidence source";
      if (/^https?:\/\//i.test(url)) {
        const link = el("a", null, title);
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        srcP.append(link);
      } else {
        srcP.append(document.createTextNode(title));
      }

      const rawScore = ev.score !== undefined ? ev.score : (ev.raw_similarity !== undefined ? ev.raw_similarity : 0);
      const relScore = Math.round(Number(rawScore) * 100);
      const relSpan = el("span", "muted", ` · relevance ${relScore}%`);
      srcP.append(relSpan);

      card.append(srcP);
      aside.append(card);
    });
  }

  // Wire claim click events
  if (claims.length > 0) {
    const claimBtns = claimsSec.querySelectorAll(".claim");
    claimBtns.forEach((btn, idx) => {
      btn.addEventListener("click", () => {
        showEvidenceForClaim(claims[idx], btn);
      });
    });
    // Initially show first claim
    showEvidenceForClaim(claims[0], claimBtns[0]);
  } else {
    aside.innerHTML = `<div class="inspector-empty"><span class="inspector-icon">⌕</span><h2>Evidence inspector</h2><p>No claims were extracted to inspect.</p></div>`;
  }

  reportDiv.append(aside);
  container.append(reportDiv);
}

// ------------------------------------------------------------
// History Management (GET & DELETE)
// ------------------------------------------------------------
async function loadHistory() {
  const listEl = document.getElementById("history-list");
  const statsEl = document.getElementById("history-stats");
  if (!listEl) return;

  try {
    const resp = await fetch(`${API_BASE}/history`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    const checks = data.checks || [];
    const stats = data.stats || {};

    if (statsEl) {
      if (stats.total !== undefined) {
        statsEl.style.display = "flex";
        statsEl.innerHTML = `
          <div style="display:flex; gap:2rem; flex-wrap:wrap; font-size:0.95rem;">
            <span><strong>Total checks:</strong> ${stats.total || 0}</span>
            <span><strong>Average signal:</strong> ${stats.avg_score || 0}%</span>
            <span><strong>Claims checked:</strong> ${stats.claims || 0}</span>
          </div>
        `;
      } else {
        statsEl.style.display = "none";
      }
    }

    if (!checks.length) {
      listEl.innerHTML = `<p class="muted">No past checks found. Submit an answer above to run your first check!</p>`;
      return;
    }

    listEl.innerHTML = "";
    const ul = el("ul", "history-items");
    ul.style.listStyle = "none";
    ul.style.margin = "0";
    ul.style.padding = "0";
    ul.style.display = "grid";
    ul.style.gap = "0.75rem";

    checks.forEach(item => {
      const li = el("li", "history-item");
      li.style.background = "var(--surface)";
      li.style.border = "1px solid var(--line)";
      li.style.borderRadius = "8px";
      li.style.padding = "0.9rem 1.25rem";
      li.style.display = "flex";
      li.style.justifyContent = "space-between";
      li.style.alignItems = "center";
      li.style.gap = "1rem";
      li.style.flexWrap = "wrap";

      const left = el("div");
      left.style.flex = "1";
      left.style.minWidth = "220px";

      const meta = el("div", "muted");
      meta.style.fontSize = "0.8rem";
      meta.style.marginBottom = "0.25rem";
      meta.textContent = `${item.created_at || ""} · ${item.n_claims || 0} claim${item.n_claims === 1 ? "" : "s"}`;

      const snippet = el("div");
      snippet.style.fontWeight = "500";
      snippet.textContent = item.snippet || item.answer || `Check #${item.id}`;

      left.append(meta, snippet);

      const right = el("div");
      right.style.display = "flex";
      right.style.alignItems = "center";
      right.style.gap = "0.75rem";

      const scoreBadge = el("span", "badge");
      const s = Number(item.score || 0);
      scoreBadge.className = `badge ${s < 20 ? "supported" : s < 50 ? "unverified" : "contradicted"}`;
      scoreBadge.textContent = `${s}%`;
      right.append(scoreBadge);

      const viewBtn = el("button", "ghost", "View");
      viewBtn.type = "button";
      viewBtn.style.padding = "0.3rem 0.75rem";
      viewBtn.style.fontSize = "0.85rem";
      viewBtn.addEventListener("click", async () => {
        try {
          viewBtn.disabled = true;
          viewBtn.textContent = "Loading…";
          const dResp = await fetch(`${API_BASE}/history/${item.id}`);
          if (!dResp.ok) throw new Error(`HTTP ${dResp.status}`);
          const detail = await dResp.json();
          const resultsArea = document.getElementById("results-area");
          renderResults(detail, resultsArea);
          resultsArea.scrollIntoView({ behavior: "smooth" });
        } catch (err) {
          alert(`Failed to load check #${item.id}: ${err.message}`);
        } finally {
          viewBtn.disabled = false;
          viewBtn.textContent = "View";
        }
      });
      right.append(viewBtn);

      const delBtn = el("button", "ghost", "Delete");
      delBtn.type = "button";
      delBtn.style.padding = "0.3rem 0.75rem";
      delBtn.style.fontSize = "0.85rem";
      delBtn.style.color = "var(--bad, #b42318)";
      delBtn.addEventListener("click", async () => {
        if (!confirm(`Delete check #${item.id}?`)) return;
        try {
          delBtn.disabled = true;
          const delResp = await fetch(`${API_BASE}/history/${item.id}`, { method: "DELETE" });
          if (!delResp.ok) throw new Error(`HTTP ${delResp.status}`);
          li.remove();
          loadHistory();
        } catch (err) {
          alert(`Failed to delete check: ${err.message}`);
          delBtn.disabled = false;
        }
      });
      right.append(delBtn);

      li.append(left, right);
      ul.append(li);
    });

    listEl.append(ul);
  } catch (err) {
    listEl.innerHTML = `<p class="muted">Failed to load history (${esc(err.message)}).</p>`;
  }
}

// ------------------------------------------------------------
// Wire check form & live character counting
// ------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("check-form");
  const answerBox = document.getElementById("answer");
  const countSpan = document.getElementById("count");
  const submitBtn = document.getElementById("submit-btn");
  const statusDiv = document.getElementById("status");
  const resultsArea = document.getElementById("results-area");
  const formError = document.getElementById("form-error");
  const refreshHistoryBtn = document.getElementById("refresh-history-btn");

  if (answerBox && countSpan) {
    answerBox.addEventListener("input", () => {
      const len = answerBox.value.length;
      countSpan.textContent = `${len} character${len === 1 ? "" : "s"}`;
      if (form) form.classList.toggle("filled", len > 0);
    });
  }

  if (refreshHistoryBtn) {
    refreshHistoryBtn.addEventListener("click", () => {
      loadHistory();
    });
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = (answerBox ? answerBox.value : "").trim();
      if (!text) {
        if (formError) {
          formError.textContent = "Please paste an answer first.";
          formError.style.display = "block";
        }
        return;
      }

      if (formError) formError.style.display = "none";
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Checking…";
      }
      if (statusDiv) statusDiv.style.display = "flex";

      try {
        const resp = await fetch(`${API_BASE}/check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer: text, live: true })
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.error || `HTTP ${resp.status}`);
        }

        const data = await resp.json();
        renderResults(data, resultsArea);
        resultsArea.scrollIntoView({ behavior: "smooth" });

        // Refresh history list so the new check appears immediately
        loadHistory();
      } catch (err) {
        if (formError) {
          formError.textContent = `Check failed: ${err.message}`;
          formError.style.display = "block";
        } else {
          alert(`Check failed: ${err.message}`);
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = `<span>Analyse claims</span><span aria-hidden="true">⟶</span>`;
        }
        if (statusDiv) statusDiv.style.display = "none";
      }
    });
  }

  // Quick scan widget
  const qcToggle = document.getElementById("qc-toggle");
  const qcPanel = document.getElementById("qc-panel");
  const qcAnswer = document.getElementById("qc-answer");
  const qcSubmit = document.getElementById("qc-submit-btn");
  const qcCount = document.getElementById("qc-count");
  const qcSample = document.getElementById("qc-sample");

  if (qcToggle && qcPanel) {
    qcToggle.addEventListener("click", () => {
      const open = !qcPanel.hidden;
      qcPanel.hidden = open;
      qcToggle.setAttribute("aria-expanded", String(!open));
    });
  }

  if (qcAnswer && qcCount) {
    qcAnswer.addEventListener("input", () => {
      qcCount.textContent = `${qcAnswer.value.length} characters`;
    });
  }

  if (qcSample && qcAnswer) {
    qcSample.addEventListener("click", () => {
      qcAnswer.value = "The Eiffel Tower is in Paris, France. It was designed by Gustave Eiffel and built in 1889.";
      qcAnswer.dispatchEvent(new Event("input"));
    });
  }

  if (qcSubmit && qcAnswer) {
    qcSubmit.addEventListener("click", async () => {
      const text = qcAnswer.value.trim();
      if (!text) return;
      qcSubmit.disabled = true;
      qcSubmit.textContent = "Scanning…";
      try {
        const resp = await fetch(`${API_BASE}/check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer: text, live: true })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderResults(data, resultsArea);
        resultsArea.scrollIntoView({ behavior: "smooth" });
        if (qcPanel) qcPanel.hidden = true;
        loadHistory();
      } catch (err) {
        alert(`Scan failed: ${err.message}`);
      } finally {
        qcSubmit.disabled = false;
        qcSubmit.innerHTML = `<span>Run signal scan</span><span aria-hidden="true">⟶</span>`;
      }
    });
  }

  // Initial history load
  loadHistory();
});

