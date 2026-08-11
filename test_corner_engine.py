import unittest
from corner_engine import CornerEngine


class TestCornerEngine(unittest.TestCase):
    """Automated test suite for Quantitative Corner Engine logic."""

    def test_init_validation(self):
        """Verify parameter bounds and tournament pre-line adjustments."""
        with self.assertRaises(ValueError):
            CornerEngine(pre_match_line=-1.0)

        with self.assertRaises(ValueError):
            CornerEngine(pre_match_line=9.5, tournament_type="InvalidFormat")

        # Knockout Leg 1 applies 5% conservative discount (9.5 * 0.95 = 9.025)
        engine_leg1 = CornerEngine(pre_match_line=9.5, tournament_type="Knockout_Leg1")
        self.assertAlmostEqual(engine_leg1.adjusted_pre_line, 9.025)

    def test_shot_heat_clamping(self):
        """Verify shot heat intensity coefficient clamps between 0.80 and 1.30."""
        engine = CornerEngine(pre_match_line=9.5)

        # Baseline expected rate at minute 60 (15 total shots, 5 on target)
        self.assertEqual(engine.get_shot_heat(time_t=60, total_shots=15, shots_on_target=5), 1.00)

        # Low intensity floor cap (0.80)
        self.assertEqual(engine.get_shot_heat(time_t=60, total_shots=1, shots_on_target=0), 0.80)

        # High intensity ceiling cap (1.30)
        self.assertEqual(engine.get_shot_heat(time_t=60, total_shots=30, shots_on_target=15), 1.30)

    def test_score_modifier(self):
        """Verify game-state scoreline tactical modifiers."""
        engine = CornerEngine(pre_match_line=9.5, asian_handicap=-0.75, tournament_type="League")

        # Tied match -> 1.00
        self.assertEqual(engine.get_score_modifier(time_t=60, home_goals=0, away_goals=0), 1.00)

        # Favorite trailing by 1 goal -> High urgency boost (1.35)
        self.assertEqual(engine.get_score_modifier(time_t=60, home_goals=0, away_goals=1), 1.35)

        # Favorite leading by 2 goals -> Passive state penalty (0.75)
        self.assertEqual(engine.get_score_modifier(time_t=60, home_goals=2, away_goals=0), 0.75)

    def test_red_card_modifier(self):
        """Verify red card tactical status modifiers."""
        engine = CornerEngine(pre_match_line=9.5)

        self.assertEqual(engine.get_red_card_modifier("Underdog_Red"), 1.20)
        self.assertEqual(engine.get_red_card_modifier("Favorite_Red"), 0.85)
        self.assertEqual(engine.get_red_card_modifier("None"), 1.00)

    def test_ev_and_circuit_breaker(self):
        """Verify expected value (+EV) output and risk circuit breaker triggers."""
        engine = CornerEngine(pre_match_line=9.5, asian_handicap=-0.75)

        lambda_val = engine.calculate_remaining_lambda(
            time_t=60, current_corners=4, total_shots=10, shots_on_target=3, home_goals=0, away_goals=1
        )
        ev_res = engine.calculate_ev(live_line=7.5, current_corners=4, lambda_rem=lambda_val, odds_under=1.85, odds_over=1.95)

        self.assertIn("ev_under", ev_res)
        self.assertIn("ev_over", ev_res)

        # Test extreme line spike trigger (Live line 15.0 >= 14.5 or +5.0 over pre-line)
        signals = engine.get_signal_diagnostics(
            time_t=60, live_line=15.0, current_corners=4, odds_under=1.85, odds_over=1.95, ev_results=ev_res
        )
        self.assertIn("CIRCUIT BREAKER", signals["over_signal"])


if __name__ == "__main__":
    unittest.main()