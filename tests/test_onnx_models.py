"""
tests/test_onnx_models.py
-------------------------
Unit tests for the ONNX Runtime model inference layer in verification/models.py:
  1. NLI 3-way mapping via id2label (contradiction, entailment, neutral)
  2. Embedding shape (384,) and L2 normalisation (unit norm)
  3. Mean pooling respecting the attention mask
  4. Cosine similarity bounds and edge cases
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

import verification.models as models


class TestONNXModels(unittest.TestCase):

    def test_nli_3way_mapping_via_id2label(self):
        """Verifies that logits are correctly mapped to entailment/contradiction/neutral via id2label."""
        # Setup mock session output: logits [10.0, 0.0, 0.0] -> index 0 highest
        # Under id2label {0: 'contradiction', 1: 'entailment', 2: 'neutral'},
        # index 0 is contradiction.
        mock_sess = MagicMock()
        mock_sess.run.return_value = [np.array([[10.0, -5.0, -5.0]], dtype=np.float32)]
        mock_inp = MagicMock()
        mock_inp.name = "input_ids"
        mock_sess.get_inputs.return_value = [mock_inp]

        mock_tok = MagicMock()
        encoding = MagicMock()
        encoding.ids = [101, 102]
        encoding.attention_mask = [1, 1]
        encoding.type_ids = [0, 0]
        mock_tok.encode.return_value = encoding

        with patch.object(models, "_nli_session", mock_sess), \
             patch.object(models, "_nli_tokenizer", mock_tok), \
             patch.object(models, "_nli_id2label", {0: "contradiction", 1: "entailment", 2: "neutral"}), \
             patch.object(models, "_nli_input_names", ["input_ids", "attention_mask"]):
            scores = models.get_nli_scores("Paris is capital", "Paris is in Germany")

        self.assertIn("contradiction", scores)
        self.assertIn("entailment", scores)
        self.assertIn("neutral", scores)
        self.assertGreater(scores["contradiction"], 0.99)
        self.assertLess(scores["entailment"], 0.01)
        self.assertLess(scores["neutral"], 0.01)

        # All scores must be clamped in [0.0, 1.0]
        for label, val in scores.items():
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)

    def test_embedding_shape_and_l2_normalization(self):
        """Verifies that get_embeddings returns (N, 384) float32 with unit L2 norm."""
        mock_sess = MagicMock()
        # 2 texts, seq_len 3, dim 384
        batch_size = 2
        seq_len = 3
        dim = 384
        # Deterministic random token embeddings
        token_embs = np.ones((batch_size, seq_len, dim), dtype=np.float32)
        mock_sess.run.return_value = [token_embs]

        mock_tok = MagicMock()
        enc1 = MagicMock()
        enc1.ids = [1, 2, 3]
        enc1.attention_mask = [1, 1, 1]
        enc1.type_ids = [0, 0, 0]
        mock_tok.encode.return_value = enc1

        # Clear cache for isolated test
        models._embedding_cache.clear()

        with patch.object(models, "_embed_session", mock_sess), \
             patch.object(models, "_embed_tokenizer", mock_tok), \
             patch.object(models, "_embed_input_names", ["input_ids", "attention_mask"]):
            vecs = models.get_embeddings(["text A", "text B"])

        self.assertEqual(vecs.shape, (2, 384))
        self.assertEqual(vecs.dtype, np.float32)

        # Both rows should have unit norm
        norm_0 = float(np.linalg.norm(vecs[0]))
        norm_1 = float(np.linalg.norm(vecs[1]))
        self.assertAlmostEqual(norm_0, 1.0, places=5)
        self.assertAlmostEqual(norm_1, 1.0, places=5)

    def test_mean_pooling_respects_attention_mask(self):
        """Verifies that padding tokens (attention_mask == 0) are excluded from the mean pool."""
        mock_sess = MagicMock()
        # 1 text, seq_len 2, dim 4
        # token 0 = [2, 2, 2, 2] (mask=1), token 1 = [100, 100, 100, 100] (mask=0)
        token_embs = np.array([[[2.0, 2.0, 2.0, 2.0], [100.0, 100.0, 100.0, 100.0]]], dtype=np.float32)
        mock_sess.run.return_value = [token_embs]

        mock_tok = MagicMock()
        enc = MagicMock()
        enc.ids = [1, 0]
        enc.attention_mask = [1, 0]  # second token is masked out
        enc.type_ids = [0, 0]
        mock_tok.encode.return_value = enc

        models._embedding_cache.clear()

        with patch.object(models, "_embed_session", mock_sess), \
             patch.object(models, "_embed_tokenizer", mock_tok), \
             patch.object(models, "_embed_input_names", ["input_ids", "attention_mask"]):
            vec = models.get_embeddings(["masked text"])[0]

        # The vector should be the normalized version of [2, 2, 2, 2], which is [0.5, 0.5, 0.5, 0.5]
        expected = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        np.testing.assert_allclose(vec, expected, rtol=1e-5, atol=1e-5)

    def test_cosine_similarity_bounds_and_edges(self):
        """Tests cosine_similarity calculation, edge cases, and bounds."""
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        self.assertAlmostEqual(models.cosine_similarity(v1, v2), 1.0)

        # Orthogonal
        v_orth = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.assertAlmostEqual(models.cosine_similarity(v1, v_orth), 0.0)

        # Opposite -> dot product is -1.0, must clamp to 0.0
        v_opp = np.array([-1.0, 0.0, 0.0], dtype=np.float32)
        self.assertAlmostEqual(models.cosine_similarity(v1, v_opp), 0.0)

        # Zero vector -> returns 0.0
        v_zero = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.assertAlmostEqual(models.cosine_similarity(v1, v_zero), 0.0)


if __name__ == "__main__":
    unittest.main()

