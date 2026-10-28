"""
dashboard/app.py
----------------
Flask web dashboard for the AI Hallucination Detector with high-aesthetic 3D UI.

Routes:
    GET  /         — paste-answer form with interactive 3D neural core
    POST /check    — run_pipeline on submitted text, render results + 3D constellation
    GET  /history  — past checks from SQLite, newest first
    GET  /history/<id> — view specific check result

Models are loaded ONCE at startup via _warm_up_models() so that DeBERTa +
MiniLM embeddings + FAISS index are ready before the first request arrives.
"""

from __future__ import annotations

import os
import sys
import re
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path regardless of how app.py is started
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flask import Flask, render_template, request, redirect, url_for, g

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "hallucination_history.db"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = os.environ.get("FLASK_SECRET", "hallucination-detector-3d-secret")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    """Return a per-request SQLite connection, creating the schema if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(str(DB_PATH))
        g.db.row_factory = sqlite3.Row
        g.db.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp          TEXT    NOT NULL,
                answer_text        TEXT    NOT NULL,
                hallucination_score REAL   NOT NULL,
                supported_count    INTEGER NOT NULL DEFAULT 0,
                contradicted_count INTEGER NOT NULL DEFAULT 0,
                unverified_count   INTEGER NOT NULL DEFAULT 0,
                report_json        TEXT    NOT NULL
            )
        """)
        g.db.commit()
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def save_check(answer_text: str, report: dict) -> int:
    """Persist a pipeline report and return the new row id."""
    verdicts = report.get("verdicts", [])
    supported = sum(1 for v in verdicts if v.get("label") == "SUPPORTED")
    contradicted = sum(1 for v in verdicts if v.get("label") == "CONTRADICTED")
    unverified = sum(1 for v in verdicts if v.get("label") == "UNVERIFIED")

    db = get_db()
    cur = db.execute(
        """
        INSERT INTO checks
            (timestamp, answer_text, hallucination_score,
             supported_count, contradicted_count, unverified_count, report_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            answer_text,
            float(report.get("hallucination_score", 0.0)),
            supported,
            contradicted,
            unverified,
            json.dumps(report),
        ),
    )
    db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Startup: warm up models ONCE
# ---------------------------------------------------------------------------

def _warm_up_models():
    """
    Import and trigger lazy model loading so DeBERTa + MiniLM + FAISS index
    are fully ready before the first HTTP request.
    """
    print("[dashboard] Warming up pipeline models … (DeBERTa + MiniLM + FAISS)")
    try:
        from verification.models import _load_models
        _load_models()
        from retrieval.search import retrieve_evidence
        retrieve_evidence("warm up query", k=1)
        print("[dashboard] Models ready — serving requests.")
    except Exception as e:
        print(f"[dashboard] Warning during warm up: {e}")


if "pytest" not in sys.modules:
    _warm_up_models()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _highlight_text(answer_text: str, verdicts: list[dict]) -> str:
    """
    Return HTML where each verified claim span is highlighted inline.
    Green for SUPPORTED, red for CONTRADICTED, yellow for UNVERIFIED,
    with an inline confidence % badge.
    """
    text = answer_text
    lower_text = text.lower()
    annotations: list[tuple[int, int, dict]] = []

    for v in verdicts:
        claim_text = (v.get("claim_text") or "").strip().rstrip(".")
        if not claim_text:
            continue

        start_idx = -1
        match_len = len(claim_text)

        # 1. Direct exact or lowercase match
        direct = lower_text.find(claim_text.lower())
        if direct != -1:
            start_idx = direct
            match_len = len(claim_text)
        else:
            # 2. Try prefix or significant subphrase if decontextualized
            words = claim_text.split()
            for window_size in range(min(len(words), 8), 2, -1):
                subphrase = " ".join(words[:window_size]).lower()
                cand = lower_text.find(subphrase)
                if cand != -1:
                    start_idx = cand
                    # Extend until punctuation
                    end_punct = re.search(r"[.!?\n]|$", text[cand:])
                    match_len = end_punct.start() if end_punct else len(subphrase)
                    break

        if start_idx != -1:
            end_idx = min(len(text), start_idx + match_len)
            # Avoid overlaps
            if not any(not (end_idx <= s or start_idx >= e) for s, e, _ in annotations):
                annotations.append((start_idx, end_idx, v))

    # Sort annotations by position
    annotations.sort(key=lambda x: x[0])

    label_classes = {
        "SUPPORTED": "claim-supported",
        "CONTRADICTED": "claim-contradicted",
        "UNVERIFIED": "claim-unverified",
    }

    parts = []
    cursor = 0
    for start, end, v in annotations:
        if start > cursor:
            parts.append(_esc(text[cursor:start]))
        label = v.get("label", "UNVERIFIED")
        conf = int(round(v.get("confidence", 0.0) * 100))
        cls = label_classes.get(label, "claim-unverified")
        cid = v.get("claim_id", "")
        parts.append(
            f'<mark class="{cls} inline-claim" data-claim-id="{cid}" id="claim-highlight-{cid}">'
            f'{_esc(text[start:end])}'
            f'<span class="conf-badge">{conf}%</span>'
            f'</mark>'
        )
        cursor = end

    if cursor < len(text):
        parts.append(_esc(text[cursor:]))

    return "".join(parts)


def _esc(s: str) -> str:
    """Minimal HTML escape for safe template rendering."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_result_context(answer_text: str, report: dict) -> dict:
    """
    Build context dictionary for results page including enriched verdict data
    and serialized JSON for interactive 3D visualizations.
    """
    from claim_extractor.extractor import extract_claims
    claims = extract_claims(answer_text)
    claim_map = {str(c.get("claim_id")): c.get("text", "") for c in claims}

    verdicts = report.get("verdicts", [])
    enriched = []
    for v in verdicts:
        cid = str(v.get("claim_id", ""))
        item = dict(v)
        item["claim_text"] = claim_map.get(cid, "")
        enriched.append(item)

    highlighted_html = _highlight_text(answer_text, enriched)

    supported = sum(1 for v in enriched if v.get("label") == "SUPPORTED")
    contradicted = sum(1 for v in enriched if v.get("label") == "CONTRADICTED")
    unverified = sum(1 for v in enriched if v.get("label") == "UNVERIFIED")

    score = float(report.get("hallucination_score", 0.0))
    if score < 20:
        verdict_label = "TRUSTED"
        verdict_color = "#10b981"  # Emerald
        verdict_sub = "High confidence in factual alignment"
    elif score < 50:
        verdict_label = "QUESTIONABLE"
        verdict_color = "#f59e0b"  # Amber
        verdict_sub = "Contains unverified or partially conflicting statements"
    else:
        verdict_label = "HIGH HALLUCINATION"
        verdict_color = "#ef4444"  # Crimson
        verdict_sub = "Critical contradictions detected with ground-truth sources"

    return {
        "answer_text": answer_text,
        "highlighted_html": highlighted_html,
        "verdicts": enriched,
        "verdicts_json": json.dumps(enriched),
        "hallucination_score": score,
        "verdict_label": verdict_label,
        "verdict_color": verdict_color,
        "verdict_sub": verdict_sub,
        "supported": supported,
        "contradicted": contradicted,
        "unverified": unverified,
        "total": len(enriched),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/check", methods=["POST"])
def check():
    answer_text = (request.form.get("answer_text") or "").strip()
    if not answer_text:
        return redirect(url_for("index"))

    from verification.pipeline import run_pipeline
    report = run_pipeline(answer_text)

    # Persist in SQLite
    save_check(answer_text, report)

    ctx = _build_result_context(answer_text, report)
    return render_template("results.html", **ctx)


@app.route("/history")
def history():
    db = get_db()
    rows = db.execute(
        """
        SELECT id, timestamp, answer_text, hallucination_score,
               supported_count, contradicted_count, unverified_count
        FROM checks
        ORDER BY id DESC
        LIMIT 200
        """
    ).fetchall()
    return render_template("history.html", rows=rows)


@app.route("/history/<int:check_id>")
def history_detail(check_id: int):
    db = get_db()
    row = db.execute(
        "SELECT answer_text, report_json FROM checks WHERE id = ?", (check_id,)
    ).fetchone()
    if not row:
        return redirect(url_for("history"))

    answer_text = row["answer_text"]
    report = json.loads(row["report_json"])
    ctx = _build_result_context(answer_text, report)
    ctx["from_history"] = True
    ctx["check_id"] = check_id
    return render_template("results.html", **ctx)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000, use_reloader=False)
