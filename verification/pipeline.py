from verification.engine import verify_claim


# MOCK - replace after teammates merge
def extract_claims(answer_text: str) -> list:
    """
    Mock claim extractor that splits answer_text by '.' into claims.
    Returns: list of {"claim_id": str, "text": str}
    """
    if not answer_text:
        return []
    sentences = [s.strip() for s in answer_text.split(".") if s.strip()]
    return [{"claim_id": f"C{i}", "text": s} for i, s in enumerate(sentences, 1)]


# MOCK - replace after teammates merge
def retrieve_evidence(claim_text: str, k: int = 5) -> list:
    """
    Mock retrieval function returning a fixed evidence list.
    """
    return [
        {
            "text": (
                "The Eiffel Tower is a wrought-iron lattice tower in Paris, France. "
                "It was designed by Gustave Eiffel, completed in 1889 for the Exposition Universelle, "
                "and stands 330 metres tall."
            ),
            "source_title": "Eiffel Tower - Wikipedia",
            "source_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
            "score": 0.92,
        }
    ]


def run_pipeline(answer_text: str) -> dict:
    """
    Runs the verification pipeline on answer_text.

    Returns Report:
        {"verdicts": list, "hallucination_score": float}
    """
    claims = extract_claims(answer_text)
    total_claims = len(claims)

    if total_claims == 0:
        return {"verdicts": [], "hallucination_score": 0.0}

    verdicts = []
    contradicted_count = 0
    unverified_count = 0

    for claim in claims:
        evidence = retrieve_evidence(claim["text"], k=5)
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
