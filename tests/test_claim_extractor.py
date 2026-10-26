"""
Unit tests for the Claim Extractor module (Pratham's role).
Tests sentence splitting, compound clause separation, non-claim filtering,
decontextualization, and adherence to the shared contract schema.
"""

import os
import sys

# Add repository root to sys.path so modules can be imported in CI
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from claim_extractor.extractor import extract_claims
from claim_extractor.filters import (
    is_valid_factual_claim,
    is_question,
    is_greeting_or_filler,
    is_recommendation,
    strip_opinion_prefix
)


class TestFilters(unittest.TestCase):
    def test_questions_filtered(self):
        self.assertTrue(is_question("What is the capital of France?"))
        self.assertTrue(is_question("Did you know that water boils at 100 degrees Celsius?"))
        self.assertFalse(is_question("Paris is the capital of France."))

    def test_greetings_and_fillers_filtered(self):
        self.assertTrue(is_greeting_or_filler("Hello!"))
        self.assertTrue(is_greeting_or_filler("Sure, here is the answer to your question:"))
        self.assertTrue(is_greeting_or_filler("Hope this helps!"))
        self.assertFalse(is_greeting_or_filler("The Apollo 11 mission landed on the Moon in July 1969."))

    def test_recommendations_filtered(self):
        self.assertTrue(is_recommendation("You should always wear a seatbelt."))
        self.assertTrue(is_recommendation("Make sure to drink plenty of water."))
        self.assertFalse(is_recommendation("Water is composed of hydrogen and oxygen."))

    def test_strip_opinion_prefix(self):
        cleaned, stripped = strip_opinion_prefix("I think Barack Obama was born in 1961.")
        self.assertTrue(stripped)
        self.assertEqual(cleaned, "Barack Obama was born in 1961.")

        cleaned2, stripped2 = strip_opinion_prefix("In my opinion, Python is widely used in data science.")
        self.assertTrue(stripped2)
        self.assertEqual(cleaned2, "Python is widely used in data science.")


class TestClaimExtractor(unittest.TestCase):
    def test_contract_schema(self):
        """Verify the output strictly satisfies the Claim = {claim_id: int, text: str} schema."""
        sample_text = "The Eiffel Tower is located in Paris. It was completed in 1889."
        claims = extract_claims(sample_text)
        self.assertIsInstance(claims, list)
        self.assertGreater(len(claims), 0)
        for c in claims:
            self.assertIn("claim_id", c)
            self.assertIn("text", c)
            self.assertIsInstance(c["claim_id"], int)
            self.assertIsInstance(c["text"], str)

    def test_decontextualization_of_pronouns(self):
        """Verify that pronouns like 'He' are replaced by the preceding named entity."""
        sample_text = "Barack Obama was elected in 2008. He was born in 1961."
        claims = extract_claims(sample_text)
        self.assertEqual(len(claims), 2)
        self.assertIn("Barack Obama was born in 1961.", claims[1]["text"])

    def test_done_definition_5_sentence_mixed_input(self):
        """
        Verify the PDF 'Done means':
        A 5-sentence answer comes out as clean, standalone factual claims,
        one fact each, with opinions and questions filtered out.
        """
        answer_text = (
            "Hello there! "
            "Albert Einstein won the Nobel Prize in Physics in 1921. "
            "He later moved to the United States in 1933. "
            "I think physics is the most exciting subject in the world. "
            "Have you ever studied quantum mechanics?"
        )
        claims = extract_claims(answer_text)
        
        # Greetings, subjective opinions, and questions must be excluded
        claim_texts = [c["text"] for c in claims]
        
        # Check that questions and greetings are absent
        for text in claim_texts:
            self.assertFalse("Hello" in text)
            self.assertFalse("quantum mechanics?" in text)
            self.assertFalse("most exciting subject" in text)

        # Factual claims must be present and decontextualized
        self.assertTrue(any("Albert Einstein won the Nobel Prize" in t for t in claim_texts))
        self.assertTrue(any("Albert Einstein" in t and "1933" in t for t in claim_texts))

    def test_compound_sentence_splitting(self):
        """Verify compound sentences joined by conjunctions split into atomic facts."""
        text = "Neil Armstrong landed on the Moon in 1969, and he took the first lunar steps."
        claims = extract_claims(text)
        self.assertGreaterEqual(len(claims), 2)
        self.assertEqual(claims[0]["claim_id"], 1)
        self.assertEqual(claims[1]["claim_id"], 2)


if __name__ == "__main__":
    unittest.main()
