import numpy as np
from scipy.stats import nbinom
from league_filter import get_league_tier, LeagueCategorizer

class CornerEngine:
    r"""
    Quantitative In-Play Corner Rate Engine based on Negative Binomial Distribution.
    Manages prior match setup, intensity metrics, tactical modifiers, momentum rates,
    remaining corner intensity (\lambda_rem), +EV calculations, and signal diagnostics.
    """

    VALID_TOURNAMENT_TYPES = [
        "League",
        "Cup_Final",
        "Knockout_Leg1",
        "Knockout_Leg2"
    ]

    VALID_RED_CARD_STATUSES = [
        "None",
        "Underdog_Red",
        "Favorite_Red",
        "Balanced_Red"
    ]

    BASELINE_TOTAL_SHOTS = 22.5
    BASELINE_SHOTS_ON_TARGET = 7.5

    def __init__(
        self,
        pre_match_line: float,
        asian_handicap: float = 0.0,
        tournament_type: str = "League",
        leg1_home_goals: int = 0,
        leg1_away_goals: int = 0
    ):
        if pre_match_line <= 0:
            raise ValueError("Pre-match corner line must be greater than 0.")

        if tournament_type not in self.VALID_TOURNAMENT_TYPES:
            raise ValueError(f"Invalid tournament_type. Must be one of {self.VALID_TOURNAMENT_TYPES}")

        self.pre_match_line = pre_match_line
        self.asian_handicap = asian_handicap
        self.tournament_type = tournament_type
        self.leg1_home_goals = leg1_home_goals
        self.leg1_away_goals = leg1_away_goals

        if self.tournament_type == "Knockout_Leg1":
            self.adjusted_pre_line = self.pre_match_line * 0.95
        else:
            self.adjusted_pre_line = self.pre_match_line

    def get_shot_heat(self, time_t: float, total_shots: int, shots_on_target: int) -> float:
        """Calculate match attacking intensity / shot heat modifier (Excel cell B7)."""
        if time_t <= 0:
            return 1.0

        expected_total_shots = self.BASELINE_TOTAL_SHOTS * (time_t / 90.0)
        expected_shots_on_target = self.BASELINE_SHOTS_ON_TARGET * (time_t / 90.0)

        total_shot_ratio = total_shots / expected_total_shots if expected_total_shots > 0 else 0.0
        target_shot_ratio = shots_on_target / expected_shots_on_target if expected_shots_on_target > 0 else 0.0

        raw_heat = (0.6 * total_shot_ratio) + (0.4 * target_shot_ratio)
        return min(1.30, max(0.80, round(raw_heat, 2)))

    def get_score_modifier(self, time_t: float, home_goals: int, away_goals: int) -> float:
        """Calculate scoreline tactical modifier coefficient (Excel cell B8)."""
        goal_diff = home_goals - away_goals

        is_favorite_behind_by_2 = (
            (self.asian_handicap <= -0.75 and goal_diff <= -2) or
            (self.asian_handicap >= 0.75 and goal_diff >= 2)
        )

        if self.tournament_type == "Knockout_Leg2":
            aggregate_diff = (home_goals + self.leg1_home_goals) - (away_goals + self.leg1_away_goals)

            if abs(aggregate_diff) >= 3:
                return 0.65
            elif abs(aggregate_diff) == 2:
                return 1.00 if is_favorite_behind_by_2 else 0.75
            elif (self.asian_handicap <= -0.75 and aggregate_diff == -1) or (self.asian_handicap >= 0.75 and aggregate_diff == 1):
                return 1.45
            else:
                return 1.00

        elif self.tournament_type == "Cup_Final":
            if time_t >= 70 and goal_diff == 0:
                return 0.80
            elif abs(goal_diff) >= 2:
                return 1.00 if is_favorite_behind_by_2 else 0.75
            elif (self.asian_handicap <= -0.75 and goal_diff == -1) or (self.asian_handicap >= 0.75 and goal_diff == 1):
                return 1.35
            else:
                return 1.00

        elif self.tournament_type == "Knockout_Leg1":
            if time_t >= 70 and goal_diff == 0:
                return 0.95
            elif abs(goal_diff) >= 2:
                return 1.00 if is_favorite_behind_by_2 else 0.75
            elif (self.asian_handicap <= -0.75 and goal_diff == -1) or (self.asian_handicap >= 0.75 and goal_diff == 1):
                return 1.35
            else:
                return 1.00

        else:  # League
            if abs(goal_diff) >= 2:
                return 1.00 if is_favorite_behind_by_2 else 0.75
            elif (self.asian_handicap <= -0.75 and goal_diff == -1) or (self.asian_handicap >= 0.75 and goal_diff == 1):
                return 1.35
            else:
                return 1.00

    def get_red_card_modifier(self, red_card_status: str = "None") -> float:
        """Calculate red card tactical impact modifier (Excel cell B22)."""
        modifiers = {
            "Underdog_Red": 1.20,
            "Favorite_Red": 0.85,
            "Balanced_Red": 0.90,
            "None": 1.00
        }
        return modifiers.get(red_card_status, 1.00)

    def get_global_momentum(self, time_t: float, current_corners: int) -> float:
        """Calculate global corner pace deviation rate P (Excel cell B9)."""
        if time_t <= 0:
            return 0.0
        expected_corners_so_far = self.adjusted_pre_line * (time_t / 90.0)
        return current_corners / expected_corners_so_far if expected_corners_so_far > 0 else 0.0

    def get_rolling_momentum(self, time_t: float, current_corners: int, rolling_10m_corners: int | None = None) -> float:
        """Calculate 10-minute rolling corner rate deviation."""
        global_rate = self.get_global_momentum(time_t, current_corners)
        if time_t < 10 or rolling_10m_corners is None:
            return global_rate

        actual_10m_rate_per_min = rolling_10m_corners / 10.0
        expected_rate_per_min = self.adjusted_pre_line / 90.0
        return actual_10m_rate_per_min / expected_rate_per_min if expected_rate_per_min > 0 else 0.0

    def get_composite_momentum(self, time_t: float, current_corners: int, rolling_10m_corners: int | None = None) -> float:
        """Calculate combined composite momentum rate."""
        if time_t <= 0:
            return 0.0

        global_rate = self.get_global_momentum(time_t, current_corners)
        rolling_rate = self.get_rolling_momentum(time_t, current_corners, rolling_10m_corners)
        capped_rolling = min(1.50, rolling_rate)

        if time_t >= 55:
            composite = (0.80 * global_rate) + (0.20 * capped_rolling)
        else:
            composite = (0.85 * global_rate) + (0.15 * capped_rolling)

        return round(composite, 4)
    
    def calculate_remaining_lambda(
        self,
        time_t: float,
        current_corners: int,
        total_shots: int,
        shots_on_target: int,
        home_goals: int,
        away_goals: int,
        rolling_10m_corners: int | None = None,
        red_card_status: str = "None"
    ) -> float:
        if time_t >= 90:
            return 0.0

        time_decay = (max(0.0, 90.0 - time_t) / 90.0) ** 0.85
        shot_heat = self.get_shot_heat(time_t, total_shots, shots_on_target)
        score_mod = self.get_score_modifier(time_t, home_goals, away_goals)
        red_card_mod = self.get_red_card_modifier(red_card_status)
        composite_momentum = self.get_composite_momentum(time_t, current_corners, rolling_10m_corners)

        elapsed_ratio = time_t / 90.0
        weighted_momentum = (elapsed_ratio * composite_momentum) + (1.0 - elapsed_ratio)

        lambda_rem = (
            self.adjusted_pre_line * time_decay * weighted_momentum * score_mod * shot_heat * red_card_mod
        )
        return lambda_rem
    
    def calculate_ev(
        self,
        live_line: float,
        current_corners: int,
        lambda_rem: float,
        odds_under: float,
        odds_over: float,
        r_dispersion: int = 12
    ) -> dict:
        r"""
        Calculate win probabilities and Expected Value (+EV) using Negative Binomial Distribution.
        (Corresponds to Excel cells B12:B15).
        """
        corners_needed_to_hit_line = int(live_line - current_corners)

        if current_corners >= live_line:
            return {
                "prob_under": 0.0,
                "ev_under": -1.0,
                "prob_over": 1.0,
                "ev_over": (1.0 * odds_over) - 1.0
            }

        p_param = r_dispersion / (r_dispersion + lambda_rem) if (r_dispersion + lambda_rem) > 0 else 1.0

        prob_under = nbinom.cdf(corners_needed_to_hit_line - 1, r_dispersion, p_param) if corners_needed_to_hit_line > 0 else 0.0
        prob_over = 1.0 - prob_under

        ev_under = (prob_under * odds_under) - 1.0
        ev_over = (prob_over * odds_over) - 1.0

        return {
            "prob_under": prob_under,
            "ev_under": ev_under,
            "prob_over": prob_over,
            "ev_over": ev_over
        }

    def get_signal_diagnostics(
        self,
        time_t: float,
        live_line: float,
        current_corners: int,
        odds_under: float,
        odds_over: float,
        ev_results: dict,
        league_tier: str = "ALLOWED",
        rolling_10m_corners: int | None = None
    ) -> dict:

        composite_m = self.get_composite_momentum(time_t, current_corners, rolling_10m_corners)
        under_buffer = live_line - current_corners

        # 1. Banned Leagues Check
        if league_tier == "BANNED":
            return {
                "under_signal": "⛔ BANNED LEAGUE: Trading Suspended (South America)",
                "over_signal": "⛔ BANNED LEAGUE: Trading Suspended (South America)",
                "composite_momentum": composite_m,
                "under_buffer": under_buffer,
                "over_checks": {},
                "under_checks": {}
            }

        # 2. Under Signal & Checks (Keep Pre-Line Cap strictly <= 9.5)
        u_checks = {
            "Time Window (55-68m)": (55 <= time_t <= 68, f"{time_t:.0f}m"),
            "Pre-Line (<= 9.5)": (self.pre_match_line <= 9.5, f"{self.pre_match_line}"),
            "Momentum P (<= 0.50)": (composite_m <= 0.50, f"{composite_m:.2f}"),
            "Under Buffer (>= 2.5)": (under_buffer >= 2.5, f"{under_buffer:.1f}"),
            "Odds (>= 1.65)": (odds_under >= 1.65, f"{odds_under:.2f}"),
            "EV (> +15%)": (ev_results["ev_under"] > 0.15, f"{ev_results['ev_under']:+.1%}")
        }

        if league_tier == "NO_UNDER":
            under_signal = "⛔ NO-UNDER LEAGUE: Under Trades Prohibited"
        else:
            under_eligible = all(check[0] for check in u_checks.values())
            under_signal = (
                f"🔥 SNIPER UNDER (+EV: {ev_results['ev_under']:+.1%})"
                if under_eligible else "💤 No Under Signal"
            )

        # 3. Over Signal & Checks (Expanded Pre-Line Cap to <= 10.5)
        required_over_momentum = 1.15 if time_t >= 55 else 1.35
        required_over_odds = 1.80 if time_t >= 70 else 1.65
        valid_time_window = (25 <= time_t <= 38) or (55 <= time_t <= 78)
        line_spike_break = (live_line >= 14.5) or ((live_line - self.pre_match_line) >= 5.0)
        is_outburst_window = (55 <= time_t <= 68) and (composite_m >= 1.50)

        o_checks = {
            "Time Window (25-38 / 55-78m)": (valid_time_window, f"{time_t:.0f}m"),
            "Pre-Line (<= 10.5)": (self.pre_match_line <= 10.5, f"{self.pre_match_line}"),
            f"Momentum P (>= {required_over_momentum:.2f})": (composite_m >= required_over_momentum, f"{composite_m:.2f}"),
            "Odds (>= 1.65/1.80)": (odds_over >= required_over_odds, f"{odds_over:.2f}"),
            "EV (> +15%)": (ev_results["ev_over"] > 0.15, f"{ev_results['ev_over']:+.1%}")
        }

        if line_spike_break and not is_outburst_window:
            over_signal = "CIRCUIT BREAKER: Extreme Line Spike (>=14.5 or +5.0 Over Pre-Line)"
        else:
            over_eligible = all(check[0] for check in o_checks.values())
            over_signal = (
                f"🔥 SNIPER OVER (+EV: {ev_results['ev_over']:+.1%})"
                if over_eligible else "💤 No Over Signal"
            )

        return {
            "under_signal": under_signal,
            "over_signal": over_signal,
            "composite_momentum": composite_m,
            "under_buffer": under_buffer,
            "over_checks": o_checks,
            "under_checks": u_checks
        }