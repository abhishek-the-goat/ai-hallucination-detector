"""
evaluate_claims.py
------------------
Evaluates the verification pipeline (with live=True) on 20 factual claims
with predefined ground-truth labels (SUPPORTED or CONTRADICTED).

Prints one line per claim with:
  claim, expected label, system label, confidence, and evidence source title.
Followed by total correct out of 20.
Also saves the output to evaluation_results.txt.
"""

import sys
import os
from pathlib import Path

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from verification.pipeline import run_pipeline

# 20 benchmark claims: 10 true facts (SUPPORTED), 10 false claims (CONTRADICTED)
CLAIMS_DATA = [
    # --- Supported Claims ---
    {
        "claim": "The Eiffel Tower is located in Paris.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "The Pacific Ocean is the largest ocean on Earth.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "Mount Everest is the highest mountain above sea level.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "Water freezes at 0 degrees Celsius under standard atmospheric pressure.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "The human skeleton has 206 bones in an adult.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "Albert Einstein developed the theory of general relativity.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "Tokyo is the capital of Japan.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "The Nile is widely considered the longest river in Africa.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "The speed of light in a vacuum is approximately 299,792 kilometers per second.",
        "expected": "SUPPORTED"
    },
    {
        "claim": "The Amazon rainforest is located in South America.",
        "expected": "SUPPORTED"
    },

    # --- Contradicted Claims ---
    {
        "claim": "The Taj Mahal is located in China.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "The Eiffel Tower is located in Berlin.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "Mount Everest is located in Australia.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "Water boils at 20 degrees Celsius at sea level.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "The Moon is larger than the Earth.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "Tokyo is the capital of France.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "The Pacific Ocean is the smallest ocean on Earth.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "Albert Einstein was the first President of the United States.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "The Nile River is located entirely in South America.",
        "expected": "CONTRADICTED"
    },
    {
        "claim": "The Great Wall of China is located in Canada.",
        "expected": "CONTRADICTED"
    },
]


def evaluate():
    output_lines = []
    header = "=" * 80
    output_lines.append(header)
    output_lines.append("AI Hallucination Detector - Pipeline Evaluation (live=True)")
    output_lines.append(header)

    correct_count = 0
    total = len(CLAIMS_DATA)

    for i, item in enumerate(CLAIMS_DATA, 1):
        claim_text = item["claim"]
        expected = item["expected"]

        report = run_pipeline(claim_text, live=True)
        verdicts = report.get("verdicts", [])

        if verdicts:
            v = verdicts[0]
            system_label = v.get("label", "UNVERIFIED")
            confidence = float(v.get("confidence", 0.0))
            evidence_list = v.get("evidence", [])
            source_title = evidence_list[0].get("source_title", "None") if evidence_list else "None"
        else:
            system_label = "UNVERIFIED"
            confidence = 0.0
            source_title = "None"

        is_correct = (system_label == expected)
        if is_correct:
            correct_count += 1

        status_mark = "PASS" if is_correct else "FAIL"

        line = (
            f"[{i:02d}/20] [{status_mark}] Claim: \"{claim_text}\" | "
            f"Expected: {expected} | System: {system_label} | "
            f"Confidence: {confidence:.2f} | Evidence Source: {source_title}"
        )
        print(line, flush=True)
        output_lines.append(line)

    summary_header = "-" * 80
    summary_line = f"Total correct: {correct_count}/{total} ({correct_count / total * 100:.1f}%)"
    print(summary_header, flush=True)
    print(summary_line, flush=True)
    output_lines.append(summary_header)
    output_lines.append(summary_line)

    out_file = REPO_ROOT / "evaluation_results.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines) + "\n")

    print(f"\nSaved evaluation output to: {out_file}", flush=True)


if __name__ == "__main__":
    evaluate()

