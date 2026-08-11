import random
from corner_engine import CornerEngine
from league_filter import LeagueCategorizer


def run_fuzz_test(num_scenarios: int = 1000):
    print(f"🚀 Starting Fuzz Engine Test ({num_scenarios:,} scenarios)...\n")

    leagues = [
        "English Premier League", "Spanish La Liga", "German Bundesliga",
        "Australian A-League", "Dutch Eredivisie", "Brazilian Serie A", "Argentine Primera"
    ]

    stats = {
        "total": 0,
        "under_signals": 0,
        "over_signals": 0,
        "circuit_breakers": 0,
        "league_blocks": 0
    }

    for i in range(1, num_scenarios + 1):
        time_t = random.randint(0, 90)
        pre_line = random.choice([8.5, 9.5, 10.5, 11.5])
        current_corners = random.randint(0, int(pre_line + 5))
        rolling_5m = random.randint(0, min(current_corners, 4)) if time_t >= 5 else None

        league_name = random.choice(leagues)
        league_tier = LeagueCategorizer.get_tier(league_name)

        engine = CornerEngine(
            pre_match_line=pre_line,
            asian_handicap=random.choice([-1.0, -0.75, 0.0, 0.75, 1.0]),
            tournament_type=random.choice(["League", "Cup_Final", "Knockout_Leg1", "Knockout_Leg2"])
        )

        lambda_rem = engine.calculate_remaining_lambda(
            time_t=time_t,
            current_corners=current_corners,
            total_shots=random.randint(0, 30),
            shots_on_target=random.randint(0, 12),
            home_goals=random.randint(0, 4),
            away_goals=random.randint(0, 4),
            rolling_5m_corners=rolling_5m,
            red_card_status=random.choice(["None", "Underdog_Red", "Favorite_Red"])
        )

        live_line = float(current_corners) + random.choice([0.5, 1.5, 2.5, 3.5])
        ev_res = engine.calculate_ev(
            live_line=live_line,
            current_corners=current_corners,
            lambda_rem=lambda_rem,
            odds_under=round(random.uniform(1.60, 2.20), 2),
            odds_over=round(random.uniform(1.60, 2.20), 2)
        )

        signals = engine.get_signal_diagnostics(
            time_t=time_t,
            live_line=live_line,
            current_corners=current_corners,
            odds_under=1.80,
            odds_over=1.80,
            ev_results=ev_res,
            league_tier=league_tier,
            rolling_5m_corners=rolling_5m
        )

        # Aggregate stats
        stats["total"] += 1
        if "SNIPER UNDER" in signals["under_signal"]:
            stats["under_signals"] += 1
        if "SNIPER OVER" in signals["over_signal"]:
            stats["over_signals"] += 1
        if "CIRCUIT BREAKER" in signals["over_signal"]:
            stats["circuit_breakers"] += 1
        if "BANNED LEAGUE" in signals["under_signal"] or "NO-UNDER LEAGUE" in signals["under_signal"]:
            stats["league_blocks"] += 1

        # Print progress every 100 runs
        if i % 100 == 0 or i == num_scenarios:
            print(f"Progress: [{i:>4d}/{num_scenarios}] | Under Signals: {stats['under_signals']:>2d} | Over Signals: {stats['over_signals']:>2d} | Circuit Breakers: {stats['circuit_breakers']:>2d}")

    print("\n" + "="*50)
    print("📊 FUZZ TESTING SUMMARY REPORT")
    print("="*50)
    print(f"Total Scenarios Evaluated: {stats['total']:,}")
    print(f"Sniper Under Signals (+EV): {stats['under_signals']} ({stats['under_signals']/stats['total']:.1%})")
    print(f"Sniper Over Signals (+EV):  {stats['over_signals']} ({stats['over_signals']/stats['total']:.1%})")
    print(f"Circuit Breakers Triggered: {stats['circuit_breakers']} ({stats['circuit_breakers']/stats['total']:.1%})")
    print(f"League Filter Interventions: {stats['league_blocks']} ({stats['league_blocks']/stats['total']:.1%})")
    print("="*50)


if __name__ == "__main__":
    run_fuzz_test(1000)