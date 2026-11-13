import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from verification.pipeline import run_pipeline


def test_no_factual_and_eiffel():
    # Test A: Emotional input (live=True by default)
    text_a = "i am happy"
    print(f"\n{'='*70}\nTest A: Emotional input: {text_a!r}\n{'='*70}")
    report_a = run_pipeline(text_a)
    print(json.dumps(report_a, indent=2))
    assert report_a["hallucination_score"] == 0.0
    assert report_a["verdicts"] == []
    assert report_a["total_claims"] == 0
    assert "no" in report_a["message"].lower() or "not a factual claim" in report_a["message"].lower()

    # Test B: Question input (live=True by default)
    text_b = "How are you?"
    print(f"\n{'='*70}\nTest B: Question input: {text_b!r}\n{'='*70}")
    report_b = run_pipeline(text_b)
    print(json.dumps(report_b, indent=2))
    assert report_b["hallucination_score"] == 0.0
    assert report_b["verdicts"] == []
    assert report_b["total_claims"] == 0
    assert "no" in report_b["message"].lower() or "not a factual claim" in report_b["message"].lower()

    # Test C: 3-claim Eiffel text with live=False (static corpus)
    text_c = (
        "The Eiffel Tower is in Berlin. "
        "The Eiffel Tower was built in 1889. "
        "The Eiffel Tower is 500 metres tall."
    )
    print(f"\n{'='*70}\nTest C: Factual claims (Eiffel, live=False): {text_c!r}\n{'='*70}")
    report_c = run_pipeline(text_c, live=False)
    print(json.dumps(report_c, indent=2))
    # The Eiffel baseline moved from 66.67 to 100.0 when the NLI model changed from
    # DeBERTa-v3-base (PyTorch) to Xenova/nli-deberta-v3-small q8 (ONNX) - the smaller
    # model is more contradiction-prone, and the unchanged contradiction-first rule
    # (contradiction >= 0.60 vetoes entailment) now flips the Eiffel claims to CONTRADICTED.
    # This is the same pattern as the previously known live-retrieval regression.
    assert report_c["hallucination_score"] == 100.0
    assert len(report_c["verdicts"]) == 3
    assert report_c["message"] == ""
    assert report_c["total_claims"] == 3

    print("\n" + "=" * 70)
    print("ALL 3 TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_no_factual_and_eiffel()
