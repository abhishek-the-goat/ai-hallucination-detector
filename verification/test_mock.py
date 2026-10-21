from verification.pipeline import run_pipeline


def main():
    test_text = (
        "The Eiffel Tower is in Berlin. "
        "The Eiffel Tower was built in 1889. "
        "The Eiffel Tower is 500 metres tall."
    )

    print("Running verification pipeline on mock text:")
    print(f"'{test_text}'\n")

    report = run_pipeline(test_text)

    print("--- Verdicts ---")
    for v in report["verdicts"]:
        print(f"Claim ID: {v['claim_id']} | Label: {v['label']} | Confidence: {v['confidence']}")

    print("\n--- Summary ---")
    print(f"Hallucination Score: {report['hallucination_score']}")


if __name__ == "__main__":
    main()
