try:
    from claim_extractor import extract_claims, analyze_claims
except ImportError:
    from claim_extractor.extractor import extract_claims, analyze_claims
from retrieval.search import retrieve_evidence
from verification.engine import verify_claim


def run_pipeline(answer_text: str, live: bool = True) -> dict:
    """
    Runs the verification pipeline on answer_text.

    Returns Report:
        {
            "verdicts": list,
            "hallucination_score": float,
            "message": str,
            "total_claims": int,
        }
    """
    raw_claims = extract_claims(answer_text)
    total_claims = len(raw_claims)

    if total_claims == 0:
        message = "No factual claims to check."
        try:
            analysis = analyze_claims(answer_text)
            if isinstance(analysis, dict) and analysis.get("status_message"):
                message = str(analysis["status_message"]).strip() or "No factual claims to check."
        except Exception:
            pass
        return {
            "verdicts": [],
            "hallucination_score": 0.0,
            "message": message,
            "total_claims": 0,
        }

    verdicts = []
    contradicted_count = 0
    unverified_count = 0

    for raw_claim in raw_claims:
        # Adapt Claim shape: ensure claim_id is str and text is str for verify_claim contract
        claim = {
            "claim_id": str(raw_claim.get("claim_id", "")),
            "text": raw_claim.get("text", ""),
        }
        raw_evidence = retrieve_evidence(claim["text"], k=5, live=live)

        # Drop any evidence whose raw similarity is below 0.5
        filtered_evidence = [
            ev for ev in raw_evidence
            if float(ev.get("raw_similarity", ev.get("cosine_similarity", ev.get("score", 0.0)))) >= 0.5
        ]

        # If all evidence is below 0.5, mark UNVERIFIED with no evidence shown
        if not filtered_evidence:
            verdict = {
                "claim_id": claim["claim_id"],
                "label": "UNVERIFIED",
                "confidence": 0.3,
                "evidence": [],
            }
        else:
            verdict = verify_claim(claim, filtered_evidence)
        verdicts.append(verdict)

        if verdict["label"] == "CONTRADICTED":
            contradicted_count += 1
        elif verdict["label"] == "UNVERIFIED":
            unverified_count += 1

    hallucination_score = (contradicted_count + 0.5 * unverified_count) / total_claims * 100.0
    hallucination_score = round(hallucination_score, 2)

    return {
        "verdicts": verdicts,
        "hallucination_score": hallucination_score,
        "message": "",
        "total_claims": total_claims,
    }
