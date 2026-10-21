from verification.models import get_nli_scores, get_embedding, cosine_similarity


def verify_claim(claim: dict, evidence_list: list) -> dict:
    """
    Verifies a claim against a list of evidence dicts.

    Contracts:
        Claim   = {"claim_id": str, "text": str}
        Evidence = {"text": str, "source_title": str, "source_url": str, "score": float}
        Verdict = {"claim_id": str, "label": str, "confidence": float, "evidence": list}
          label must be one of: "SUPPORTED", "CONTRADICTED", "UNVERIFIED"
    """
    claim_id = claim.get("claim_id", "")

    # a. If evidence_list is empty or None: return UNVERIFIED
    if not evidence_list:
        return {
            "claim_id": claim_id,
            "label": "UNVERIFIED",
            "confidence": 0.3,
            "evidence": [],
        }

    # b. Embed the claim once
    claim_emb = get_embedding(claim["text"])

    # c. For each evidence: run get_nli_scores and compute cosine similarity
    max_contradiction = -1.0
    best_contra_ev = None

    max_entailment = -1.0
    best_entail_ev = None
    best_entail_sim = 0.0

    best_sim = -1.0
    best_sim_ev = None

    for ev in evidence_list:
        premise = ev["text"]
        nli_scores = get_nli_scores(premise=premise, hypothesis=claim["text"])
        ev_emb = get_embedding(premise)
        sim = cosine_similarity(claim_emb, ev_emb)

        contra_score = float(nli_scores.get("contradiction", 0.0))
        entail_score = float(nli_scores.get("entailment", 0.0))

        if contra_score > max_contradiction:
            max_contradiction = contra_score
            best_contra_ev = ev

        if entail_score > max_entailment:
            max_entailment = entail_score
            best_entail_ev = ev
            best_entail_sim = sim

        if sim > best_sim:
            best_sim = sim
            best_sim_ev = ev

    # d & e. Decide label, confidence, and evidence
    if max_contradiction >= 0.60:
        label = "CONTRADICTED"
        raw_confidence = max_contradiction
        evidence = [best_contra_ev] if best_contra_ev else []
    elif max_entailment >= 0.60 and best_entail_sim >= 0.40:
        label = "SUPPORTED"
        raw_confidence = max_entailment
        evidence = [best_entail_ev] if best_entail_ev else []
    else:
        label = "UNVERIFIED"
        raw_confidence = 1.0 - max(max_entailment, max_contradiction)
        # Select best available evidence
        if max_entailment >= max_contradiction and best_entail_ev:
            evidence = [best_entail_ev]
        elif best_contra_ev:
            evidence = [best_contra_ev]
        elif best_sim_ev:
            evidence = [best_sim_ev]
        else:
            evidence = []

    # f. confidence must be rounded to 4 decimal places and clipped between 0 and 1
    confidence = round(float(max(0.0, min(1.0, raw_confidence))), 4)

    return {
        "claim_id": claim_id,
        "label": label,
        "confidence": confidence,
        "evidence": evidence,
    }
