import streamlit as st
from corner_engine import CornerEngine
from goal_engine import GoalEngine
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
pre_match_goal_line = st.sidebar.number_input("Pre-Match Goal Line (全場大小球)", min_value=1.5, max_value=5.5, value=2.5, step=0.25)
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
corner_eng = CornerEngine(
    pre_match_line=pre_match_line,
    asian_handicap=asian_handicap,
    tournament_type=tournament_type,
    leg1_home_goals=leg1_home_goals,
    leg1_away_goals=leg1_away_goals
)

goal_eng = GoalEngine(
    pre_match_goal_line=pre_match_goal_line,
    asian_handicap=asian_handicap
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

        # --- 2. 射門與進攻數據輸入區 (SofaScore / Flashscore 雙模態輸入) ---
        with st.container(border=True):
            use_advanced = st.toggle("🚀 啟用高級遙測 (SofaScore xG/xGOT & Box Stats)", value=True)
            
            if use_advanced:
                st.caption("🔍 **Advanced Mode**: Enter Independent xG, xGOT, and Box Score Metrics for Home & Away Teams")
                col_h1, col_h2, col_h3 = st.columns(3)
                with col_h1:
                    home_xg = st.number_input("Home xG", min_value=0.0, max_value=10.0, value=1.0, step=0.05)
                with col_h2:
                    home_xgot = st.number_input("Home xGOT", min_value=0.0, max_value=10.0, value=1.0, step=0.05)
                with col_h3:
                    home_sot = st.number_input("Home SoT", min_value=0, max_value=30, value=2)
                    

                col_a1, col_a2, col_a3 = st.columns(3)
                with col_a1:
                    away_xg = st.number_input("Away xG", min_value=0.0, max_value=10.0, value=1.0, step=0.05)
                with col_a2:
                    away_xgot = st.number_input("Away xGOT", min_value=0.0, max_value=10.0, value=1.0, step=0.05)
                with col_a3:
                    away_sot = st.number_input("Away SoT", min_value=0, max_value=30, value=2)

                col_sot1, col_sot2 = st.columns(2)
                with col_sot1:
                    shots_inside_box = st.number_input("Shots Inside Box", min_value=0, max_value=60, value=8)
                with col_sot2:
                    blocked_shots = st.number_input("Blocked Shots", min_value=0, max_value=30, value=4)

                # 安全賦予 Basic 模式預設值 (避免 NameError)
                home_shots, away_shots, home_da, away_da = 0, 0, 0, 0

            else:
                st.caption("⚡ **Basic Mode**: Enter Total Shots, Shots on Target (SoT), and Dangerous Attacks for Home & Away Teams")
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    home_shots = st.number_input("Home Total Shots", min_value=0, max_value=60, value=5)
                with col_b2:
                    home_sot = st.number_input("Home SoT", min_value=0, max_value=30, value=2)
                with col_b3:
                    home_da = st.number_input("Home Dangerous Attacks", min_value=0, max_value=200, value=50)

                col_b4, col_b5, col_b6 = st.columns(3)
                with col_b4:
                    away_shots = st.number_input("Away Total Shots", min_value=0, max_value=60, value=5)
                with col_b5:
                    away_sot = st.number_input("Away SoT", min_value=0, max_value=30, value=2)
                with col_b6:
                    away_da = st.number_input("Away Dangerous Attacks", min_value=0, max_value=200, value=50)

                # 安全賦予 Advanced 模式預設值 (避免 NameError)
                home_xg, away_xg, home_xgot, away_xgot = 0.0, 0.0, 0.0, 0.0
                shots_inside_box, blocked_shots = 0, 0

        # --- 3. 角球與紅牌數據 ---
        col_corn1, col_corn2 = st.columns(2)
        with col_corn1:
            current_corners = st.number_input("Current Corner Count", min_value=0, max_value=30, value=5)
        with col_corn2:
            rolling_10m = st.number_input("Corners (Last 10 Mins)", min_value=0, max_value=15, value=2)

        red_card_status = st.selectbox("Red Card Status", CornerEngine.VALID_RED_CARD_STATUSES, index=0)

        st.divider()
        st.subheader("💰 Live Corner Market")

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            live_line = st.number_input("Live Corner Line", min_value=float(current_corners), max_value=25.0, value=max(7.5, float(current_corners) + 0.5), step=0.5)
        with col_m2:
            odds_under = st.number_input("Corner Under Odds", min_value=1.01, max_value=10.0, value=1.85, step=0.05)
        with col_m3:
            odds_over = st.number_input("Corner Over Odds", min_value=1.01, max_value=10.0, value=1.95, step=0.05)

        # 🔥 NEW: Live Goal Bookmaker Market Entries
        st.subheader("⚽ Live Goal Market")
        col_g1, col_g2, col_g3 = st.columns(3)
        current_total_goals = home_goals + away_goals

        with col_g1:
            live_goal_line = st.number_input("Live Goal Line", min_value=float(current_total_goals), max_value=15.0, value=max(2.5, float(current_total_goals) + 0.5), step=0.25)
        with col_g2:
            goal_odds_under = st.number_input("Goal Under Odds", min_value=1.01, max_value=10.0, value=1.85, step=0.05)
        with col_g3:
            goal_odds_over = st.number_input("Goal Over Odds", min_value=1.01, max_value=10.0, value=1.95, step=0.05)

    # -------------------------------------------------------------------------
    # CALCULATIONS PIPELINE
    # -------------------------------------------------------------------------
    # 1. Corner Engine Calculations (加總主客數據以完全兼容舊角球邏輯)
    total_sot = home_sot + away_sot
    total_shots = home_shots + away_shots

    if use_advanced:
        corner_shot_heat = corner_eng.get_advanced_corner_heat(
            time_t=time_t,
            shots_inside_box=shots_inside_box,
            blocked_shots=blocked_shots,
            shots_on_target=total_sot
        )
    else:
        corner_shot_heat = corner_eng.get_shot_heat(time_t, total_shots, total_sot)

    corner_composite_m = corner_eng.get_composite_momentum(time_t, current_corners, rolling_10m)
    corner_lambda_rem = corner_eng.calculate_remaining_lambda(
        time_t=time_t,
        current_corners=current_corners,
        shot_heat=corner_shot_heat,
        home_goals=home_goals,
        away_goals=away_goals,
        rolling_10m_corners=rolling_10m,
        red_card_status=red_card_status
    )
    corner_ev = corner_eng.calculate_ev(
        live_line=live_line,
        current_corners=current_corners,
        lambda_rem=corner_lambda_rem,
        odds_under=odds_under,
        odds_over=odds_over,
        time_t=time_t,
        composite_m=corner_composite_m
    )
    corner_signals = corner_eng.get_signal_diagnostics(
        time_t=time_t,
        live_line=live_line,
        current_corners=current_corners,
        odds_under=odds_under,
        odds_over=odds_over,
        ev_results=corner_ev,
        league_tier=league_tier,
        rolling_10m_corners=rolling_10m
    )

    # 2. Goal Engine Calculations (主客完全分立運算)
    heat_h, heat_a, fault_h, fault_a = goal_eng.get_goal_heat(
        time_t=time_t,
        use_advanced=use_advanced,
        home_xg=home_xg, away_xg=away_xg,
        home_xgot=home_xgot, away_xgot=away_xgot,
        home_shots=home_shots, away_shots=away_shots,
        home_sot=home_sot, away_sot=away_sot,
        home_da=home_da, away_da=away_da
    )
    goal_lambdas = goal_eng.calculate_remaining_lambda(
        time_t=time_t,
        heat_h=heat_h, heat_a=heat_a,
        home_goals=home_goals, away_goals=away_goals,
        red_card_status=red_card_status
    )
    goal_ev = goal_eng.calculate_ev(
        live_goal_line=live_goal_line,
        current_goals=current_total_goals,
        lambda_rem=goal_lambdas["lambda_rem"],
        odds_under=goal_odds_under,
        odds_over=goal_odds_over
    )
    goal_signals = goal_eng.get_signal_diagnostics(
        time_t=time_t,
        live_goal_line=live_goal_line,
        current_goals=current_total_goals,
        odds_under=goal_odds_under,
        odds_over=goal_odds_over,
        ev_results=goal_ev,
        league_tier=league_tier
    )

    # -------------------------------------------------------------------------
    #                            OUTPUT DASHBOARD
    # -------------------------------------------------------------------------
    with col_output:
        st.subheader("🎯 Quantitative Outputs")

        tab_out_corner, tab_out_goal = st.tabs(["🚩 Corner Engine", "⚽ Goal Engine"])

        # --- CORNER ENGINE TAB ---
        with tab_out_corner:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Shot Heat", f"{corner_shot_heat:.2f}")
            m2.metric("Score Mod", f"{corner_eng.get_score_modifier(time_t, home_goals, away_goals):.2f}")
            m3.metric("Momentum (P)", f"{corner_composite_m:.2f}")
            m4.metric("λ (Corner Rem)", f"{corner_lambda_rem:.2f}")

            st.divider()

            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Under Prob", f"{corner_ev['prob_under']:.1%}")
            p2.metric("Under EV", f"{corner_ev['ev_under']:+.1%}")
            p3.metric("Over Prob", f"{corner_ev['prob_over']:.1%}")
            p4.metric("Over EV", f"{corner_ev['ev_over']:+.1%}")

            st.divider()

            u_sig = corner_signals["under_signal"]
            o_sig = corner_signals["over_signal"]

            if "SNIPER UNDER" in u_sig:
                st.markdown(f'<div class="signal-box-green"><p class="signal-title">{u_sig}</p></div>', unsafe_allow_html=True)
            elif "⛔" in u_sig:
                st.markdown(f'<div class="signal-box-red"><p class="signal-title">{u_sig}</p></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="signal-box-gray"><p class="signal-title">{u_sig}</p></div>', unsafe_allow_html=True)

            if "SNIPER OVER" in o_sig:
                st.markdown(f'<div class="signal-box-green"><p class="signal-title">{o_sig}</p></div>', unsafe_allow_html=True)
            elif "CIRCUIT BREAKER" in o_sig or "⛔" in o_sig:
                st.markdown(f'<div class="signal-box-red"><p class="signal-title">{o_sig}</p></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="signal-box-gray"><p class="signal-title">{o_sig}</p></div>', unsafe_allow_html=True)

            if corner_signals["under_checks"] and league_tier != "NO_UNDER":
                with st.expander("🔍 Corner Under Qualification Breakdown"):
                    for criterion, (passed, val) in corner_signals["under_checks"].items():
                        icon = "✅" if passed else "❌"
                        st.write(f"{icon} **{criterion}**: `{val}`")

            if corner_signals["over_checks"]:
                with st.expander("🔍 Corner Over Qualification Breakdown"):
                    for criterion, (passed, val) in corner_signals["over_checks"].items():
                        icon = "✅" if passed else "❌"
                        st.write(f"{icon} **{criterion}**: `{val}`")

        # --- GOAL ENGINE TAB ---
        with tab_out_goal:
            # 1. 終結能力故障警告 (Conversion Fault Risk Control)
            if fault_h:
                st.warning("⚠️ **Home Conversion Fault**: High xG but very low xGOT, shot heat penalized by 0.75x.")
            if fault_a:
                st.warning("⚠️ **Away Conversion Fault**: High xG but very low xGOT, shot heat penalized by 0.75x.")

            # 2. 主客獨立熱度與剩餘期望值 Metric
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("Home Heat", f"{heat_h:.2f}")
            g2.metric("Away Heat", f"{heat_a:.2f}")
            g3.metric("λ Home Rem", f"{goal_lambdas['lambda_home_rem']:.2f}")
            g4.metric("λ Away Rem", f"{goal_lambdas['lambda_away_rem']:.2f}")

            st.info(f"💡 **Total Remaining Expected Goals (λ Rem)**: `{goal_lambdas['lambda_rem']:.2f}`")

            st.divider()

            # 3. 大小球勝率與 +EV
            prob_u_eff = goal_ev.get("prob_under_eff", goal_ev.get("prob_under", 0.0))
            prob_o_eff = goal_ev.get("prob_over_eff", goal_ev.get("prob_over", 0.0))

            gp1, gp2, gp3, gp4 = st.columns(4)
            gp1.metric("Under Eff Prob", f"{prob_u_eff:.1%}")
            gp2.metric("Under EV", f"{goal_ev['ev_under']:+.1%}")
            gp3.metric("Over Eff Prob", f"{prob_o_eff:.1%}")
            gp4.metric("Over EV", f"{goal_ev['ev_over']:+.1%}")

            st.divider()

            # 4. 訊號卡片與條款檢查
            gu_sig = goal_signals["under_signal"]
            go_sig = goal_signals["over_signal"]

            if "GOAL SNIPER UNDER" in gu_sig:
                st.markdown(f'<div class="signal-box-green"><p class="signal-title">{gu_sig}</p></div>', unsafe_allow_html=True)
            elif "⛔" in gu_sig:
                st.markdown(f'<div class="signal-box-red"><p class="signal-title">{gu_sig}</p></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="signal-box-gray"><p class="signal-title">{gu_sig}</p></div>', unsafe_allow_html=True)

            if "GOAL SNIPER OVER" in go_sig:
                st.markdown(f'<div class="signal-box-green"><p class="signal-title">{go_sig}</p></div>', unsafe_allow_html=True)
            elif "⛔" in go_sig:
                st.markdown(f'<div class="signal-box-red"><p class="signal-title">{go_sig}</p></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="signal-box-gray"><p class="signal-title">{go_sig}</p></div>', unsafe_allow_html=True)

            if goal_signals["under_checks"] and league_tier != "NO_UNDER":
                with st.expander("🔍 Goal Under Signal Qualification Breakdown"):
                    for criterion, (passed, val) in goal_signals["under_checks"].items():
                        icon = "✅" if passed else "❌"
                        st.write(f"{icon} **{criterion}**: `{val}`")

            if goal_signals["over_checks"]:
                with st.expander("🔍 Goal Over Signal Qualification Breakdown"):
                    for criterion, (passed, val) in goal_signals["over_checks"].items():
                        icon = "✅" if passed else "❌"
                        st.write(f"{icon} **{criterion}**: `{val}`")
# -----------------------------------------------------------------------------
# 4. Tab 2: Documentation & Rule References
# -----------------------------------------------------------------------------

with tab_rules:
    st.markdown(r"""
    ## 📖 Quantitative Dual-Engine Framework & In-Play Risk Protocol

    This platform operates on a dual quantitative architecture: the **Corner Engine** utilizes a Negative Binomial distribution to capture high-frequency discrete events, while the **Goal Engine** implements a Time-Varying Non-Homogeneous Poisson Process (NHPP) with team-disaggregated $+EV$ pricing.

    ---

    ### 🚩 1. Corner Rate Engine Protocol

    #### **A. Pre-Match Baseline Constraints**
    * **Sniper Under**: Strictly restricted to matches with a pre-match corner line $\le 9.5$.
    * **Sniper Over**: Strictly restricted to matches with a pre-match corner line $\ge 9.5$.

    #### **B. Observation Windows & Entry Thresholds**
    * **Sniper Under**:
      * **Time Window**: $T \in [55, 68]$ minutes.
      * **Composite Momentum ($P$)**: $P \le 0.50$ (indicating low match and 10-min rolling corner pace).
      * **Corner Buffer**: $\text{Live Line} - \text{Current Corners} \ge 2.5$.
      * **Odds & EV**: Odds $\ge 1.65$ and Expected Value $+EV > +15\%$.
    * **Sniper Over**:
      * **Time Window**: $T \in [55, 78]$ minutes (Odds $\ge 1.80$ required when $T \ge 70$).
      * **Composite Momentum ($P$)**: $P \ge 1.15$ (indicating sustained siege pressure).
      * **Odds & EV**: Odds $\ge 1.65$ ($\ge 1.80$ for $T \ge 70$) and $+EV > +15\%$.

    #### **C. Circuit Breaker Fuse**
    * **Extreme Line Spike Fuse**: Automatically blocks Over trades if the live corner line reaches $\ge 14.5$ or exceeds the pre-match line by $\ge 5.0$ corners.
    * **Outburst Window Waiver**: Circuit breaker is waived strictly during $T \in [55, 68]$ if composite momentum $P \ge 1.50$ (extreme outburst).

    ---

    ### ⚽ 2. Goal Rate Engine Protocol (NHPP Model)

    #### **A. Telemetry Integrity & Conversion Fault Gate (xG vs xGOT Filter)**
    * **Volume & Quality Dual Calibration**: $xG$ represents spatial chance creation volume; $xGOT$ represents on-target finishing execution quality.
    * **Conversion Fault Gate**: Triggered when a team achieves $xG \ge 0.80$ but $\frac{xGOT}{xG} < 0.35$. This identifies "Finishing Conversion Faults / Shooting Noise", applying an automatic **$0.75\times$ penalty** to team goal heat to suppress false Over signals from ineffective siege.

    #### **B. Observation Windows & Entry Thresholds**
    * **Goal Sniper Under**:
      * **Time Window**: $T \in [50, 75]$ minutes.
      * **Goal Buffer**: $\text{Live Goal Line} - \text{Current Total Goals} \ge 1.25$ goals (split-line safety margin).
      * **Odds & EV**: Odds $\ge 1.65$ and $+EV > +15\%$.
    * **Goal Sniper Over**:
      * **Time Window**: $T \in [45, 80]$ minutes.
      * **Odds & EV**: Odds $\ge 1.65$ ($\ge 1.80$ for $T \ge 70$) and $+EV > +15\%$.

    #### **C. Tactical Game State & Asymmetric Red Card Modifiers**
    * **Blowout Rule**: Leads of $\ge 3$ goals trigger tactical cooldown, scaling goal expectation down to $0.65\times$ for both teams.
    * **Trailing Favorite ($\vert{}AH\vert{} \ge 0.75$)**: Trailing favorites receive a $1.35\times$ siege pressure multiplier; leading underdogs receive a $1.15\times$ counter-attack space multiplier.
    * **Asymmetric Red Card Effects**:
      * **Underdog Red**: Favorite receives a $1.35\times$ siege multiplier; underdog reduced to $0.60\times$.
      * **Favorite Red**: Favorite reduced to $0.75\times$; underdog receives a cautious $1.15\times$ multiplier.

    ---

    ### 🛡️ 3. League Risk Tier Protocol

    | Risk Tier | League Characteristics | Corner Engine Action | Goal Engine Action |
    | :--- | :--- | :--- | :--- |
    | **`ALLOWED`** | Top leagues with high telemetry integrity (Big 5, UEFA CL, J1/K1) | ✅ Standard Over/Under $+EV$ signals | ✅ Standard Over/Under $+EV$ signals |
    | **`NO_UNDER`** | High-variance leagues (MLS, A-League, Dutch Eerste Divisie, Cup Ties) | ⛔ **Under trades strictly prohibited** | ⛔ **Under trades strictly prohibited** |
    | **`BANNED`** | Telemetry distortion or integrity risks (South American leagues, Youth, Friendlies) | ⛔ **ALL trading strictly suspended** | ⛔ **ALL trading strictly suspended** |

    """)