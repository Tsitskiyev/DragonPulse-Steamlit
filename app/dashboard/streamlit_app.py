import streamlit as st
import requests
import pandas as pd
from datetime import datetime

API_BASE_DEFAULT = "http://127.0.0.1:8000/api"


# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="DragonPulse Control Tower",
    page_icon="🐉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Custom CSS
# -----------------------------
st.markdown(
    """
    <style>
    /* Надежные селекторы для Streamlit */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #0b1020 0%, #121a33 100%);
        color: #E6ECFF;
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    [data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    [data-testid="stSidebar"] * {
        color: #E6ECFF !important;
    }

    .block-container {
        padding-top: 1.1rem;
    }

    /* Карточки */
    .dp-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 16px;
        padding: 14px 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.24);
    }

    .dp-title {
        font-size: 1.55rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        color: #E6ECFF;
    }

    .dp-sub {
        color: #A9B7E8;
        margin-bottom: 0.9rem;
    }

    .risk-low { color: #4ADE80; font-weight: 700; }
    .risk-medium { color: #FACC15; font-weight: 700; }
    .risk-high { color: #F87171; font-weight: 700; }

    .small-muted {
        color: #9CA3AF;
        font-size: 0.85rem;
    }

    /* Чтобы табы и подписи не исчезали */
    [data-baseweb="tab"] {
        color: #E6ECFF !important;
    }

    label, p, span, div {
        color: inherit;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# -----------------------------
# Helpers
# -----------------------------
def safe_get(url: str, params=None, timeout=60):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ReadTimeout:
        return None, "ReadTimeout: API отвечает слишком долго. Уменьши max_items или выключи LLM."
    except requests.exceptions.ConnectionError:
        return None, "ConnectionError: API недоступен. Проверь, запущен ли uvicorn на 127.0.0.1:8000."
    except requests.exceptions.HTTPError as e:
        text = ""
        try:
            text = r.text[:350]
        except Exception:
            pass
        return None, f"HTTPError: {e}. {text}"
    except Exception as e:
        return None, f"Ошибка GET: {e}"


def safe_post(url: str, payload: dict, timeout=60):
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ReadTimeout:
        return None, "ReadTimeout: API отвечает слишком долго."
    except requests.exceptions.ConnectionError:
        return None, "ConnectionError: API недоступен. Проверь, запущен ли uvicorn на 127.0.0.1:8000."
    except requests.exceptions.HTTPError as e:
        text = ""
        try:
            text = r.text[:350]
        except Exception:
            pass
        return None, f"HTTPError: {e}. {text}"
    except Exception as e:
        return None, f"Ошибка POST: {e}"


def risk_html(level: str) -> str:
    lvl = (level or "").upper()
    if lvl == "LOW":
        return '<span class="risk-low">LOW</span>'
    if lvl == "MEDIUM":
        return '<span class="risk-medium">MEDIUM</span>'
    return '<span class="risk-high">HIGH</span>'


# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("## ⚙️ Параметры")
    api_base = st.text_input("API Base URL", value=API_BASE_DEFAULT)
    use_llm = st.toggle("Use LLM (DeepSeek or Qroq)", value=False)
    max_items = st.slider("Live News max_items", min_value=1, max_value=20, value=6, step=1)
    llm_limit = st.slider("LLM items limit", min_value=1, max_value=10, value=5, step=1)
    timeout_sec = st.slider("HTTP timeout (sec)", min_value=15, max_value=180, value=90, step=5)
    min_relevance = st.slider("Min relevance_score", 0.0, 1.0, 0.30, 0.05)
    min_impact = st.slider("Min impact_score", 0.0, 1.0, 0.20, 0.05)
    actionable_only = st.toggle("Actionable only", value=False)

    st.markdown("---")
    st.markdown("### Рекомендации (стабильный demo)")
    st.markdown("- Use LLM: **OFF**")
    st.markdown("- max_items: **3..6**")
    st.markdown("- timeout: **90 sec**")


# -----------------------------
# Header
# -----------------------------
st.markdown('<div class="dp-title">🐉 DragonPulse Control Tower</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="dp-sub">Predictive Supply Chain Auditor — News Intelligence • Delay Forecast • Composite Risk</div>',
    unsafe_allow_html=True
)

# -----------------------------
# KPI Row
# -----------------------------
k1, k2, k3, k4 = st.columns(4)

# API health
with k1:
    st.markdown('<div class="dp-card">', unsafe_allow_html=True)
    health, err = safe_get(f"{api_base}/health", timeout=timeout_sec)
    if err:
        st.metric("API Status", "DOWN")
        st.caption(err)
    else:
        st.metric("API Status", "UP")
        st.caption(health.get("service", "DragonPulse API"))
    st.markdown('</div>', unsafe_allow_html=True)

# Last event risk
with k2:
    st.markdown('<div class="dp-card">', unsafe_allow_html=True)
    ev1, err_ev1 = safe_get(f"{api_base}/risk/events", params={"limit": 1}, timeout=timeout_sec)
    if err_ev1 or not ev1 or ev1.get("count", 0) == 0:
        st.metric("Last Risk Score", "—")
        st.caption("Нет сохранённых событий")
    else:
        last_score = ev1["items"][0].get("risk_score", "—")
        st.metric("Last Risk Score", last_score)
        st.caption(f"Analyzer: {ev1['items'][0].get('analyzer', '—')}")
    st.markdown('</div>', unsafe_allow_html=True)

# Analyzer mode
with k3:
    st.markdown('<div class="dp-card">', unsafe_allow_html=True)
    st.metric("Mode", "LLM" if use_llm else "RULES")
    st.caption("Текущий режим анализа")
    st.markdown('</div>', unsafe_allow_html=True)

# Timestamp
with k4:
    st.markdown('<div class="dp-card">', unsafe_allow_html=True)
    st.metric("Updated", datetime.now().strftime("%H:%M:%S"))
    st.caption(datetime.now().strftime("%Y-%m-%d"))
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("")

# -----------------------------
# Tabs
# -----------------------------
tab_news, tab_risk, tab_events, tab_eval = st.tabs(["📰 News Intelligence", "📈 Composite Risk", "🗂 Event Journal", "🧪 Model Evaluation"])

with tab_eval:
    st.subheader("Rolling Backtest & Ablation")
    data, err = safe_get(f"{api_base}/risk/backtest-summary", timeout=timeout_sec)
    if err:
        st.error(err)
    else:
        if data.get("status") == "not_ready":
            st.warning(data.get("message"))
        else:
            st.success(f"Dataset rows: {data.get('dataset_rows')}")
            summary = data.get("summary", {})

            rows = []
            for k, v in summary.items():
                rows.append({
                    "variant": k,
                    "MAE": v.get("mae_mean"),
                    "RMSE": v.get("rmse_mean"),
                    "MAPE %": v.get("mape_mean_percent"),
                    "MAE improve vs baseline %": v.get("mae_improvement_vs_baseline_percent"),
                })

            df_eval = pd.DataFrame(rows).sort_values("MAE", ascending=True)
            st.dataframe(df_eval, use_container_width=True)

            if not df_eval.empty:
                st.markdown("**MAE by variant (lower is better)**")
                st.bar_chart(df_eval.set_index("variant")["MAE"])

# =============================
# TAB 1: News Intelligence
# =============================
with tab_news:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="dp-card">', unsafe_allow_html=True)
        st.subheader("Mock News (быстрый тест)")
        if st.button("Load Mock News", key="btn_mock", use_container_width=True):
            data, err = safe_get(
                f"{api_base}/news-risk/mock",
                params={"use_llm": use_llm,
                        "max_items": max_items,          # для live
                        "llm_limit": llm_limit,
                        "min_relevance": 0.0,
                        "min_impact": 0.0,
                        "actionable_only": False
                },
                timeout=timeout_sec
            )
            if err:
                st.error(err)
            else:
                df = pd.DataFrame(data.get("items", []))
                if df.empty:
                    st.info("Пустой ответ.")
                else:
                    show_cols = [c for c in ["title", "port", "risk_score", "relevance_score", "impact_score", "recommended_action" ,"analyzer", "published_at"] if c in df.columns]
                    st.dataframe(df[show_cols], use_container_width=True, height=380)

                                        # 1) Главный график: risk_score
                    if "risk_score" in df.columns and not df["risk_score"].isna().all():
                        st.markdown("**Risk trend (primary KPI):**")
                        st.line_chart(df["risk_score"].reset_index(drop=True))

                    # 2) Дополнительный график: impact_score (только один раз)
                    if "impact_score" in df.columns and not df["impact_score"].isna().all():
                        st.markdown("**Impact trend (secondary signal):**")
                        st.line_chart(df["impact_score"].reset_index(drop=True))

        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="dp-card">', unsafe_allow_html=True)
        st.subheader("Live RSS News")
        if st.button("Load Live News", key="btn_live", use_container_width=True):
            # llm_limit можно передавать, если API поддерживает; если нет — проигнорируется
            data, err = safe_get(
                f"{api_base}/news-risk/live",
                params={
                    "use_llm": use_llm,
                    "max_items": max_items,
                    "llm_limit": llm_limit,
                    "min_relevance":min_relevance,
                    "actionable_only":actionable_only
                },
                timeout=timeout_sec
            )
            if err:
                st.error(err)
            else:
                df = pd.DataFrame(data.get("items", []))
                if df.empty:
                    st.info("Live feed пустой/недоступен.")
                else:
                    # optional filters
                    if "port" in df.columns:
                        ports = ["All"] + sorted(df["port"].fillna("Unknown").unique().tolist())
                        selected_port = st.selectbox("Фильтр по порту", ports, key="port_filter_live")
                        if selected_port != "All":
                            df = df[df["port"] == selected_port]

                    if "analyzer" in df.columns:
                        analyzers = ["All"] + sorted(df["analyzer"].fillna("unknown").unique().tolist())
                        selected_an = st.selectbox("Фильтр по analyzer", analyzers, key="an_filter_live")
                        if selected_an != "All":
                            df = df[df["analyzer"] == selected_an]

                    show_cols = [c for c in ["title", "port", "risk_score", "relevance_score","impact_score", "recommended_action" ,"analyzer", "published_at"] if c in df.columns]
                    st.dataframe(df[show_cols], use_container_width=True, height=380)

                    # 1) Главный график: risk_score
                    if "risk_score" in df.columns and not df["risk_score"].isna().all():
                        st.markdown("**Risk trend (primary KPI):**")
                        st.line_chart(df["risk_score"].reset_index(drop=True))

                    # 2) Дополнительный график: impact_score (только один раз)
                    if "impact_score" in df.columns and not df["impact_score"].isna().all():
                        st.markdown("**Impact trend (secondary signal):**")
                        st.line_chart(df["impact_score"].reset_index(drop=True))


                    # Debug hint
                    if use_llm and "analyzer" in df.columns and (df["analyzer"] == "rules").all():
                        st.warning(
                            "LLM включён, но все записи = rules. "
                            "Значит сработал fallback (ключ/баланс/сеть/timeout)."
                        )
        st.markdown('</div>', unsafe_allow_html=True)


# =============================
# TAB 2: Composite Risk
# =============================
with tab_risk:
    # ВАЖНО: лучше убрать HTML div-обертки, чтобы Streamlit не ломался
    # st.markdown('<div class="dp-card">', unsafe_allow_html=True)

    st.subheader("Composite Risk Simulator")

    a, b, c = st.columns(3)
    with a:
        port = st.selectbox("Port", ["Shanghai", "Ningbo"], key="risk_port")
        queue_index = st.slider("Queue Index", 0.0, 1.0, 0.50, 0.01, key="risk_queue")
        backlog_index = st.slider("Backlog Index", 0.0, 1.0, 0.50, 0.01, key="risk_backlog")

    with b:
        weather_risk = st.slider("Weather Risk", 0.0, 1.0, 0.40, 0.01, key="risk_weather")
        news_risk = st.slider("News Risk", 0.0, 1.0, 0.50, 0.01, key="risk_news")
        ops_risk = st.slider("Ops Risk (ERP)", 0.0, 1.0, 0.40, 0.01, key="risk_ops")

    with c:
        st.markdown("<br>", unsafe_allow_html=True)
        run_calc = st.button("Compute Composite Risk", use_container_width=True, key="btn_compute")

    if run_calc:
        payload = {
            "port": port,
            "queue_index": queue_index,
            "weather_risk": weather_risk,
            "news_risk": news_risk,
            "backlog_index": backlog_index,
            "ops_risk": ops_risk,
        }

        out, err = safe_post(f"{api_base}/risk/aggregate", payload=payload, timeout=timeout_sec)
        if err:
            st.error(err)
        else:
            # KPI row
            m1, m2, m3 = st.columns(3)
            m1.metric("Predicted Delay (hours)", out.get("predicted_delay_hours", "—"))
            m2.metric("Composite Risk Score", out.get("composite_risk_score", "—"))
            m3.markdown(
                f"### Risk Level: {risk_html(out.get('risk_level', 'HIGH'))}",
                unsafe_allow_html=True
            )

            # --- NEW: model/predictor info ---
            predictor = out.get("predictor", "unknown")
            model_name = out.get("model_name", "n/a")
            st.caption(f"Predictor: {predictor} | Model: {model_name}")

            metrics = out.get("model_metrics", {}) or {}
            if isinstance(metrics, dict) and len(metrics) > 0:
                def _fmt_num(x, nd=3):
                    try:
                        return f"{float(x):.{nd}f}"
                    except Exception:
                        return "—"

                mae = _fmt_num(metrics.get("mae"), 3)
                rmse = _fmt_num(metrics.get("rmse"), 3)
                mape = _fmt_num(metrics.get("mape_percent"), 2)

                st.info(f"Model quality → MAE: {mae} | RMSE: {rmse} | MAPE: {mape}%")
            else:
                st.warning("Model metrics not available yet. Train model to see MAE/RMSE/MAPE.")

            # Recommendation
            try:
                score = float(out.get("composite_risk_score", 0.0))
            except Exception:
                score = 0.0

            st.markdown("#### Recommendation")
            if score < 0.35:
                st.success("Low risk: текущий план приемлем, мониторинг каждые 6 часов.")
            elif score < 0.65:
                st.warning("Medium risk: увеличь safety stock для критичных SKU и подготовь альтернативный маршрут.")
            else:
                st.error("High risk: активируй contingency plan, рассмотри expedited shipping / dual-source.")

    st.markdown(
        f'<div class="small-muted">Last update: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>',
        unsafe_allow_html=True
    )

    # st.markdown('</div>', unsafe_allow_html=True)

# =============================
# TAB 3: Event Journal
# =============================
with tab_events:
    st.markdown('<div class="dp-card">', unsafe_allow_html=True)
    st.subheader("Stored Risk Events (SQLite)")

    ev_limit = st.slider("Rows", min_value=10, max_value=500, value=100, step=10, key="events_limit")
    if st.button("Refresh Events", key="btn_events", use_container_width=True):
        data, err = safe_get(f"{api_base}/risk/events", params={"limit": ev_limit}, timeout=timeout_sec)
        if err:
            st.error(err)
        else:
            df = pd.DataFrame(data.get("items", []))
            if df.empty:
                st.info("Журнал пуст. Сначала запусти News Intelligence.")
            else:
                cols = [c for c in ["id", "title", "port", "risk_score", "analyzer", "published_at", "created_at"] if c in df.columns]
                st.dataframe(df[cols], use_container_width=True, height=500)

                c1, c2 = st.columns(2)
                with c1:
                    if "analyzer" in df.columns:
                        st.markdown("**Analyzer distribution**")
                        st.bar_chart(df["analyzer"].value_counts())
                with c2:
                    if "risk_score" in df.columns:
                        st.markdown("**Risk score distribution**")
                        # bins with pandas cut
                        bins = pd.cut(df["risk_score"], bins=[-0.01, 0.33, 0.66, 1.0], labels=["LOW", "MEDIUM", "HIGH"])
                        st.bar_chart(bins.value_counts().sort_index())
    st.markdown('</div>', unsafe_allow_html=True)
