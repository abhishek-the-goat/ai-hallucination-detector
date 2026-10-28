# Hallucination Detector — updated UI

## What's new
- **Signal Scan quick-check dock:** custom floating launcher, ready-state indicator, live character counter, sample text shortcut, and a clearer scan action.
- **Evidence-first homepage:** refreshed headline and three-step explanation of claim extraction, evidence review, and the report fingerprint.
- **Hallucination fingerprint:** each report now shows evidence coverage, contradiction rate, a plain-language profile, and a suggested next review step.
- **Transparency note:** fingerprint metrics describe the report returned by the pipeline; they are not a guarantee that a claim is true or false.
- **Custom neon cursor and pointer glow** on fine-pointer devices, with click ripples and reduced-motion support.
- **Dark/light theme switcher** that remembers the chosen theme in the browser.
- **Interactive report gauge and evidence network** linking claim nodes to returned evidence sources.
- **Evidence inspector** with safe source links, relevance indicators, and copy-claim action.
- **History dashboard** with search, signal filters, sorting, summary statistics, and individual report deletion.
- **Accessible interaction details** including keyboard-operable graph nodes, responsive layouts, and print styles.

## Run locally
1. Install Python 3.10+.
2. In this folder, run `python -m pip install -r requirements.txt`.
3. Run `python app.py`.
4. Open the local address printed by Flask (normally `http://127.0.0.1:5000`).

The app creates `history.db` automatically. The `verification.pipeline` module is not included in this source bundle. If it is unavailable, the demo fallback is used and the page explicitly labels its results as illustrative; no real claim verification is performed in demo mode. For real claim verification, add your actual verification pipeline to `verification/pipeline.py`. The UI cannot create a reliable fact-checking engine without that backend and its evidence-retrieval logic.
