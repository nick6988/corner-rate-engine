import math
from scipy.stats import poisson

class GoalEngine:
    r"""
    Quantitative In-Play Goal Rate Engine based on Time-Varying Non-Homogeneous Poisson Process (NHPP).
    """

    BENCHMARK_GOAL_LINE = 2.75
    BASELINE_SOT = 7.5
    BASELINE_SHOTS = 22.5
    BASELINE_DA = 90.0

    BENCHMARK_TEAM_GOAL = 1.375
    BASELINE_TEAM_SOT = 3.75
    BASELINE_TEAM_SHOTS = 11.25
    BASELINE_TEAM_DA = 45.0

    # -------------------------------------------------------------------------
    # v2.1 Dynamic Flow Constants (Empirical Calibration Placeholders)
    # -------------------------------------------------------------------------
    WEIGHT_FLOW_XG = 0.70      # TODO: Empirically calibrate via 100+ match log
    WEIGHT_FLOW_XGOT = 0.30    # TODO: Empirically calibrate via 100+ match log
    BASELINE_XGOT_RATIO = 0.65 # TODO: Calibrate per league (EPL vs secondary leagues)
    DAMPENING_FACTOR = 0.25    # Reserved for v2.2 pricing integration

    def __init__(self, pre_match_goal_line: float, asian_handicap: float = 0.0):
        if pre_match_goal_line <= 0:
            raise ValueError("Pre-match goal line must be greater than 0.")

        self.pre_match_goal_line = pre_match_goal_line
        self.asian_handicap = asian_handicap

        # Dynamic Line Scale Relative to 2.75 Benchmark
        self.line_scale = self.pre_match_goal_line / self.BENCHMARK_GOAL_LINE

        # Pre-Match Team Expectation Split
        self.lambda_h_pre = max(0.1, (self.pre_match_goal_line - self.asian_handicap) / 2.0)
        self.lambda_a_pre = max(0.1, (self.pre_match_goal_line + self.asian_handicap) / 2.0)
    

    def get_goal_heat(
        self,
        time_t: float,
        use_advanced: bool,
        home_xg: float = 0.0,
        away_xg: float = 0.0,
        home_xgot: float = 0.0,
        away_xgot: float = 0.0,
        home_shots: int = 0,
        away_shots: int = 0,
        home_sot: int = 0,
        away_sot: int = 0,
        home_da: int = 0,
        away_da: int = 0
    ) -> tuple[float, float, bool, bool]: # return goal_heat_home, goal_heat_away, fault_home, fault_away
        """Calculates independent goal heat intensity and conversion faults for Home and Away."""
        if time_t <= 0:
            return 1.0, 1.0, False, False

        time_ratio = time_t / 90.0
        elapsed_ratio = min(1.0, max(0.0, time_ratio))

        # Dynamic baseline scaling per team
        scale_h = self.lambda_h_pre / self.BENCHMARK_TEAM_GOAL
        scale_a = self.lambda_a_pre / self.BENCHMARK_TEAM_GOAL

        fault_h, fault_a = False, False

        if use_advanced:
            # 1. Advanced Mode (xG & xGOT)
            exp_xg_h = self.lambda_h_pre * time_ratio
            exp_xg_a = self.lambda_a_pre * time_ratio

            # 獨立計算 xGOT 的期望基準 (套用 0.65 執行折率)
            exp_xgot_h = exp_xg_h * self.BASELINE_XGOT_RATIO
            exp_xgot_a = exp_xg_a * self.BASELINE_XGOT_RATIO

            # 各自計算達成率 (Rate)
            rate_xg_h = (home_xg / exp_xg_h) if exp_xg_h > 0 else 1.0
            rate_xgot_h = (home_xgot / exp_xgot_h) if exp_xgot_h > 0 else 1.0

            rate_xg_a = (away_xg / exp_xg_a) if exp_xg_a > 0 else 1.0
            rate_xgot_a = (away_xgot / exp_xgot_a) if exp_xgot_a > 0 else 1.0

            # 體積加權 60% + 質量加權 40%
            raw_heat_h = (0.60 * rate_xg_h) + (0.40 * rate_xgot_h)
            raw_heat_a = (0.60 * rate_xg_a) + (0.40 * rate_xgot_a)

            # Independent Conversion Fault Gates (High xG, broken xGOT)
            if home_xg >= 0.80 and (home_xgot / home_xg if home_xg > 0 else 1.0) < 0.35:
                raw_heat_h *= 0.75
                fault_h = True

            if away_xg >= 0.80 and (away_xgot / away_xg if away_xg > 0 else 1.0) < 0.35:
                raw_heat_a *= 0.75
                fault_a = True

        else:
            # 2. Proxy Mode (SoT, Shots, DA)
            exp_sot_h, exp_sot_a = (self.BASELINE_TEAM_SOT * scale_h) * time_ratio, (self.BASELINE_TEAM_SOT * scale_a) * time_ratio
            exp_s_h, exp_s_a = (self.BASELINE_TEAM_SHOTS * scale_h) * time_ratio, (self.BASELINE_TEAM_SHOTS * scale_a) * time_ratio
            exp_da_h, exp_da_a = (self.BASELINE_TEAM_DA * scale_h) * time_ratio, (self.BASELINE_TEAM_DA * scale_a) * time_ratio

            r_sot_h = home_sot / exp_sot_h if exp_sot_h > 0 else 0.0
            r_sot_a = away_sot / exp_sot_a if exp_sot_a > 0 else 0.0
            r_s_h = home_shots / exp_s_h if exp_s_h > 0 else 0.0
            r_s_a = away_shots / exp_s_a if exp_s_a > 0 else 0.0
            r_da_h = home_da / exp_da_h if exp_da_h > 0 else 0.0
            r_da_a = away_da / exp_da_a if exp_da_a > 0 else 0.0

            raw_heat_h = (0.50 * r_sot_h) + (0.30 * r_s_h) + (0.20 * r_da_h)
            raw_heat_a = (0.50 * r_sot_a) + (0.30 * r_s_a) + (0.20 * r_da_a)


        # Apply bounds without premature rounding
        # 放寬極端熱度上限
        max_heat_limit = 1.85 if (use_advanced and (home_xg >= 2.50 or away_xg >= 2.50)) else 1.50

        bounded_h = min(max_heat_limit, max(0.50, raw_heat_h))
        bounded_a = min(max_heat_limit, max(0.50, raw_heat_a))

        # Bayesian Compound Weighting with elapsed time
        compound_h = (1.0 - elapsed_ratio) * 1.0 + elapsed_ratio * bounded_h
        compound_a = (1.0 - elapsed_ratio) * 1.0 + elapsed_ratio * bounded_a

        return round(compound_h, 4), round(compound_a, 4), fault_h, fault_a

    def get_score_modifiers(
        self, time_t: float, home_goals: int, away_goals: int, heat_h: float = 1.0, heat_a: float = 1.0
    ) -> tuple[float, float]: # return mod_home, mod_away
        """Calculates distinct tactical scoreline modifiers for Home and Away (mod_home, mod_away)."""
        goal_diff = home_goals - away_goals  # >0: Home leads, <0: Away leads

        # 1. Blowout (Lead >= 3 goals) -> Both teams drop tempo
        if abs(goal_diff) >= 3:
            if goal_diff >= 3:  # 主隊大勝
                mod_h = 0.85 if heat_h >= 1.30 else 0.65
                mod_a = 0.50  # 客隊士氣崩潰
                return mod_h, mod_a
            else:  # 客隊大勝 (如 0-4)
                mod_h = 0.50  # 主隊士氣崩潰
                mod_a = 0.85 if heat_a >= 1.30 else 0.65
                return mod_h, mod_a

        # 2. Home Favorite Trailing (AH <= -0.75 and Home is behind)
        if self.asian_handicap <= -0.75 and goal_diff <= -1:
            return 1.35, 1.15  # Home siege pressure (1.35), Away counter space (1.15)

        # 3. Away Favorite Trailing (AH >= 0.75 and Away is behind)
        if self.asian_handicap >= 0.75 and goal_diff >= 1:
            return 1.15, 1.35  # Home counter space (1.15), Away siege pressure (1.35)

        # 4. Favorite Leading by 1+ Goals (Game cools down slightly)
        if self.asian_handicap <= -0.75 and goal_diff >= 1:
            return 0.85, 1.10  # Home controls tempo, Away forced to push
        if self.asian_handicap >= 0.75 and goal_diff <= -1:
            return 1.10, 0.85  # Home forced to push, Away controls tempo

        # 5. Late-Game Tight Draw (T >= 75 and score tied)
        if time_t >= 75 and goal_diff == 0:
            return 0.90, 0.90

        return 1.00, 1.00

    def get_red_card_modifiers(self, red_card_status: str = "None") -> tuple[float, float]:
        """Calculates asymmetric team red card impact modifiers considering favorite/underdog status."""
        if red_card_status == "None":
            return 1.00, 1.00
        elif red_card_status == "Both_Red":
            return 0.85, 0.85

        # 判斷主隊是否為強隊 (AH <= -0.75) 或 弱隊 (AH >= 0.75)
        home_is_fav = self.asian_handicap <= -0.75
        away_is_fav = self.asian_handicap >= 0.75

        if red_card_status == "Home_Red":
            if home_is_fav:
                # 強隊(主)領紅牌：主隊打75折，弱隊(客)多打一人但進攻能力有限，僅加成1.15x
                return 0.75, 1.15
            elif away_is_fav:
                # 弱隊(主)領紅牌：主隊打60折，強隊(客)多打一人展開徹底圍攻，獲得1.35x加成
                return 0.60, 1.35
            else:
                # 均勢盤 (AH 接近 0)
                return 0.70, 1.25

        elif red_card_status == "Away_Red":
            if away_is_fav:
                # 強隊(客)領紅牌：客隊打75折，弱隊(主)僅獲得1.15x加成
                return 1.15, 0.75
            elif home_is_fav:
                # 弱隊(客)領紅牌：客隊打60折，強隊(主)獲得1.35x圍攻加成
                return 1.35, 0.60
            else:
                # 均勢盤 (AH 接近 0)
                return 1.25, 0.70

        return 1.00, 1.00
    
    def calculate_remaining_lambda(
        self,
        time_t: float,
        heat_h: float,
        heat_a: float,
        home_goals: int,
        away_goals: int,
        red_card_status: str = "None"
    ) -> dict[str, float]:
        """Calculates remaining match and team goal expectations independently."""
        if time_t >= 90:
            return {"lambda_rem": 0.0, "lambda_home_rem": 0.0, "lambda_away_rem": 0.0}

        time_decay = (max(0.0, 90.0 - time_t) / 90.0) ** 0.88
        score_mod_h, score_mod_a = self.get_score_modifiers(time_t, home_goals, away_goals, heat_h, heat_a)
        red_mod_h, red_mod_a = self.get_red_card_modifiers(red_card_status)

        # Fully Independent Team Lambdas
        lambda_home_rem = (
            self.lambda_h_pre * time_decay * heat_h * score_mod_h * red_mod_h
        )
        lambda_away_rem = (
            self.lambda_a_pre * time_decay * heat_a * score_mod_a * red_mod_a
        )

        lambda_rem = lambda_home_rem + lambda_away_rem

        return {
            "lambda_rem": round(lambda_rem, 4),
            "lambda_home_rem": round(lambda_home_rem, 4),
            "lambda_away_rem": round(lambda_away_rem, 4)
        }

    def calculate_ev(
        self,
        live_goal_line: float,
        current_goals: int,
        lambda_rem: float,
        odds_under: float,
        odds_over: float
    ) -> dict[str, float]:
        """Calculates exact Poisson probabilities and +EV for split Asian total lines."""
        
        # Hard cap check: if current goals already completely guarantee Over full win
        if current_goals >= live_goal_line + 0.5:
            return {
                "prob_under": 0.0,
                "ev_under": -1.0,
                "prob_over": 1.0,
                "ev_over": round(odds_over - 1.0, 4)
            }

        ev_over = 0.0
        ev_under = 0.0
        
        # Effective win probability accumulators (Full Win = 1.0, Half Win = 0.5)
        eff_prob_over = 0.0
        eff_prob_under = 0.0

        # Simulate discrete Poisson distribution for remaining goals X in [0, 15]
        for rem_goals in range(16):
            p_k = poisson.pmf(rem_goals, lambda_rem)
            total_goals = current_goals + rem_goals
            
            # Precision guard for float subtraction
            diff = round(total_goals - live_goal_line, 2)

            # --- Over Payoff Matrix ---
            if diff >= 0.5:
                payoff_over = odds_over - 1.0
                eff_prob_over += p_k
            elif diff == 0.25:
                payoff_over = (odds_over - 1.0) / 2.0  # Win Half
                eff_prob_over += p_k * 0.5
            elif diff == -0.25:
                payoff_over = -0.5                    # Lose Half
            else:
                payoff_over = -1.0                    # Lose Full

            # --- Under Payoff Matrix ---
            if diff <= -0.5:
                payoff_under = odds_under - 1.0
                eff_prob_under += p_k
            elif diff == -0.25:
                payoff_under = (odds_under - 1.0) / 2.0 # Win Half
                eff_prob_under += p_k * 0.5
            elif diff == 0.25:
                payoff_under = -0.5                   # Lose Half
            elif diff == 0.0:
                payoff_under = 0                      # Push (No Win/Loss)
            else:
                payoff_under = -1.0                   # Lose Full

            ev_over += p_k * payoff_over
            ev_under += p_k * payoff_under

        return {
            "prob_under_eff": round(float(eff_prob_under), 4),
            "prob_over_eff": round(float(eff_prob_over), 4),
            "ev_under": round(float(ev_under), 4),
            "ev_over": round(float(ev_over), 4)
        }
    
    def get_flow_pressure_index(
        self,
        time_t: float,
        home_xg_15m: float,
        away_xg_15m: float,
        home_xgot_15m: float,
        away_xgot_15m: float,
        heat_h: float,
        heat_a: float
    ) -> dict[str, float]:
        """
        Calculates 15-Minute Flow Pressure Index & Quality Ratio.
        PURE DIAGNOSTIC METRIC (v2.1): Strictly logged for observation; does NOT alter lambda_rem.
        """
        if time_t < 15:
            return {
                "mom_h": 1.00, "mom_a": 1.00, "mom_total": 1.00,
                "quality_h": 0.0, "quality_a": 0.0,
                "eff_mom_h": 1.00, "eff_mom_a": 1.00
            }

        # 1. Baseline Expectations per 15m Window
        exp_xg_15m_h = max(0.05, (self.lambda_h_pre * (15.0 / 90.0)) * heat_h)
        exp_xg_15m_a = max(0.05, (self.lambda_a_pre * (15.0 / 90.0)) * heat_a)
        
        exp_xgot_15m_h = exp_xg_15m_h * self.BASELINE_XGOT_RATIO
        exp_xgot_15m_a = exp_xg_15m_a * self.BASELINE_XGOT_RATIO

        # 2. Acceleration Rates
        rate_xg_h = home_xg_15m / exp_xg_15m_h
        rate_xg_a = away_xg_15m / exp_xg_15m_a
        
        rate_xgot_h = home_xgot_15m / exp_xgot_15m_h
        rate_xgot_a = away_xgot_15m / exp_xgot_15m_a

        # 3. Weighted Momentum (Configurable Constants)
        raw_mom_h = (self.WEIGHT_FLOW_XG * rate_xg_h) + (self.WEIGHT_FLOW_XGOT * rate_xgot_h)
        raw_mom_a = (self.WEIGHT_FLOW_XG * rate_xg_a) + (self.WEIGHT_FLOW_XGOT * rate_xgot_a)

        # 4. Clamped Momentum [0.85, 1.20]
        mom_h = min(1.20, max(0.85, raw_mom_h))
        mom_a = min(1.20, max(0.85, raw_mom_a))
        mom_total = round((mom_h + mom_a) / 2.0, 2)

        # 5. Micro Quality Ratio (Execution vs Volume)
        quality_h = round(home_xgot_15m / home_xg_15m, 3) if home_xg_15m > 0 else 0.0
        quality_a = round(away_xgot_15m / away_xg_15m, 3) if away_xg_15m > 0 else 0.0

        # 6. Theoretical Dampened Multiplier for v2.2 Evaluation
        eff_mom_h = round(1.0 + self.DAMPENING_FACTOR * (mom_h - 1.0), 3)
        eff_mom_a = round(1.0 + self.DAMPENING_FACTOR * (mom_a - 1.0), 3)

        return {
            "mom_h": round(mom_h, 2),
            "mom_a": round(mom_a, 2),
            "mom_total": mom_total,
            "quality_h": quality_h,
            "quality_a": quality_a,
            "eff_mom_h": eff_mom_h,
            "eff_mom_a": eff_mom_a
        }
    
    def get_signal_diagnostics(
        self,
        time_t: float,
        live_goal_line: float,
        current_goals: int,
        odds_under: float,
        odds_over: float,
        ev_results: dict,
        league_tier: str = "ALLOWED"
    ) -> dict:
        """Evaluates goal market risk control and signal generation."""

        # 1. Banned Leagues Check (Identical to CornerEngine)
        if league_tier == "BANNED":
            return {
                "under_signal": "⛔ BANNED LEAGUE: Trading Suspended",
                "over_signal": "⛔ BANNED LEAGUE: Trading Suspended",
                "over_checks": {},
                "under_checks": {}
            }

        # 2. Under Goal Checks
        goal_under_buffer = live_goal_line - current_goals
        u_checks = {
            "Time Window (50-75m)": (50 <= time_t <= 75, f"{time_t:.0f}m"),
            "Under Buffer (>= 1.25)": (goal_under_buffer >= 1.25, f"{goal_under_buffer:.2f}"),
            "Odds (>= 1.65)": (odds_under >= 1.65, f"{odds_under:.2f}"),
            "EV (> +15%)": (ev_results["ev_under"] > 0.15, f"{ev_results['ev_under']:+.1%}")
        }

        if league_tier == "NO_UNDER":
            under_signal = "⛔ NO-UNDER LEAGUE: Under Trades Prohibited"
        else:
            under_eligible = all(check[0] for check in u_checks.values())
            under_signal = (
                f"🔥 GOAL SNIPER UNDER (+EV: {ev_results['ev_under']:+.1%})"
                if under_eligible else "💤 No Goal Under Signal"
            )

        # 3. Over Goal Checks
        required_over_odds = 1.80 if time_t >= 70 else 1.65
        o_checks = {
            "Time Window (45-80m)": (45 <= time_t <= 80, f"{time_t:.0f}m"),
            "Odds (>= 1.65/1.80)": (odds_over >= required_over_odds, f"{odds_over:.2f}"),
            "EV (> +15%)": (ev_results["ev_over"] > 0.15, f"{ev_results['ev_over']:+.1%}")
        }

        over_eligible = all(check[0] for check in o_checks.values())
        over_signal = (
            f"🔥 GOAL SNIPER OVER (+EV: {ev_results['ev_over']:+.1%})"
            if over_eligible else "💤 No Goal Over Signal"
        )

        return {
            "under_signal": under_signal,
            "over_signal": over_signal,
            "over_checks": o_checks,
            "under_checks": u_checks
        }
'''
g = GoalEngine(3.0, 0.5)
print(g.lambda_h_pre)  # Example usage
print(g.lambda_a_pre)  # Example usage
goal_heat = g.get_goal_heat(time_t=60, use_advanced=True, home_xg=0.5, away_xg=0.3, home_xgot=0.4, away_xgot=0.2, home_shots=5, away_shots=3, home_sot=3, away_sot=2, home_da=10, away_da=8)
print(goal_heat)  # Example usage
calculated_lambdas = g.calculate_remaining_lambda(time_t=60, heat_h=goal_heat[0], heat_a=goal_heat[1], home_goals=1, away_goals=0, red_card_status="Home_Red")
print(calculated_lambdas)  # Example usage
ev_results = g.calculate_ev(live_goal_line=3.25, current_goals=1, lambda_rem=calculated_lambdas["lambda_rem"], odds_under=1.5, odds_over=1.5)
print(ev_results)  # Example usage
sig = g.get_signal_diagnostics(time_t=60, live_goal_line=3.25, current_goals=1, odds_under=1.85, odds_over=1.85, ev_results=ev_results, league_tier="ALLOWED")
print(sig)  # Example usage
'''