"""Unit tests for V2 tuned discriminative head/scorer + quantity-invariance training & group-CV."""

import json
import site
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_SITE = ROOT.parent / "aegis/.venv/Lib/site-packages"
if VENV_SITE.is_dir():
    site.addsitedir(str(VENV_SITE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from expand_operational_data import QUANTITIES
from reviewed_development_v2 import validated_rows
from reviewed_development_v2_tuned import (
    CLASS_WEIGHTS_TUPLE,
    TUNED_CONFIG,
    build_profile_grouped_folds,
)


class TestReviewedDevelopmentV2Tuned(unittest.TestCase):
    def test_class_weights_balance_total_class_mass(self):
        counts = (36, 76, 49)
        masses = [c * w for c, w in zip(counts, CLASS_WEIGHTS_TUPLE)]
        for m in masses:
            self.assertAlmostEqual(m, 161.0 / 3.0, places=6)

    def test_tuned_config_discriminative_lrs_and_fp32(self):
        self.assertEqual(TUNED_CONFIG["head_lr"], 7e-5)
        self.assertEqual(TUNED_CONFIG["scorer_lr"], 1.2e-3)
        self.assertTrue(TUNED_CONFIG["encoder_frozen"])
        self.assertGreater(TUNED_CONFIG["quantity_invariance_weight"], 0.0)
        self.assertGreater(TUNED_CONFIG["safety_penalty_weight"], 0.0)

    def test_profile_grouped_folds_have_zero_valid_profile_leakage(self):
        rows, metadata, _ = validated_rows()
        folds = build_profile_grouped_folds(rows, metadata, n_folds=5)
        self.assertEqual(len(folds), 5)
        all_val = []
        for f in folds:
            train_set = set(f["train_indices"])
            val_set = set(f["val_indices"])
            self.assertFalse(train_set & val_set)
            self.assertEqual(len(train_set) + len(val_set), 161)
            train_valid_profiles = {
                metadata[i]["profile_id"]
                for i in train_set
                if json.loads(rows[i]["state"])["operational"]["quantity"] in QUANTITIES
            }
            val_valid_profiles = {
                metadata[i]["profile_id"]
                for i in val_set
                if json.loads(rows[i]["state"])["operational"]["quantity"] in QUANTITIES
            }
            self.assertFalse(train_valid_profiles & val_valid_profiles)
            all_val.extend(f["val_indices"])
        self.assertEqual(sorted(all_val), list(range(161)))


if __name__ == "__main__":
    unittest.main()
