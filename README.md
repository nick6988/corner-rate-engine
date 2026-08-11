# ⚽ Quantitative In-Play Corner Rate Engine

A real-time quantitative sports trading and risk management engine designed to identify Expected Value (+EV) mispricings in live football corner markets. Powered by a Negative Binomial probability distribution model and an interactive Streamlit frontend.

---

## 🌟 Key Features

* **Statistical Pricing Engine**: Uses Negative Binomial distribution (`scipy.stats.nbinom`, $r=12$) over standard Poisson to capture variance, clustering, and tail risk in corner counts.
* **Non-Linear Time Decay**: Models remaining corner intensity ($\lambda_{rem}$) using a non-linear $t^{0.85}$ decay function combined with live momentum rates ($P$).
* **Tactical Score & Heat Modifiers**: Dynamically adjusts expected rates based on shot heat (total vs. target shots), goal-line margins, aggregate leg scores, and red card impact.
* **Automated Trading Diagnostics**: Triggers **Sniper Over** / **Sniper Under** signals only when strict $+EV$ (>15%), time window, momentum ($P$), and line buffer conditions are met.
* **Dynamic League Risk Tiers**: Persistent JSON storage (`leagues.json`) enforcing 3-tier risk control:
  * `ALLOWED`: Full trading.
  * `NO_UNDER`: Prohibits Under trades in high-variance leagues (e.g., MLS, Eredivisie, Scandinavian divisions).
  * `BANNED`: Suspends trading on volatile markets (e.g., South American domestic leagues).
* **Interactive Dashboard**: Full Streamlit interface featuring dynamic metric cards, pass/fail signal breakdowns, and real-time league tier management.

---

## 🛠️ Tech Stack

* **Language**: Python 3.10+
* **Data & Analytics**: SciPy, NumPy
* **Frontend**: Streamlit
* **Persistence**: JSON (`leagues.json`)
* **Version Control**: Git / GitHub

---

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/nick6988/corner-rate-engine.git
cd corner-rate-engine
```

### 2. Set Up Environment & Install Dependencies
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Launch Streamlit Dashboard
```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## 📂 Project Architecture

```text
├── app.py               # Streamlit dashboard & UI logic
├── corner_engine.py     # Quantitative engine & probability calculation core
├── league_filter.py     # Dynamic JSON reader/writer for league risk tiers
├── leagues.json         # Storage file for league translations and risk tiers
├── requirements.txt     # Python package dependencies
└── .gitignore           # Git exclusion rules
```
