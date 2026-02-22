🐉 DragonPulse — Predictive Supply Chain Auditor

DragonPulse is a hands-on MVP I built to study how external disruption signals can be converted into operational risk indicators for supply chain decision-making.

The system ingests public logistics/news feeds, extracts risk events, maps them to regions/ports, and estimates delay impact through a lightweight ML model.
It is designed as a demo-ready research prototype, not a production product.

1. Why I built this
In real supply chains, disruptions appear in open signals (weather reports, customs incidents, shipping congestion) before they show up in ERP dashboards.
I wanted to build a small control-tower system that can:

1)detect these early signals
2)convert them into numeric risk (risk_score)
3)estimate delay impact
4)provide actionable outputs in a simple dashboard.

2. What currently works

1)RSS ingestion + relevance filtering for supply-chain topics
2)Rule-based risk extraction with deterministic fallback behavior
3)Source typing (news, weather, port_index, customs_notice)
4)Region/port mapping (Shanghai, Ningbo, Other-China, Global, Unknown)
5)Composite risk scoring endpoint
6)Delay prediction model (with rolling backtest)
7)Streamlit dashboard (news intelligence, simulator, event journal)
8)SQLite event logging

3. Implementation notes (important)

This project was built iteratively with local debugging on Windows.
Key fixes completed during implementation:

1)fixed UnboundLocalError in the risk scoring path (score variable case),
2)fixed geo mapping edge cases (Hong Kong and Zhonggu now map to China/Other-China),
3)improved source-type classification (weather no longer falls into generic news),
4)stabilized API/Streamlit behavior under timeout and fallback scenarios.


4. High-level architecture

[RSS/Open Feeds]
      ↓
[Ingestion + Normalization + Dedup]
      ↓
[Risk Engine: rules (+ optional LLM)]
      ├─ source_type
      ├─ matched_events
      ├─ risk_score
      └─ region/port mapping
      ↓
[SQLite Event Journal]
      ↓
[Composite Risk + Delay Predictor]
      ↓
[FastAPI Endpoints]
      ↓
[Streamlit Control Tower]

5. Tech stack

1)API: FastAPI, Uvicorn
2)Dashboard: Streamlit
3)Data/NLP: pandas, numpy, feedparser, requests
4)ML: scikit-learn, joblib
5)Storage: SQLite
6)Optional LLM: DeepSeek / Qwen-compatible endpoint

6. Project structure
DragonPulse/
├─ app/
│  ├─ api/
│  ├─ dashboard/
│  ├─ ingestion/
│  ├─ nlp/
│  ├─ ml/
│  └─ main.py
├─ data/
├─ artifacts/
├─ .env.example
├─ requirements.txt
└─ README.md

7. Setup (Windows, PowerShell)
1) Create and activate environment

cd C:\Users\магамед\DragonPulse
python -m venv .venv
.\.venv\Scripts\Activate.ps1

If script execution is blocked:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

2) Install dependencies

pip install -r requirements.txt

8. Run the system
Start API
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

API: http://127.0.0.1:8000

Docs: http://127.0.0.1:8000/docs

9. Start Dashboard (new terminal)

cd C:\Users\магамед\DragonPulse
.\.venv\Scripts\Activate.ps1
python -m streamlit run app/dashboard/streamlit_app.py

Dashboard: http://localhost:8501


10. Quick API checks

Health
http://127.0.0.1:8000/api/health

Live feed (rules mode)
http://127.0.0.1:8000/api/news-risk/live?use_llm=false&max_items=8

Mock feed
http://127.0.0.1:8000/api/news-risk/mock?use_llm=false

Event journal
http://127.0.0.1:8000/api/risk/events?limit=20

Backtest summary
http://127.0.0.1:8000/api/risk/backtest-summary

11. Train + backtest (delay model)
python -m app.ml.generate_synthetic_data --rows 500 --seed 7
python -m app.ml.train_delay_model --csv data/port_delay_training.csv
python -m app.ml.backtest_delay_model --csv data/port_delay_training.csv


12. Artifacts generated in artifacts/:

1) delay_model.joblib
2) delay_model_meta.json
3) backtest_results.csv
4) backtest_summary.json


13. Current quantitative result

From rolling backtest:

1)Baseline MAE: 15.0034
2)ML MAE: 1.6829
3)Improvement: 88.78%
This confirms the ML predictor is materially better than the baseline heuristic in this MVP setup.


14. Optional LLM mode

If configured in .env:

LLM_PROVIDER=deepseek
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat


Then:
/api/news-risk/live?use_llm=true&max_items=6

If LLM auth/network fails, the pipeline should fall back to rules mode.

15. Known limitations

1)Part of training data is still proxy/hybrid (not full production ERP history)
2)Port mapping is good for key cases, but not complete for all lanes
3)Source coverage should be expanded with more official operational feeds
4)MLOps layer (drift detection/retraining policy) is still basic

16. Next steps

5)integrate real ERP transaction streams
4)enrich bilingual event ontology (CN/EN)
3)improve lane-level port mapping granularity
2)add drift monitoring + retrain triggers
1)improve explainability in dashboard outputs

17. License

Academic / research prototype.