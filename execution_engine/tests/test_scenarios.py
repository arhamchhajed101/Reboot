"""Unit tests for ScenarioGenerator."""

import unittest
from execution_engine.evaluation.scenario import ScenarioGenerator, ScenarioType


class TestScenarioGenerator(unittest.TestCase):
    def test_determinism_with_fixed_seed(self):
        s1 = ScenarioGenerator.generate(ScenarioType.NORMAL_MARKET, num_steps=10, seed=123)
        s2 = ScenarioGenerator.generate(ScenarioType.NORMAL_MARKET, num_steps=10, seed=123)

        self.assertEqual(len(s1), 10)
        self.assertEqual(len(s2), 10)
        for state1, state2 in zip(s1, s2):
            self.assertEqual(state1.price, state2.price)
            self.assertEqual(state1.volume, state2.volume)
            self.assertEqual(state1.volatility, state2.volatility)

    def test_mid_scenario_shock_profile(self):
        states = ScenarioGenerator.generate(ScenarioType.MID_SCENARIO_SHOCK, num_steps=10, seed=42)
        # Pre-shock (step 0): normal vol (~0.01)
        self.assertLess(states[0].volatility, 0.02)
        self.assertGreater(states[0].liquidity, 0.8)

        # Mid-shock (step 5): high vol (>0.04) and low liq (<0.3)
        self.assertGreaterEqual(states[5].volatility, 0.04)
        self.assertLessEqual(states[5].liquidity, 0.3)

    def test_zero_volume_gap_profile(self):
        states = ScenarioGenerator.generate(ScenarioType.ZERO_VOLUME_GAP, num_steps=10, seed=42)
        self.assertEqual(states[3].volume, 0.0)
        self.assertEqual(states[4].volume, 0.0)


if __name__ == "__main__":
    unittest.main()
