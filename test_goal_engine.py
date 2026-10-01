import numpy as np
import math
from goal_engine import GoalEngine

def run_corrected_monte_carlo_test(n_sims: int = 5000):
    """
    Corrected Monte Carlo parameter recovery test.
    Simulates true match rates vs. bookmaker market pricing errors.
    """
    engine = GoalEngine(pre_match_goal_line=2.75, asian_handicap=-0.75)
    
    true_positives = 0   # Engine flagged +EV AND True EV > 0
    false_positives = 0  # Engine flagged +EV BUT True EV <= 0
    true_negatives = 0   # Engine ignored AND True EV <= 0
    false_negatives = 0  # Engine ignored BUT True EV > 0

    for _ in range(n_sims):
        # 1. Ground Truth Match State at T=60
        current_goals = np.random.choice([0, 1, 2])
        live_goal_line = current_goals + 1.25  # Split Asian line
        
        # Ground truth remaining expectation lambda_true
        true_lambda_rem = float(np.random.uniform(0.40, 1.60))
        
        # 2. Bookmaker Market Pricing (with market noise and 5% vig)
        # Sometimes bookies over/underprice remaining goals
        market_lambda_noise = np.random.normal(0.0, 0.25)
        market_lambda = max(0.10, true_lambda_rem + market_lambda_noise)
        
        # Bookmaker Odds calculated from market_lambda with 5% margin
        market_ev_dict = engine.calculate_ev(
            live_goal_line=live_goal_line,
            current_goals=current_goals,
            lambda_rem=market_lambda,
            odds_under=1.90, odds_over=1.90
        )
        
        # Derive fair odds from market_lambda, then apply 5% margin
        prob_over_m = max(0.05, min(0.95, market_ev_dict["prob_over_eff"]))
        prob_under_m = max(0.05, min(0.95, market_ev_dict["prob_under_eff"]))
        
        offered_odds_over = round(max(1.05, (1.0 / prob_over_m) * 0.95), 2)
        offered_odds_under = round(max(1.05, (1.0 / prob_under_m) * 0.95), 2)

        # 3. Ground Truth EV (evaluated at true_lambda_rem against bookie odds)
        true_ev_dict = engine.calculate_ev(
            live_goal_line=live_goal_line,
            current_goals=current_goals,
            lambda_rem=true_lambda_rem,
            odds_under=offered_odds_under,
            odds_over=offered_odds_over
        )
        is_true_plus_ev_over = true_ev_dict["ev_over"] > 0.05

        # 4. Generate Telemetry from true_lambda_rem for GoalEngine
        # Scale back from T=60 baseline remaining decay: (30/90)^0.88 = 0.381
        time_decay = (30.0 / 90.0) ** 0.88
        implied_pre_lambda = true_lambda_rem / time_decay
        
        # Generate xG & xGOT centered around implied_pre_lambda * (60/90)
        exp_xg_total = implied_pre_lambda * (60.0 / 90.0)
        sim_xg_h = max(0.05, (exp_xg_total * 0.6) + np.random.normal(0, 0.08))
        sim_xg_a = max(0.05, (exp_xg_total * 0.4) + np.random.normal(0, 0.08))
        
        sim_xgot_h = sim_xg_h * np.random.uniform(0.70, 0.95)
        sim_xgot_a = sim_xg_a * np.random.uniform(0.70, 0.95)

        # 5. GoalEngine Pricing & Diagnostics
        heat_h, heat_a, _, _ = engine.get_goal_heat(
            time_t=60, use_advanced=True,
            home_xg=sim_xg_h, away_xg=sim_xg_a,
            home_xgot=sim_xgot_h, away_xgot=sim_xgot_a,
            home_sot=3, away_sot=2
        )
        
        engine_lambdas = engine.calculate_remaining_lambda(
            time_t=60, heat_h=heat_h, heat_a=heat_a,
            home_goals=current_goals, away_goals=0
        )
        
        engine_ev_results = engine.calculate_ev(
            live_goal_line=live_goal_line,
            current_goals=current_goals,
            lambda_rem=engine_lambdas["lambda_rem"],
            odds_under=offered_odds_under,
            odds_over=offered_odds_over
        )
        
        model_flagged_over = engine_ev_results["ev_over"] > 0.15

        # 6. Matrix Accumulation
        if model_flagged_over and is_true_plus_ev_over:
            true_positives += 1
        elif model_flagged_over and not is_true_plus_ev_over:
            false_positives += 1
        elif not model_flagged_over and not is_true_plus_ev_over:
            true_negatives += 1
        elif not model_flagged_over and is_true_plus_ev_over:
            false_negatives += 1

    # 7. Diagnostic Summary Output
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0

    print("=======================================================")
    print(f"📊 CORRECTED MONTE CARLO TEST RESULTS ({n_sims} Iterations)")
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
    run_corrected_monte_carlo_test()