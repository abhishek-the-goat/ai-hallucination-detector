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
from claim_extractor.extractor import extract_claims, analyze_claims
from claim_extractor.filters import (
    is_valid_factual_claim,
    is_question,
    is_greeting_or_filler,
    is_recommendation,
    is_emotion,
    is_self_referential,
    is_single_word,
    is_random_or_gibberish,
    has_assertion_predicate,
    strip_opinion_prefix,
    classify_statement
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

    def test_emotions_and_self_referential_filtered(self):
        self.assertTrue(is_emotion("I feel so sad and anxious today."))
        self.assertTrue(is_emotion("I hate this situation so much."))
        self.assertFalse(is_emotion("The Pacific Ocean is the largest ocean."))

        self.assertTrue(is_self_referential("Who am I and what is my purpose?"))
        self.assertTrue(is_self_referential("Are you an AI?"))
        self.assertTrue(is_self_referential("Tell me about yourself."))
        self.assertFalse(is_self_referential("Mount Everest is the highest mountain above sea level."))

    def test_single_word_invalid(self):
        """Single words are invalid and cannot be factual claims."""
        self.assertTrue(is_single_word("Paris"))
        self.assertTrue(is_single_word("Apple"))
        self.assertTrue(is_single_word("hello!"))
        self.assertFalse(is_single_word("Ice melts."))
        
        # Verify classification and validity
        res = classify_statement("Apple")
        self.assertEqual(res["category"], "INVALID")
        self.assertIn("Invalid input", res["message"])
        self.assertFalse(is_valid_factual_claim("Apple"))

    def test_random_gibberish_invalid(self):
        """Random characters, keyboard smashing, and verbless words are invalid."""
        self.assertTrue(is_random_or_gibberish("asdfghjkl"))
        self.assertTrue(is_random_or_gibberish("12345678"))
        self.assertTrue(is_random_or_gibberish("qwertyuiop"))
        self.assertTrue(is_random_or_gibberish("... !!! ???"))
        self.assertFalse(is_random_or_gibberish("Water boils at 100 degrees Celsius."))

        # Random verbless words
        self.assertFalse(has_assertion_predicate("table potato chair window"))
        self.assertFalse(is_valid_factual_claim("table potato chair window"))

        # Verify classification
        res = classify_statement("asdfghjkl")
        self.assertEqual(res["category"], "INVALID")
        self.assertIn("Invalid input", res["message"])

    def test_no_min_word_limit_valid_short_claims(self):
        """Short 2-word assertions with subject and verb are valid (no 3-word minimum)."""
        self.assertTrue(is_valid_factual_claim("Ice melts."))
        self.assertTrue(is_valid_factual_claim("Birds fly."))
        self.assertTrue(is_valid_factual_claim("Fish swim."))
        
        claims = extract_claims("Ice melts.")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["text"], "Ice melts.")


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

    def test_analyze_claims_no_facts_detected(self):
        """Verify that questions and emotions trigger clear diagnostic messages."""
        text = "I feel very sad today. Who am I and why are you here?"
        analysis = analyze_claims(text)
        self.assertFalse(analysis["has_factual_claims"])
        self.assertEqual(analysis["total_claims"], 0)
        self.assertIn("not a factual claim", analysis["status_message"].lower())
        self.assertIn("emotions", analysis["status_message"].lower())
        self.assertIn("questions", analysis["status_message"].lower())

    def test_analyze_claims_with_factual_claims(self):
        """Verify that factual claims are recognized and separated from personal feelings."""
        text = "The Moon orbits the Earth every 27.3 days. I love looking at the stars."
        analysis = analyze_claims(text)
        self.assertTrue(analysis["has_factual_claims"])
        self.assertEqual(analysis["total_claims"], 1)
        self.assertIn("The Moon orbits the Earth", analysis["claims"][0]["text"])
        self.assertIn("1 factual claim", analysis["status_message"].lower())

    def test_analyze_claims_single_word_and_random(self):
        """Verify that single words or random text give clear 'Invalid input' messages."""
        res_single = analyze_claims("Apple")
        self.assertFalse(res_single["has_factual_claims"])
        self.assertIn("invalid input", res_single["status_message"].lower())
        self.assertIn("single word", res_single["status_message"].lower())

        res_random = analyze_claims("asdfghjkl")
        self.assertFalse(res_random["has_factual_claims"])
        self.assertIn("invalid input", res_random["status_message"].lower())


if __name__ == "__main__":
    unittest.main()
