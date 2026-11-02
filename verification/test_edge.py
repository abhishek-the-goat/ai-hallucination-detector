from verification.engine import verify_claim
from verification.models import get_nli_scores, get_embedding, cosine_similarity
from verification.pipeline import run_pipeline, retrieve_evidence


def run_tests():
    print("=" * 60)
    print("RUNNING EDGE CASE TESTS")
    print("=" * 60)

    # 1. EMPTY EVIDENCE
    print("\n--- TEST 1: EMPTY EVIDENCE ---")
    claim_1 = {"claim_id": "E1", "text": "The Eiffel Tower is in Paris"}
    evidence_1 = []
    verdict_1 = verify_claim(claim_1, evidence_1)
    print(f"Claim: {claim_1['text']}")
    print(f"Evidence count: {len(evidence_1)}")
    print(f"Verdict: Label={verdict_1['label']} | Confidence={verdict_1['confidence']}")
    print(f"Raw NLI Scores: N/A (no evidence provided)")

    # 2. UNRELATED CLAIM
    print("\n--- TEST 2: UNRELATED CLAIM ---")
    claim_2 = {"claim_id": "E2", "text": "Barack Obama was born in Hawaii"}
    evidence_2 = retrieve_evidence(claim_2["text"], k=5)
    ev_text_2 = evidence_2[0]["text"]
    nli_scores_2 = get_nli_scores(premise=ev_text_2, hypothesis=claim_2["text"])
    c_emb_2 = get_embedding(claim_2["text"])
    ev_emb_2 = get_embedding(ev_text_2)
    sim_2 = cosine_similarity(c_emb_2, ev_emb_2)
    verdict_2 = verify_claim(claim_2, evidence_2)
    print(f"Claim: {claim_2['text']}")
    print(f"Verdict: Label={verdict_2['label']} | Confidence={verdict_2['confidence']}")
    print(f"Raw NLI Scores: {nli_scores_2}")
    print(f"Cosine Similarity: {sim_2:.4f}")

    # 3. EMPTY TEXT
    print("\n--- TEST 3: EMPTY TEXT ---")
    report_3 = run_pipeline("")
    print(f"Input: ''")
    print(f"Verdicts: {report_3['verdicts']}")
    print(f"Hallucination Score: {report_3['hallucination_score']}")

    # 4. ALL CORRECT TEXT
    print("\n--- TEST 4: ALL CORRECT TEXT ---")
    text_4 = "The Eiffel Tower is in Paris. The Eiffel Tower was built in 1889."
    report_4 = run_pipeline(text_4)
    print(f"Input: '{text_4}'")
    for v in report_4["verdicts"]:
        claim_text = (
            "The Eiffel Tower is in Paris"
            if v["claim_id"] in ("C1", "1", 1)
            else "The Eiffel Tower was built in 1889"
        )
        ev_text_4 = retrieve_evidence(claim_text)[0]["text"]
        nli_scores_4 = get_nli_scores(premise=ev_text_4, hypothesis=claim_text)
        sim_4 = cosine_similarity(get_embedding(claim_text), get_embedding(ev_text_4))
        print(f"Claim ID: {v['claim_id']} | Text: '{claim_text}'")
        print(f"Verdict: Label={v['label']} | Confidence={v['confidence']}")
        print(f"Raw NLI Scores: {nli_scores_4}")
        print(f"Cosine Similarity: {sim_4:.4f}")
    print(f"Final Hallucination Score: {report_4['hallucination_score']}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    run_tests()
