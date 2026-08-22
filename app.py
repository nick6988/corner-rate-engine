import streamlit as st
from corner_engine import CornerEngine
from league_filter import LeagueCategorizer

# -----------------------------------------------------------------------------
# 1. Page Configuration & Custom CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="In-Play Corner Rate Engine (+EV)",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E293B; margin-bottom: 0rem; }
    .sub-header { font-size: 1.0rem; color: #64748B; margin-bottom: 1.5rem; }
    .card-title { font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase; }
    .card-value { font-size: 1.8rem; font-weight: 700; color: #0F172A; }
    .signal-box-green { background-color: #DCFCE7; border-left: 5px solid #16A34A; padding: 1rem; border-radius: 6px; margin-bottom: 0.5rem; }
    .signal-box-red { background-color: #FEE2E2; border-left: 5px solid #DC2626; padding: 1rem; border-radius: 6px; margin-bottom: 0.5rem; }
    .signal-box-gray { background-color: #F1F5F9; border-left: 5px solid #94A3B8; padding: 1rem; border-radius: 6px; margin-bottom: 0.5rem; }
    .signal-title { font-size: 1.1rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">⚽ In-Play Corner Rate Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Quantitative Poisson/Negative Binomial (+EV) Live Match Pricing & Risk Control</p>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Sidebar: Match Priors & Setup
# -----------------------------------------------------------------------------

st.sidebar.header("📋 Match Setup (Priors)")

display_options = LeagueCategorizer.get_all_display_names()

default_target = "英超 | English Premier League"
default_idx = display_options.index(default_target) if default_target in display_options else 0

selected_display = st.sidebar.selectbox(
    "League / 聯賽賽事",
    display_options,
    index=default_idx
)

# Custom League Fallback Logic
if "Custom League" in selected_display:
    custom_name = st.sidebar.text_input("Enter League Name (聯賽名稱)", value="Custom League")
    league_tier = st.sidebar.selectbox(
        "Assign Risk Tier (風控層級)",
        ["ALLOWED", "NO_UNDER", "BANNED"],
        index=0,
        help="ALLOWED: Normal | NO_UNDER: Block Under | BANNED: Block All"
    )
    selected_league_key = custom_name
else:
    selected_league_key = selected_display.split(" | ")[-1] if " | " in selected_display else selected_display
    league_tier = LeagueCategorizer.get_tier(selected_league_key)

# Display league tier badge
if league_tier == "ALLOWED":
    st.sidebar.success("Risk Tier: ALLOWED (Standard Trading)")
elif league_tier == "NO_UNDER":
    st.sidebar.warning("Risk Tier: NO_UNDER (Under Trades Prohibited)")
else:
    st.sidebar.error("Risk Tier: BANNED (Trading Suspended)")

st.sidebar.divider()

pre_match_line = st.sidebar.number_input("Pre-Match Corner Line", min_value=5.5, max_value=14.5, value=9.5, step=0.5)
asian_handicap = st.sidebar.slider("Home Asian Handicap", min_value=-2.5, max_value=2.5, value=-0.75, step=0.25)
tournament_type = st.sidebar.selectbox("Tournament Format", CornerEngine.VALID_TOURNAMENT_TYPES, index=0)

leg1_home_goals, leg1_away_goals = 0, 0
if tournament_type == "Knockout_Leg2":
    st.sidebar.subheader("First Leg Result")
    leg1_home_goals = st.sidebar.number_input("Leg 1 Home Goals", min_value=0, max_value=10, value=0)
    leg1_away_goals = st.sidebar.number_input("Leg 1 Away Goals", min_value=0, max_value=10, value=0)

# --- Add / Manage Leagues Expander in Streamlit Sidebar ---
with st.sidebar.expander("➕ Add / Edit League (新增或修改聯賽)"):
    with st.form("add_league_form"):
        new_eng_name = st.text_input("English League Name (例如: Saudi Pro League)")
        new_zh_name = st.text_input("Chinese Name (例如: 沙特聯)")
        new_tier = st.selectbox(
            "Select Risk Tier (選擇風控層級)",
            ["ALLOWED", "NO_UNDER", "BANNED"]
        )
        submit_btn = st.form_submit_button("Save League")

        if submit_btn:
            if new_eng_name:
                LeagueCategorizer.add_or_update_league(new_eng_name, new_zh_name, new_tier)
                st.success(f"Saved: {new_eng_name} ({new_tier})")
                st.rerun()
            else:
                st.error("English League Name is required.")

# Instantiate Engine
engine = CornerEngine(
    pre_match_line=pre_match_line,
    asian_handicap=asian_handicap,
    tournament_type=tournament_type,
    leg1_home_goals=leg1_home_goals,
    leg1_away_goals=leg1_away_goals
)

# -----------------------------------------------------------------------------
# 3. Main Interface: Live Match Input & Output Dashboard
# -----------------------------------------------------------------------------
tab_live, tab_rules = st.tabs(["📊 Live Match Telemetry", "📖 Model Rules & Formula References"])

with tab_live:
    col_input, col_output = st.columns([1, 1], gap="large")

    # --- INPUT COLUMN ---
    with col_input:
        st.subheader("⚙️ Live Telemetry Input")

        col_time, col_score1, col_score2 = st.columns(3)
        with col_time:
            time_t = st.number_input("Elapsed Minute (T)", min_value=0, max_value=90, value=60, step=1)
        with col_score1:
            home_goals = st.number_input("Home Goals", min_value=0, max_value=15, value=0)
        with col_score2:
            away_goals = st.number_input("Away Goals", min_value=0, max_value=15, value=1)

        col_shot1, col_shot2 = st.columns(2)
        with col_shot1:
            total_shots = st.number_input("Total Shots (Both Teams)", min_value=0, max_value=60, value=15)
        with col_shot2:
            shots_on_target = st.number_input("Shots on Target", min_value=0, max_value=30, value=5)

        col_corn1, col_corn2 = st.columns(2)
        with col_corn1:
            current_corners = st.number_input("Current Corner Count", min_value=0, max_value=30, value=5)
        with col_corn2:
            rolling_10m = st.number_input("Corners (Last 10 Mins)", min_value=0, max_value=15, value=2)

        red_card_status = st.selectbox("Red Card Status", CornerEngine.VALID_RED_CARD_STATUSES, index=0)

        st.divider()
        st.subheader("💰 Live Bookmaker Market")

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            live_line = st.number_input("Live Corner Line", min_value=float(current_corners), max_value=25.0, value=max(7.5, float(current_corners) + 0.5), step=0.5)
        with col_m2:
            odds_under = st.number_input("Under Odds", min_value=1.01, max_value=10.0, value=1.85, step=0.05)
        with col_m3:
            odds_over = st.number_input("Over Odds", min_value=1.01, max_value=10.0, value=1.95, step=0.05)

    # --- CALCULATIONS ---
    shot_heat = engine.get_shot_heat(time_t, total_shots, shots_on_target)
    score_mod = engine.get_score_modifier(time_t, home_goals, away_goals)
    red_card_mod = engine.get_red_card_modifier(red_card_status)
    composite_m = engine.get_composite_momentum(time_t, current_corners, rolling_10m)

    lambda_rem = engine.calculate_remaining_lambda(
        time_t=time_t,
        current_corners=current_corners,
        total_shots=total_shots,
        shots_on_target=shots_on_target,
        home_goals=home_goals,
        away_goals=away_goals,
        rolling_10m_corners=rolling_10m,
        red_card_status=red_card_status
    )

    ev_results = engine.calculate_ev(
        live_line=live_line,
        current_corners=current_corners,
        lambda_rem=lambda_rem,
        odds_under=odds_under,
        odds_over=odds_over
    )

    signals = engine.get_signal_diagnostics(
        time_t=time_t,
        live_line=live_line,
        current_corners=current_corners,
        odds_under=odds_under,
        odds_over=odds_over,
        ev_results=ev_results,
        league_tier=league_tier,
        rolling_10m_corners=rolling_10m
    )

    # --- OUTPUT COLUMN ---
    with col_output:
        st.subheader("🎯 Quantitative Engine Outputs")

        # Metric Row 1: Key Factors
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Shot Heat", f"{shot_heat:.2f}")
        m2.metric("Score Mod", f"{score_mod:.2f}")
        m3.metric("Momentum (P)", f"{composite_m:.2f}")
        m4.metric("λ (Remaining)", f"{lambda_rem:.2f}")

        st.divider()

        # Metric Row 2: Pricing & EV
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Under Prob", f"{ev_results['prob_under']:.1%}")
        p2.metric("Under EV", f"{ev_results['ev_under']:+.1%}", delta_color="normal")
        p3.metric("Over Prob", f"{ev_results['prob_over']:.1%}")
        p4.metric("Over EV", f"{ev_results['ev_over']:+.1%}", delta_color="normal")

        st.divider()
        st.subheader("🚦 Trading Signal Diagnostics")

        # --- Under Signal Card & Diagnostic Expander ---
        u_sig = signals["under_signal"]
        if "SNIPER UNDER" in u_sig:
            st.markdown(f'<div class="signal-box-green"><p class="signal-title">{u_sig}</p></div>', unsafe_allow_html=True)
        elif "⛔" in u_sig:
            st.markdown(f'<div class="signal-box-red"><p class="signal-title">{u_sig}</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="signal-box-gray"><p class="signal-title">{u_sig}</p></div>', unsafe_allow_html=True)

        if signals["under_checks"] and league_tier != "NO_UNDER":
            with st.expander("🔍 Under Signal Qualification Breakdown"):
                for criterion, (passed, val) in signals["under_checks"].items():
                    icon = "✅" if passed else "❌"
                    st.write(f"{icon} **{criterion}**: `{val}`")

        # --- Over Signal Card & Diagnostic Expander ---
        o_sig = signals["over_signal"]
        if "SNIPER OVER" in o_sig:
            st.markdown(f'<div class="signal-box-green"><p class="signal-title">{o_sig}</p></div>', unsafe_allow_html=True)
        elif "CIRCUIT BREAKER" in o_sig or "⛔" in o_sig:
            st.markdown(f'<div class="signal-box-red"><p class="signal-title">{o_sig}</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="signal-box-gray"><p class="signal-title">{o_sig}</p></div>', unsafe_allow_html=True)

        if signals["over_checks"]:
            with st.expander("🔍 Over Signal Qualification Breakdown"):
                for criterion, (passed, val) in signals["over_checks"].items():
                    icon = "✅" if passed else "❌"
                    st.write(f"{icon} **{criterion}**: `{val}`")
        
# -----------------------------------------------------------------------------
# 4. Tab 2: Documentation & Rule References
# -----------------------------------------------------------------------------
with tab_rules:
    st.markdown("""
    ### 📌 Hard In-Play Risk Control Rules
    1. **Pre-Match Baseline Constraint**: Applicable strictly to matches with pre-match corner line.
       - **Under Trades**: Only allowed if pre-match line ≤ 9.5.
       - **Over Trades**: Only allowed if pre-match line ≤ 10.5.
    2. **Observation Windows**:
       - **Sniper Under**: T ∈ [55, 68] minutes.
       - **Sniper Over**: T ∈ [25, 38] minutes or T ∈ [55, 78] minutes.
    3. **Under Entry Thresholds**:
       - Time Window: 55–68 Mins.
       - Composite Momentum (P) ≤ 0.50.
       - Under Buffer (Live Line - Current Corners) ≥ 2.5.
       - Odds ≥ 1.65 and Expected Value (+EV) > +15%.
    4. **Over Entry Thresholds**:
       - Time Window: 25–38 Mins or 55–78 Mins (Odds ≥ 1.80 required after T ≥ 70).
       - Composite Momentum (P) ≥ 1.35 for T < 55, ≥ 1.15 for T ≥ 55.
       - Expected Value (+EV) > +15%.
    5. **Circuit Breaker Fuse**: Blocks Over trades if live line ≥ 14.5 or live line exceeds pre-match line by ≥ 5.0 corners (waived only during T ∈ [55, 68] outburst windows with P ≥ 1.50).
    6. **League Filter Rules**:
       - **Banned**: South American domestic leagues (Suspended).
       - **No-Under**: High variance leagues (Eastern/Northern Europe, MLS, A-League). Under trades strictly prohibited.
    """)