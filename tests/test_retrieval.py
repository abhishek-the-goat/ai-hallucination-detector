"""
tests/test_retrieval.py
-----------------------
Unit tests for the retrieval module.

Design principles
-----------------
- All tests run OFFLINE: no network calls, no model downloads.
- BM25Index and VectorIndex are tested with real (but lightweight) logic
  using tiny in-memory corpora — no model loading for BM25 tests.
- VectorIndex-dependent tests mock SentenceTransformer and FAISS so the
  test suite runs fast and deterministically in CI.
- retrieve_evidence() is tested through its dependency-injection parameters
  (_bm25, _vector, _documents) to avoid touching the singleton state.
- A separate section marks which tests require real installed packages.
"""

from __future__ import annotations

import sys
import os
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure the repo root is on sys.path (mirrors CI setup in test_claim_extractor)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from retrieval.corpus import (
    Document,
    _split_into_passages,
    load_corpus,
    save_corpus,
    CORPUS_PATH,
)
from retrieval.search import (
    _normalise_bm25_scores,
    _merge_results,
    _doc_to_evidence,
    retrieve_evidence,
    BM25_WEIGHT,
    VECTOR_WEIGHT,
)
from retrieval.index import BM25Index, reset_indexes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(idx: int, text: str = "some text", url_suffix: str = "") -> Document:
    return Document(
        id=f"test:{idx}",
        text=text,
        source_title=f"Source {idx}",
        source_url=f"https://example.com/{idx}{url_suffix}",
    )


_EIFFEL_DOC = Document(
    id="wiki:Eiffel_Tower:0",
    text=(
        "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars "
        "in Paris, France. It was designed by Gustave Eiffel, whose company built "
        "it from 1887 to 1889 as the centerpiece of the 1889 World's Fair. "
        "The tower is 330 metres tall and was the world's tallest man-made structure "
        "for 41 years until the Chrysler Building was completed in 1930."
    ),
    source_title="Eiffel Tower - Wikipedia",
    source_url="https://en.wikipedia.org/wiki/Eiffel_Tower",
)

_EINSTEIN_DOC = Document(
    id="wiki:Albert_Einstein:0",
    text=(
        "Albert Einstein was a German-born theoretical physicist who is widely held "
        "to be one of the greatest and most influential scientists of all time. "
        "He developed the theory of relativity, and made important contributions to "
        "quantum mechanics. He received the Nobel Prize in Physics in 1921 for his "
        "discovery of the law of the photoelectric effect."
    ),
    source_title="Albert Einstein - Wikipedia",
    source_url="https://en.wikipedia.org/wiki/Albert_Einstein",
)

_MOON_DOC = Document(
    id="wiki:Moon:0",
    text=(
        "The Moon is Earth's only natural satellite. It is the fifth largest satellite "
        "in the Solar System and is larger relative to Earth than any other natural "
        "satellite of a planet. The Moon orbits Earth at an average distance of 384,400 km. "
        "Neil Armstrong and Buzz Aldrin became the first humans to walk on the Moon during "
        "the Apollo 11 mission in July 1969."
    ),
    source_title="Moon - Wikipedia",
    source_url="https://en.wikipedia.org/wiki/Moon",
)

_MINI_CORPUS = [_EIFFEL_DOC, _EINSTEIN_DOC, _MOON_DOC]


# ===========================================================================
# 1. Corpus — Document structure and passage splitting
# ===========================================================================

class TestDocumentStructure(unittest.TestCase):
    """The Document dataclass must carry the four required fields."""

    def test_fields_present(self):
        doc = _make_doc(1, text="Hello world")
        self.assertIsInstance(doc.id, str)
        self.assertIsInstance(doc.text, str)
        self.assertIsInstance(doc.source_title, str)
        self.assertIsInstance(doc.source_url, str)

    def test_fields_match_constructor(self):
        doc = _make_doc(42, text="Test passage")
        self.assertEqual(doc.id, "test:42")
        self.assertEqual(doc.text, "Test passage")
        self.assertEqual(doc.source_title, "Source 42")
        self.assertEqual(doc.source_url, "https://example.com/42")


class TestPassageSplitting(unittest.TestCase):
    """_split_into_passages must produce sensible Document lists."""

    def _long_text(self, n_words: int) -> str:
        return " ".join(["word"] * n_words)

    def test_empty_text_returns_empty_list(self):
        result = _split_into_passages("", "Title", "http://example.com", "key")
        self.assertEqual(result, [])

    def test_blank_text_returns_empty_list(self):
        result = _split_into_passages("   ", "Title", "http://example.com", "key")
        self.assertEqual(result, [])

    def test_short_text_is_single_passage(self):
        text = "The Eiffel Tower is in Paris. It was built in 1889."
        docs = _split_into_passages(text, "T", "http://x.com", "k")
        self.assertEqual(len(docs), 1)
        self.assertIn("Eiffel", docs[0].text)

    def test_long_text_splits_into_multiple_passages(self):
        # 600 words should produce at least 2 passages
        text = self._long_text(600)
        # Make it look like sentences
        sentences = ". ".join(["A group of words that form a longer sentence here"] * 40)
        docs = _split_into_passages(sentences, "T", "http://x.com", "k")
        self.assertGreaterEqual(len(docs), 2)

    def test_passage_ids_are_sequential(self):
        sentences = ". ".join(["This is a sentence with many words for testing"] * 60)
        docs = _split_into_passages(sentences, "T", "http://x.com", "mykey")
        for i, doc in enumerate(docs):
            self.assertEqual(doc.id, f"mykey:{i}")

    def test_source_propagated_to_all_passages(self):
        sentences = ". ".join(["This is a sentence with many words for testing"] * 60)
        docs = _split_into_passages(sentences, "My Title", "http://my.url", "k")
        for doc in docs:
            self.assertEqual(doc.source_title, "My Title")
            self.assertEqual(doc.source_url, "http://my.url")

    def test_no_passage_has_empty_text(self):
        sentences = ". ".join(["This is a sentence with many words for testing"] * 80)
        docs = _split_into_passages(sentences, "T", "http://x.com", "k")
        for doc in docs:
            self.assertTrue(doc.text.strip(), "Passage text must not be empty")


# ===========================================================================
# 2. Corpus — load_corpus / save_corpus
# ===========================================================================

class TestCorpusPersistence(unittest.TestCase):
    """load_corpus / save_corpus roundtrip and error handling."""

    def test_save_and_reload_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.json"
            save_corpus(_MINI_CORPUS, path=path)
            loaded = load_corpus(path=path)
        self.assertEqual(len(loaded), 3)
        ids = {d.id for d in loaded}
        self.assertIn("wiki:Eiffel_Tower:0", ids)
        self.assertIn("wiki:Albert_Einstein:0", ids)

    def test_roundtrip_preserves_all_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.json"
            save_corpus([_EIFFEL_DOC], path=path)
            loaded = load_corpus(path=path)
        doc = loaded[0]
        self.assertEqual(doc.text, _EIFFEL_DOC.text)
        self.assertEqual(doc.source_title, _EIFFEL_DOC.source_title)
        self.assertEqual(doc.source_url, _EIFFEL_DOC.source_url)

    def test_missing_file_returns_empty_list(self):
        path = Path("/nonexistent/path/corpus.json")
        result = load_corpus(path=path)
        self.assertEqual(result, [])

    def test_empty_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.json"
            path.write_text("", encoding="utf-8")
            result = load_corpus(path=path)
        self.assertEqual(result, [])

    def test_invalid_json_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.json"
            path.write_text("{not valid json[[[", encoding="utf-8")
            result = load_corpus(path=path)
        self.assertEqual(result, [])

    def test_records_missing_fields_are_skipped(self):
        bad_record = {"id": "x:0", "text": "some text"}  # missing source_title, source_url
        good_record = {
            "id": "y:0",
            "text": "valid text",
            "source_title": "Good Source",
            "source_url": "http://good.com",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.json"
            path.write_text(json.dumps([bad_record, good_record]), encoding="utf-8")
            result = load_corpus(path=path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "y:0")

    def test_empty_text_records_are_skipped(self):
        empty_text_record = {
            "id": "z:0",
            "text": "   ",
            "source_title": "T",
            "source_url": "http://x.com",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.json"
            path.write_text(json.dumps([empty_text_record]), encoding="utf-8")
            result = load_corpus(path=path)
        self.assertEqual(result, [])

    def test_save_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "corpus.json"
            save_corpus([_EIFFEL_DOC], path=path)
            self.assertTrue(path.exists())


# ===========================================================================
# 3. BM25Index — keyword search (no model, CI-safe)
# ===========================================================================

class TestBM25Index(unittest.TestCase):
    """BM25Index must return relevant keyword matches."""

    def setUp(self):
        self.index = BM25Index(_MINI_CORPUS)

    def test_rejects_empty_corpus(self):
        with self.assertRaises(ValueError):
            BM25Index([])

    def test_returns_list_of_tuples(self):
        results = self.index.search("Eiffel Tower Paris", k=3)
        self.assertIsInstance(results, list)
        for score, doc in results:
            self.assertIsInstance(score, float)
            self.assertIsInstance(doc, Document)

    def test_eiffel_query_ranks_eiffel_doc_first(self):
        results = self.index.search("Eiffel Tower Paris France", k=3)
        self.assertTrue(len(results) > 0)
        top_doc = results[0][1]
        self.assertEqual(top_doc.id, "wiki:Eiffel_Tower:0")

    def test_einstein_query_ranks_einstein_doc_first(self):
        results = self.index.search("Albert Einstein Nobel Prize physics", k=3)
        self.assertTrue(len(results) > 0)
        top_doc = results[0][1]
        self.assertEqual(top_doc.id, "wiki:Albert_Einstein:0")

    def test_moon_query_ranks_moon_doc_first(self):
        results = self.index.search("Moon Apollo Neil Armstrong lunar", k=3)
        self.assertTrue(len(results) > 0)
        top_doc = results[0][1]
        self.assertEqual(top_doc.id, "wiki:Moon:0")

    def test_k_limits_results(self):
        results = self.index.search("the and is", k=2)
        self.assertLessEqual(len(results), 2)

    def test_k_1_returns_at_most_one(self):
        results = self.index.search("Paris France", k=1)
        self.assertLessEqual(len(results), 1)

    def test_blank_query_returns_empty_list(self):
        self.assertEqual(self.index.search("", k=5), [])
        self.assertEqual(self.index.search("   ", k=5), [])

    def test_scores_sorted_descending(self):
        results = self.index.search("Eiffel Tower", k=3)
        scores = [s for s, _ in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


# ===========================================================================
# 4. Score normalisation and merging (pure logic, no dependencies)
# ===========================================================================

class TestScoreNormalisation(unittest.TestCase):
    """_normalise_bm25_scores must return scores in [0, 1]."""

    def test_empty_list_returns_empty_dict(self):
        self.assertEqual(_normalise_bm25_scores([]), {})

    def test_max_score_maps_to_one(self):
        docs = [_make_doc(i) for i in range(3)]
        results = [(3.0, docs[0]), (1.5, docs[1]), (0.5, docs[2])]
        normed = _normalise_bm25_scores(results)
        self.assertAlmostEqual(normed[docs[0].id], 1.0)

    def test_all_zero_scores_stay_zero(self):
        docs = [_make_doc(i) for i in range(2)]
        results = [(0.0, docs[0]), (0.0, docs[1])]
        normed = _normalise_bm25_scores(results)
        for v in normed.values():
            self.assertEqual(v, 0.0)

    def test_scores_in_unit_interval(self):
        docs = [_make_doc(i) for i in range(4)]
        results = [(10.0, docs[0]), (7.5, docs[1]), (2.1, docs[2]), (0.0, docs[3])]
        normed = _normalise_bm25_scores(results)
        for v in normed.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)


class TestMergeResults(unittest.TestCase):
    """_merge_results must deduplicate and combine scores correctly."""

    def test_deduplication_same_doc_in_both_sets(self):
        doc = _make_doc(1, text="duplicate document about paris eiffel")
        bm25 = [(5.0, doc)]
        vector = [(0.8, doc)]
        merged = _merge_results(bm25, vector)
        ids = [d.id for _, d in merged]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate doc must appear only once")

    def test_combined_score_formula(self):
        doc_a = _make_doc(1, text="one")
        doc_b = _make_doc(2, text="two")
        bm25_results = [(10.0, doc_a), (0.0, doc_b)]
        vector_results = [(0.9, doc_a), (0.1, doc_b)]
        merged = _merge_results(bm25_results, vector_results)
        merged_dict = {d.id: s for s, d in merged}

        # doc_a: BM25_norm=1.0, cosine=0.9
        expected_a = BM25_WEIGHT * 1.0 + VECTOR_WEIGHT * 0.9
        self.assertAlmostEqual(merged_dict[doc_a.id], expected_a, places=6)

    def test_doc_only_in_bm25_has_zero_vector_score(self):
        doc_a = _make_doc(1, text="keyword only doc")
        doc_b = _make_doc(2, text="vector only doc")
        bm25_results = [(5.0, doc_a)]
        vector_results = [(0.8, doc_b)]
        merged = _merge_results(bm25_results, vector_results)
        merged_dict = {d.id: s for s, d in merged}
        # doc_a gets BM25_WEIGHT*1.0 + VECTOR_WEIGHT*0.0
        expected_a = BM25_WEIGHT * 1.0
        self.assertAlmostEqual(merged_dict[doc_a.id], expected_a, places=6)

    def test_sorted_descending(self):
        docs = [_make_doc(i) for i in range(3)]
        bm25_results = [(3.0, docs[0]), (2.0, docs[1]), (1.0, docs[2])]
        vector_results = [(0.9, docs[0]), (0.4, docs[1]), (0.1, docs[2])]
        merged = _merge_results(bm25_results, vector_results)
        scores = [s for s, _ in merged]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_both_empty_returns_empty(self):
        self.assertEqual(_merge_results([], []), [])


# ===========================================================================
# 5. Evidence dict contract
# ===========================================================================

class TestEvidenceContract(unittest.TestCase):
    """Every Evidence dict must satisfy the four-key contract."""

    def _build_evidence_via_mock_indexes(self) -> list[dict]:
        """Run retrieve_evidence against real BM25 + mocked VectorIndex."""
        # Build real BM25 index
        bm25 = BM25Index(_MINI_CORPUS)

        # Mock VectorIndex: returns canned cosine scores
        mock_vector = MagicMock()
        mock_vector.search.return_value = [
            (0.95, _EIFFEL_DOC),
            (0.4, _EINSTEIN_DOC),
        ]

        return retrieve_evidence(
            "The Eiffel Tower is located in Paris France",
            k=3,
            _bm25=bm25,
            _vector=mock_vector,
        )

    def test_returns_list(self):
        evidence = self._build_evidence_via_mock_indexes()
        self.assertIsInstance(evidence, list)

    def test_each_item_is_dict(self):
        for ev in self._build_evidence_via_mock_indexes():
            self.assertIsInstance(ev, dict)

    def test_required_keys_present(self):
        required = {"text", "source_title", "source_url", "score"}
        for ev in self._build_evidence_via_mock_indexes():
            self.assertEqual(required, required & ev.keys(),
                             f"Missing keys in: {ev.keys()}")

    def test_text_is_nonempty_string(self):
        for ev in self._build_evidence_via_mock_indexes():
            self.assertIsInstance(ev["text"], str)
            self.assertTrue(ev["text"].strip())

    def test_source_title_is_string(self):
        for ev in self._build_evidence_via_mock_indexes():
            self.assertIsInstance(ev["source_title"], str)

    def test_source_url_is_string(self):
        for ev in self._build_evidence_via_mock_indexes():
            self.assertIsInstance(ev["source_url"], str)

    def test_score_is_float(self):
        for ev in self._build_evidence_via_mock_indexes():
            self.assertIsInstance(ev["score"], float)

    def test_score_in_unit_interval(self):
        for ev in self._build_evidence_via_mock_indexes():
            self.assertGreaterEqual(ev["score"], 0.0)
            self.assertLessEqual(ev["score"], 1.0)


# ===========================================================================
# 6. retrieve_evidence — functional behaviour
# ===========================================================================

class TestRetrieveEvidenceFunctional(unittest.TestCase):
    """Functional tests using real BM25 + mocked VectorIndex."""

    def _make_mock_vector(self, results: list[tuple[float, Document]]) -> MagicMock:
        mv = MagicMock()
        mv.search.return_value = results
        return mv

    def test_eiffel_claim_returns_eiffel_as_top_result(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = self._make_mock_vector([(0.95, _EIFFEL_DOC), (0.3, _MOON_DOC)])
        results = retrieve_evidence(
            "The Eiffel Tower was built in Paris in 1889",
            k=5,
            _bm25=bm25,
            _vector=mock_v,
        )
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["source_title"], "Eiffel Tower - Wikipedia")

    def test_einstein_claim_returns_einstein_doc(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = self._make_mock_vector([(0.9, _EINSTEIN_DOC)])
        results = retrieve_evidence(
            "Albert Einstein won the Nobel Prize in Physics",
            k=5,
            _bm25=bm25,
            _vector=mock_v,
        )
        titles = [ev["source_title"] for ev in results]
        self.assertIn("Albert Einstein - Wikipedia", titles)

    def test_k_limits_results(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = self._make_mock_vector([(0.8, _EIFFEL_DOC), (0.5, _EINSTEIN_DOC)])
        results = retrieve_evidence("some claim", k=1, _bm25=bm25, _vector=mock_v)
        self.assertLessEqual(len(results), 1)

    def test_k_equals_corpus_size_returns_all(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = self._make_mock_vector([
            (0.9, _EIFFEL_DOC),
            (0.6, _EINSTEIN_DOC),
            (0.4, _MOON_DOC),
        ])
        results = retrieve_evidence("some claim", k=100, _bm25=bm25, _vector=mock_v)
        # At most as many results as docs in corpus
        self.assertLessEqual(len(results), len(_MINI_CORPUS))

    def test_results_sorted_by_score_descending(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = self._make_mock_vector([
            (0.9, _EIFFEL_DOC),
            (0.5, _EINSTEIN_DOC),
            (0.2, _MOON_DOC),
        ])
        results = retrieve_evidence("Eiffel Tower Paris", k=3, _bm25=bm25, _vector=mock_v)
        scores = [ev["score"] for ev in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_no_duplicate_docs_in_results(self):
        bm25 = BM25Index(_MINI_CORPUS)
        # Return same doc from both indexes
        mock_v = self._make_mock_vector([(0.95, _EIFFEL_DOC), (0.5, _EIFFEL_DOC)])
        results = retrieve_evidence("Eiffel", k=5, _bm25=bm25, _vector=mock_v)
        urls = [ev["source_url"] for ev in results]
        self.assertEqual(len(urls), len(set(urls)),
                         "Duplicate documents must be deduplicated")

    def test_blank_claim_returns_empty_list(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = self._make_mock_vector([])
        self.assertEqual(retrieve_evidence("", k=5, _bm25=bm25, _vector=mock_v), [])
        self.assertEqual(retrieve_evidence("   ", k=5, _bm25=bm25, _vector=mock_v), [])

    def test_real_source_urls_not_fabricated(self):
        """All source URLs must come from the corpus — no invented links."""
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = self._make_mock_vector([
            (0.9, _EIFFEL_DOC),
            (0.7, _EINSTEIN_DOC),
        ])
        results = retrieve_evidence("any claim", k=5, _bm25=bm25, _vector=mock_v)
        valid_urls = {d.source_url for d in _MINI_CORPUS}
        for ev in results:
            self.assertIn(ev["source_url"], valid_urls,
                          f"Fabricated URL found: {ev['source_url']}")


# ===========================================================================
# 7. Empty corpus and edge cases
# ===========================================================================

class TestEdgeCases(unittest.TestCase):
    """Edge cases: empty corpus, invalid k, etc."""

    def test_empty_corpus_returns_empty_list(self):
        """retrieve_evidence must return [] (not raise) for an empty corpus."""
        # reset_indexes so we get a fresh state, then inject empty docs
        reset_indexes()
        result = retrieve_evidence("any claim", k=5, _documents=[])
        self.assertEqual(result, [])

    def test_k_zero_treated_as_one(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = MagicMock()
        mock_v.search.return_value = [(0.8, _EIFFEL_DOC)]
        results = retrieve_evidence("Eiffel", k=0, _bm25=bm25, _vector=mock_v)
        self.assertLessEqual(len(results), 1)

    def test_negative_k_treated_as_one(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = MagicMock()
        mock_v.search.return_value = [(0.8, _EIFFEL_DOC)]
        results = retrieve_evidence("Eiffel", k=-3, _bm25=bm25, _vector=mock_v)
        self.assertLessEqual(len(results), 1)

    def test_bm25_rejects_empty_corpus(self):
        with self.assertRaises(ValueError):
            BM25Index([])

    def test_doc_to_evidence_contract(self):
        doc = _EIFFEL_DOC
        ev = _doc_to_evidence(doc, 0.75)
        self.assertEqual(ev["text"], doc.text)
        self.assertEqual(ev["source_title"], doc.source_title)
        self.assertEqual(ev["source_url"], doc.source_url)
        self.assertAlmostEqual(ev["score"], 0.75, places=5)
        self.assertIsInstance(ev["score"], float)


# ===========================================================================
# 8. VectorIndex — mocked (no model download, CI-safe)
# ===========================================================================

class TestVectorIndexMocked(unittest.TestCase):
    """
    Test VectorIndex behaviour with SentenceTransformer and faiss mocked out.

    These tests verify the internal logic of VectorIndex (normalisation,
    FAISS search calls, result assembly) without downloading any model.
    """

    def _make_vector_index(self, docs: list[Document]) -> "VectorIndex":
        """Build a VectorIndex with mocked SentenceTransformer and faiss."""
        import numpy as np
        from retrieval.index import VectorIndex

        dim = 8  # small fake embedding dimension
        n = len(docs)
        # Fixed deterministic embeddings — each doc gets a unit vector
        embeddings = np.eye(n, dim, dtype=np.float32)

        mock_model = MagicMock()
        # encode() for corpus passages
        mock_model.encode.side_effect = lambda texts, **kw: (
            embeddings[:len(texts)] if isinstance(texts, list) else embeddings[0:1]
        )

        mock_index = MagicMock()
        # Simulate FAISS returning the first doc as the best match
        mock_index.ntotal = n
        mock_index.search.return_value = (
            np.array([[1.0, 0.9, 0.1]], dtype=np.float32),  # distances
            np.array([[0, 1, 2]], dtype=np.int64),           # indices
        )

        mock_faiss = MagicMock()
        mock_faiss.IndexFlatIP.return_value = mock_index

        mock_st = MagicMock()
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict(sys.modules, {"faiss": mock_faiss, "sentence_transformers": mock_st}):
            vi = VectorIndex(docs)

        return vi

    def test_rejects_empty_corpus(self):
        from retrieval.index import VectorIndex
        with patch.dict(sys.modules, {"sentence_transformers": MagicMock(), "faiss": MagicMock()}):
            with self.assertRaises(ValueError):
                VectorIndex([])

    def test_search_returns_tuples(self):
        vi = self._make_vector_index(_MINI_CORPUS)
        results = vi.search("some query", k=3)
        self.assertIsInstance(results, list)
        for score, doc in results:
            self.assertIsInstance(score, float)
            self.assertIsInstance(doc, Document)

    def test_scores_clipped_to_unit_interval(self):
        vi = self._make_vector_index(_MINI_CORPUS)
        results = vi.search("query", k=3)
        for score, _ in results:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_blank_query_returns_empty(self):
        vi = self._make_vector_index(_MINI_CORPUS)
        self.assertEqual(vi.search("", k=5), [])
        self.assertEqual(vi.search("   ", k=5), [])

    def test_sorted_descending(self):
        vi = self._make_vector_index(_MINI_CORPUS)
        results = vi.search("query", k=3)
        scores = [s for s, _ in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


# ===========================================================================
# Entry point
# ===========================================================================

# ===========================================================================
# 8. Live Wikipedia Search & Fallback
# ===========================================================================

class TestLiveSearchRetrieval(unittest.TestCase):
    """Tests for live Wikipedia retrieval and fallback mechanisms."""

    def test_split_into_passages(self):
        from retrieval.live_search import split_into_passages
        text = (
            "Sentence one is here. Sentence two is here. Sentence three is here. "
            "Sentence four is here. Sentence five is here. Sentence six is here."
        )
        passages = split_into_passages(text, min_sents=3, max_sents=5)
        self.assertTrue(len(passages) >= 1)
        self.assertIn("Sentence one is here.", passages[0])

    def test_split_into_passages_blank(self):
        from retrieval.live_search import split_into_passages
        self.assertEqual(split_into_passages(""), [])
        self.assertEqual(split_into_passages("   "), [])

    def test_live_true_returns_live_evidence(self):
        mock_evidence = [
            {
                "text": "The Taj Mahal is in Agra.",
                "source_title": "Taj Mahal - Wikipedia",
                "source_url": "https://en.wikipedia.org/wiki/Taj_Mahal",
                "score": 0.85,
                "raw_similarity": 0.85,
                "cosine_similarity": 0.85,
            }
        ]
        with patch("retrieval.live_search.retrieve_live_evidence", return_value=mock_evidence):
            res = retrieve_evidence("Taj Mahal claim", live=True)
            self.assertEqual(res, mock_evidence)

    def test_live_true_falls_back_on_exception(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = MagicMock()
        mock_v.search.return_value = [(0.9, _EIFFEL_DOC)]
        with patch("retrieval.live_search.retrieve_live_evidence", side_effect=Exception("Timeout")):
            res = retrieve_evidence(
                "Eiffel Tower",
                live=True,
                _bm25=bm25,
                _vector=mock_v,
            )
            self.assertTrue(len(res) > 0)
            self.assertEqual(res[0]["source_title"], "Eiffel Tower - Wikipedia")

    def test_live_true_falls_back_on_empty_results(self):
        bm25 = BM25Index(_MINI_CORPUS)
        mock_v = MagicMock()
        mock_v.search.return_value = [(0.9, _EIFFEL_DOC)]
        with patch("retrieval.live_search.retrieve_live_evidence", return_value=[]):
            res = retrieve_evidence(
                "Eiffel Tower",
                live=True,
                _bm25=bm25,
                _vector=mock_v,
            )
            self.assertTrue(len(res) > 0)
            self.assertEqual(res[0]["source_title"], "Eiffel Tower - Wikipedia")


if __name__ == "__main__":
    unittest.main(verbosity=2)
