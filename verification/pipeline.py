import verification.models  # Ensures PyTorch CPU accelerator patch is active
from claim_extractor.extractor import extract_claims
from retrieval.search import retrieve_evidence
from verification.engine import verify_claim


def run_pipeline(answer_text: str) -> dict:
    """
    Runs the verification pipeline on answer_text.

    Returns Report:
        {"verdicts": list, "hallucination_score": float}
    """
    raw_claims = extract_claims(answer_text)
    total_claims = len(raw_claims)

    if total_claims == 0:
        return {"verdicts": [], "hallucination_score": 0.0}

    verdicts = []
    contradicted_count = 0
    unverified_count = 0

    for raw_claim in raw_claims:
        # Adapt Claim shape: ensure claim_id is str and text is str for verify_claim contract
        claim = {
            "claim_id": str(raw_claim.get("claim_id", "")),
            "text": raw_claim.get("text", ""),
        }
        raw_evidence = retrieve_evidence(claim["text"], k=5)
        # Adapt Evidence shape: ensure text, source_title, source_url, and score keys
        evidence = [
            {
                "text": ev.get("text", ""),
                "source_title": ev.get("source_title", ""),
                "source_url": ev.get("source_url", ""),
                "score": float(ev.get("score", 0.0)),
            }
            for ev in raw_evidence
        ]
        verdict = verify_claim(claim, evidence)
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
    }

