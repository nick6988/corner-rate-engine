import numpy as np
import math
from scipy.stats import nbinom
from corner_engine import CornerEngine

def run_corner_monte_carlo_test(n_sims: int = 5000):
    pre_match_line = 9.5
    asian_handicap = -0.75
    engine = CornerEngine(pre_match_line=pre_match_line, asian_handicap=asian_handicap)
    
    true_positives = 0   
    false_positives = 0  
    true_negatives = 0   
    false_negatives = 0  

    for _ in range(n_sims):
        time_t = 60.0
        
        # 1. Ground Truth remaining corner expectation (lambda_true)
        true_lambda_rem = float(np.random.uniform(2.0, 5.5))
        
        # ✅ 正確公式：高 λ_rem 對應更高的前 60 分鐘產出 (約 1.70 * lambda_rem)
        time_decay = (30.0 / 90.0) ** 0.85
        implied_heat = true_lambda_rem / (pre_match_line * time_decay)
        expected_past_corners = (pre_match_line * (60.0 / 90.0)) * implied_heat
        
        current_corners = int(max(2, round(expected_past_corners + np.random.normal(0, 0.8))))
        live_line = float(current_corners + 3.5)  # 即時盤口 (如 7 角 -> 盤口 10.5)
        
        # 2. Bookmaker Market Pricing (5% margin)
        market_lambda_noise = np.random.normal(0.0, 0.50)
        market_lambda = max(0.50, true_lambda_rem + market_lambda_noise)
        
        r_disp_m = 15 if market_lambda < 4.0 else 8
        p_market = r_disp_m / (r_disp_m + market_lambda)
        corners_needed = int(math.ceil(live_line - current_corners))
        
        prob_under_m = float(nbinom.cdf(corners_needed - 1, r_disp_m, p_market))
        prob_over_m = max(0.05, min(0.95, 1.0 - prob_under_m))
        prob_under_m = max(0.05, min(0.95, prob_under_m))
        
        offered_odds_over = round(max(1.05, (1.0 / prob_over_m) * 0.95), 2)
        offered_odds_under = round(max(1.05, (1.0 / prob_under_m) * 0.95), 2)

        # 3. Ground Truth EV calculation
        r_disp_true = 15 if true_lambda_rem < 4.0 else 8
        p_true = r_disp_true / (r_disp_true + true_lambda_rem)
        prob_over_true = 1.0 - float(nbinom.cdf(corners_needed - 1, r_disp_true, p_true))
        
        true_ev_over = (prob_over_true * offered_odds_over) - 1.0
        is_true_plus_ev_over = true_ev_over > 0.05

        # 4. Synthesize SofaScore 3-parameter box telemetry matched with implied_heat
        shots_inside_box = int(max(1, round(7.33 * implied_heat + np.random.normal(0, 0.8))))
        blocked_shots = int(max(0, round(5.33 * implied_heat + np.random.normal(0, 0.6))))
        shots_on_target = int(max(1, round(5.0 * implied_heat + np.random.normal(0, 0.6))))
        rolling_10m = int(max(0, round((true_lambda_rem / 30.0) * 10.0 + np.random.normal(0, 0.5))))

        # 5. Engine Diagnostics
        shot_heat = engine.get_advanced_corner_heat(
            time_t=time_t,
            shots_inside_box=shots_inside_box,
            blocked_shots=blocked_shots,
            shots_on_target=shots_on_target
        )
        
        composite_m = engine.get_composite_momentum(time_t, current_corners, rolling_10m)
        
        lambda_rem = engine.calculate_remaining_lambda(
            time_t=time_t,
            current_corners=current_corners,
            shot_heat=shot_heat,
            home_goals=1, away_goals=0,
            rolling_10m_corners=rolling_10m,
            red_card_status="None"
        )
        
        ev_results = engine.calculate_ev(
            live_line=live_line,
            current_corners=current_corners,
            lambda_rem=lambda_rem,
            odds_under=offered_odds_under,
            odds_over=offered_odds_over,
            time_t=time_t,
            composite_m=composite_m
        )
        
        signals = engine.get_signal_diagnostics(
            time_t=time_t,
            live_line=live_line,
            current_corners=current_corners,
            odds_under=offered_odds_under,
            odds_over=offered_odds_over,
            ev_results=ev_results,
            league_tier="ALLOWED",
            rolling_10m_corners=rolling_10m
        )
        
        model_flagged_over = "SNIPER OVER" in signals["over_signal"]

        # 6. Confusion Matrix Update
        if model_flagged_over and is_true_plus_ev_over:
            true_positives += 1
        elif model_flagged_over and not is_true_plus_ev_over:
            false_positives += 1
        elif not model_flagged_over and not is_true_plus_ev_over:
            true_negatives += 1
        elif not model_flagged_over and is_true_plus_ev_over:
            false_negatives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0

    print("=======================================================")
    print(f"📊 FIXED CORNER ENGINE MONTE CARLO RESULTS ({n_sims} Iterations)")
    print("=======================================================")
    print(f"  • True Positives (Valid +EV Signals Captured) : {true_positives}")
    print(f"  • False Positives (False Signals Flagged)   : {false_positives}")
    print(f"  • True Negatives (Correctly Filtered Negative EV): {true_negatives}")
    print(f"  • False Negatives (Missed +EV Opportunities)  : {false_negatives}")
    print("-------------------------------------------------------")
    print(f"  🎯 Signal Precision (Win Rate of Signals)     : {precision:.2%}")
    print(f"  🔍 Signal Recall (Coverage of True Edge)     : {recall:.2%}")
    print("=======================================================\n")

if __name__ == "__main__":
    run_corner_monte_carlo_test()