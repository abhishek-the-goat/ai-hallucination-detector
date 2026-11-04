"""
tests/test_sources.py
---------------------
Unit tests for external multi-source fetchers (Wikipedia, Wikidata, arXiv).

Strictly offline: all external HTTP calls and network requests are mocked
using unittest.mock.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import requests

from retrieval.sources import (
    fetch_wikipedia,
    fetch_wikidata,
    fetch_arxiv,
)


class TestWikidataFetcher(unittest.TestCase):
    """Tests for fetch_wikidata using mocked HTTP responses."""

    def test_wikidata_mocked_entity_and_claims(self):
        """Mocked entity + claims parse into evidence sentences with source='wikidata'."""
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {
            "search": [
                {
                    "id": "Q90",
                    "label": "Paris",
                    "description": "capital of France",
                }
            ]
        }

        mock_entity_resp = MagicMock()
        mock_entity_resp.status_code = 200
        mock_entity_resp.json.return_value = {
            "entities": {
                "Q90": {
                    "labels": {"en": {"value": "Paris"}},
                    "descriptions": {"en": {"value": "capital of France"}},
                    "claims": {
                        "P1376": [
                            {
                                "mainsnak": {
                                    "property": "P1376",
                                    "datavalue": {"value": "France", "type": "string"},
                                }
                            }
                        ],
                        "P1082": [
                            {
                                "mainsnak": {
                                    "property": "P1082",
                                    "datavalue": {"value": {"amount": "+2145906"}, "type": "quantity"},
                                }
                            }
                        ],
                    },
                }
            }
        }

        with patch("retrieval.sources._SESSION.get", side_effect=[mock_search_resp, mock_entity_resp]):
            results = fetch_wikidata("Paris is the capital of France", k=3)

            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)

            required_keys = {"text", "source_title", "source_url", "score", "source"}
            for ev in results:
                self.assertTrue(required_keys.issubset(ev.keys()))
                self.assertEqual(ev["source"], "wikidata")
                self.assertIn("https://www.wikidata.org/wiki/Q90", ev["source_url"])

            # Verify that description or claims became readable sentences
            all_text = " ".join(ev["text"] for ev in results)
            self.assertIn("Paris", all_text)
            self.assertIn("capital of France", all_text)

    def test_wikidata_no_entity_found_returns_empty(self):
        """When no entity matches, fetch_wikidata returns [] without error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"search": []}

        with patch("retrieval.sources._SESSION.get", return_value=mock_resp):
            results = fetch_wikidata("NonexistentUnknownEntityXYZ12345", k=3)
            self.assertEqual(results, [])

    def test_wikidata_timeout_returns_empty(self):
        """A timeout from Wikidata returns [] and does not raise."""
        with patch("retrieval.sources._SESSION.get", side_effect=requests.exceptions.Timeout("Wikidata timeout")):
            results = fetch_wikidata("Paris", k=3)
            self.assertEqual(results, [])


class TestArxivFetcher(unittest.TestCase):
    """Tests for fetch_arxiv using mocked Atom XML responses."""

    _SAMPLE_ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2101.00001v1</id>
    <title>Quantum Computing in Practice</title>
    <summary>Quantum computers provide exponential speedup for select algorithms. We demonstrate empirical verification.</summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2101.00002v1</id>
    <title>Neural Network Architectures</title>
    <summary>Deep neural networks excel at perceptual tasks. Benchmark results are provided.</summary>
  </entry>
</feed>
"""

    def test_arxiv_mocked_atom_feed_parses_evidence(self):
        """Mocked Atom feed parses into evidence with source='arxiv'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = self._SAMPLE_ATOM_FEED

        with patch("retrieval.sources._SESSION.get", return_value=mock_resp):
            results = fetch_arxiv("quantum computing algorithms", k=2)

            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 2)

            required_keys = {"text", "source_title", "source_url", "score", "source"}
            for ev in results:
                self.assertTrue(required_keys.issubset(ev.keys()))
                self.assertEqual(ev["source"], "arxiv")
                self.assertTrue(ev["source_url"].startswith("http://arxiv.org/abs/"))

            # Check that title + summary first sentence was extracted
            first = results[0]
            self.assertIn("Quantum Computing in Practice", first["text"])
            self.assertIn("Quantum computers provide exponential speedup for select algorithms.", first["text"])

    def test_arxiv_no_papers_found_returns_empty(self):
        """When arXiv returns a feed with no entries, returns [] without error."""
        empty_feed = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>
"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = empty_feed

        with patch("retrieval.sources._SESSION.get", return_value=mock_resp):
            results = fetch_arxiv("unmatched query", k=3)
            self.assertEqual(results, [])

    def test_arxiv_timeout_returns_empty(self):
        """A timeout from arXiv returns [] and does not raise."""
        with patch("retrieval.sources._SESSION.get", side_effect=requests.exceptions.Timeout("arXiv timeout")):
            results = fetch_arxiv("quantum computing", k=3)
            self.assertEqual(results, [])


class TestWikipediaFetcher(unittest.TestCase):
    """Tests for fetch_wikipedia wrapping existing live Wikipedia retrieval."""

    def test_wikipedia_calls_existing_live_search(self):
        """fetch_wikipedia calls retrieve_live_evidence and adds source='wikipedia'."""
        canned_evidence = [
            {
                "text": "The Eiffel Tower is in Paris.",
                "source_title": "Eiffel Tower - Wikipedia",
                "source_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
                "score": 0.95,
            }
        ]

        with patch("retrieval.live_search.retrieve_live_evidence", return_value=canned_evidence):
            results = fetch_wikipedia("Eiffel Tower", k=2)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["source"], "wikipedia")
            self.assertEqual(results[0]["text"], canned_evidence[0]["text"])

    def test_wikipedia_timeout_returns_empty(self):
        """When live Wikipedia raises an exception, returns [] without raising."""
        with patch("retrieval.live_search.retrieve_live_evidence", side_effect=Exception("Connection timed out")):
            results = fetch_wikipedia("Eiffel Tower", k=2)
            self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
