"""Flask routes. Calls only run_pipeline() and renders its Report."""
import json
import os
import re

from flask import Flask, flash, redirect, render_template, request, url_for

import db

try:
    from verification.pipeline import run_pipeline
except ImportError:  # pipeline not importable yet -> sample data so the UI can be developed
    run_pipeline = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
db.init_db()

LABELS = ("SUPPORTED", "CONTRADICTED", "UNVERIFIED")


def demo_pipeline(text):
    """Sample Report in the agreed contract shape. Used only when run_pipeline is missing."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    verdicts = []
    for i, s in enumerate(sentences, start=1):
        label = LABELS[(i - 1) % 3]
        verdicts.append({
            "claim_id": i, "claim_text": s, "label": label,
            "confidence": 0.91 - 0.07 * (i % 3),
            "evidence": [{"text": "Sample passage showing how evidence appears here.",
                          "source_title": "Sample source", "source_url": "https://en.wikipedia.org",
                          "score": 0.82}],
        })
    bad = sum(v["label"] != "SUPPORTED" for v in verdicts)
    return {"verdicts": verdicts, "hallucination_score": bad / max(len(verdicts), 1)}


def normalize(report):
    """Turn the Report contract into what the templates need."""
    claims = []
    for v in report.get("verdicts", []):
        claims.append({
            "id": v["claim_id"],
            # Verdict has no claim text in the contract; see note in the chat about this gap.
            "text": v.get("claim_text") or v.get("text") or f"Claim {v['claim_id']}",
            "label": v["label"],
            "confidence": round(float(v.get("confidence", 0)) * 100),
            "evidence": v.get("evidence", []),
        })
    score = float(report.get("hallucination_score", 0))
    score = round(score * 100 if score <= 1 else score)
    counts = {k: sum(c["label"] == k for c in claims) for k in LABELS}
    total = len(claims)
    evidence_claims = sum(bool(c["evidence"]) for c in claims)
    evidence_coverage = round(100 * evidence_claims / total) if total else 0
    contradiction_rate = round(100 * counts["CONTRADICTED"] / total) if total else 0
    if counts["CONTRADICTED"] and contradiction_rate >= 35:
        profile = "Contradiction signal"
        next_step = "Prioritise contradicted claims and compare their cited passages with the original wording."
    elif counts["UNVERIFIED"]:
        profile = "Evidence gaps"
        next_step = "Look for independent, reliable sources for claims marked unverified before relying on them."
    elif counts["CONTRADICTED"]:
        profile = "Mixed signals"
        next_step = "Review each contradicted claim; a small number of conflicts can still matter."
    else:
        profile = "Evidence-backed pattern"
        next_step = "The current report found support for the checked claims; still verify high-impact facts at their source."
    fingerprint = {
        "profile": profile,
        "evidence_coverage": evidence_coverage,
        "contradiction_rate": contradiction_rate,
        "evidence_claims": evidence_claims,
        "total_claims": total,
        "next_step": next_step,
    }
    return {"claims": claims, "score": score, "counts": counts, "fingerprint": fingerprint}


@app.context_processor
def inject_flags():
    return {"demo_mode": run_pipeline is None, "recent_checks": db.list_checks(5)}


@app.get("/")
def home():
    return render_template("home.html")


@app.post("/check")
def check():
    answer = request.form.get("answer", "").strip()
    if len(answer) < 20:
        flash("Paste an AI answer of at least one full sentence to check.")
        return redirect(url_for("home"))
    try:
        report = (run_pipeline or demo_pipeline)(answer)
        data = normalize(report)
    except Exception:
        app.logger.exception("Pipeline failed")
        flash("The check could not be completed. Try again, or tell the team if it keeps happening.")
        return redirect(url_for("home"))
    check_id = db.save_check(answer, report, data["score"], len(data["claims"]))
    return redirect(url_for("results", check_id=check_id))


@app.get("/results/<int:check_id>")
def results(check_id):
    row = db.get_check(check_id)
    if not row:
        flash("That check was not found.")
        return redirect(url_for("history"))
    data = normalize(json.loads(row["report_json"]))
    return render_template("results.html", row=row, data=data)


@app.get("/history")
def history():
    checks = db.list_checks()
    stats = {
        "total": len(checks),
        "avg_score": round(sum(c["score"] for c in checks) / len(checks)) if checks else 0,
        "claims": sum(c["n_claims"] for c in checks),
    }
    return render_template("history.html", checks=checks, stats=stats)


@app.post("/history/<int:check_id>/delete")
def delete_history(check_id):
    if db.delete_check(check_id):
        flash(f"Report #{check_id} was deleted from history.")
    else:
        flash("That report was already deleted or could not be found.")
    return redirect(url_for("history"))


if __name__ == "__main__":
    app.run(debug=True)