"""OpsIntel AI - decision-support interface.

    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opsintel import config, db  # noqa: E402
from opsintel.ai.assistant import ask, llm_available  # noqa: E402
from opsintel.analytics import anomaly, kpis, risk  # noqa: E402
from opsintel.governance import actions, audit  # noqa: E402
from opsintel.governance.rbac import DEMO_USERS, AccessDenied, get_user  # noqa: E402

st.set_page_config(page_title="OpsIntel AI", page_icon="📊", layout="wide")

# Reference categorical palette (validated order) + text tokens.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
MUTED = "#8a8984"
GRID = "#e6e5e1"

EXAMPLES = [
    "Why did our operational costs increase this month?",
    "Which open issues are most likely to delay delivery?",
    "What are the recurring causes of service downtime?",
    "Which business process should we improve first, and why?",
    "Which service category had the highest SLA breach rate last quarter, and what explains the increase?",
    "Which services are at greatest risk of missing their SLA next week?",
    "What should the support team do when a recurring network incident occurs?",
]


@st.cache_resource
def _con():
    return db.connect()


def con():
    return _con()


def style(fig: go.Figure, title: str, height: int = 340, y_title: str | None = None) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15), x=0, xanchor="left"), height=height,
        margin=dict(l=8, r=8, t=48, b=8), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0, title=None),
        hovermode="x unified", bargap=0.3, bargroupgap=0.08, font=dict(size=12),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED), title=y_title)
    fig.update_traces(selector=dict(type="bar"), marker_line_width=0)
    fig.update_traces(selector=dict(type="scatter"), line=dict(width=2))
    return fig


def chart_from_hint(result: dict):
    """Render a tool result's chart hint (bar/line/area/scatter) with a single y-axis."""
    hint, data = result.get("chart"), result.get("data")
    if not hint or not data:
        return None
    df = pd.DataFrame(data)
    x = hint["x"]
    if x not in df.columns:
        return None
    ys = [y for y in hint["y"] if y in df.columns]
    fig = go.Figure()
    color = hint.get("color")
    if color and color in df.columns:
        for i, (k, g) in enumerate(df.groupby(color)):
            c = SERIES[i % len(SERIES)] if i < 8 else MUTED
            if hint["type"] == "bar":
                fig.add_bar(x=g[x], y=g[ys[0]], name=str(k), marker_color=c)
            else:
                fig.add_scatter(x=g[x], y=g[ys[0]], name=str(k), mode="lines" if hint["type"] != "scatter" else "markers",
                                line_color=c, marker=dict(size=9, color=c), stackgroup="one" if hint["type"] == "area" else None)
    else:
        for i, y in enumerate(ys):
            if hint["type"] == "bar":
                fig.add_bar(x=df[x], y=df[y], name=y.replace("_", " "), marker_color=SERIES[i])
            else:
                fig.add_scatter(x=df[x], y=df[y], name=y.replace("_", " "), mode="lines+markers" if hint["type"] == "line" else "markers",
                                line_color=SERIES[i], marker=dict(size=8))
    fig.update_layout(showlegend=len(ys) > 1 or bool(color))
    return style(fig, hint.get("title", ""), 320)


# ---------------------------------------------------------------- sidebar / identity

with st.sidebar:
    st.title("OpsIntel AI")
    st.caption("Governed operational intelligence for IT service businesses")
    labels = {u: f"{n}  ·  {r}" for u, n, r in DEMO_USERS}
    user_id = st.selectbox("Signed in as (demo)", list(labels), index=1, format_func=labels.get)
    user = get_user(con(), user_id)
    st.caption(user.role.description)
    page = st.radio("View", ["Overview", "Ask OpsIntel", "Risk & anomalies", "Actions & approvals", "Data quality & lineage", "Audit log"])
    st.divider()
    eng_opts = ["rules"] + (["claude"] if llm_available() else [])
    engine = st.selectbox("Assistant engine", eng_opts, index=len(eng_opts) - 1,
                          help="claude = LLM with tools (needs ANTHROPIC_API_KEY); rules = deterministic analytics-only engine")
    if not llm_available():
        st.caption("No Anthropic credentials found - running the deterministic engine. Set ANTHROPIC_API_KEY to enable Claude.")
    st.caption(f"Data snapshot: {config.SNAPSHOT_DATE}. Synthetic data for a fictional company.")

can_cost = "costs" in user.role.tables

# ---------------------------------------------------------------- overview

if page == "Overview":
    st.header("Operational performance")
    if config.SOURCE != "synthetic":
        st.caption(f"Data source: {config.SOURCE} · {config.DATA_START} to {config.SNAPSHOT_DATE}")
    h = kpis.headline_kpis()

    def fmt(cur, prev, f, unit="", scale=1.0):
        if cur is None:
            return "n/a", None
        delta = None if prev is None else f"{(cur - prev) / scale:+{f}}{unit}"
        return f"{cur / scale:,{f}}{unit}", delta

    show_cost = can_cost and h["cost_gbp"] is not None
    cols = st.columns(5 if show_cost else 4)
    v, dl = fmt(h["incidents"], h["incidents_prev"], ".0f")
    cols[0].metric(f"Incidents ({h['month']})", v, dl and f"{dl} vs {h['previous_month']}", delta_color="inverse")
    v, dl = fmt(h["breach_rate_pct"], h["breach_rate_pct_prev"], ".1f")
    cols[1].metric("SLA breach rate", v if v == "n/a" else v + "%", dl and dl + " pp", delta_color="inverse")
    v, dl = fmt(h["mttr_hours"], h["mttr_hours_prev"], ".1f", " h")
    cols[2].metric("Mean time to resolve", v, dl, delta_color="inverse")
    v, dl = fmt(h["outage_minutes"], h["outage_minutes_prev"], ".0f", " h", 60)
    cols[3].metric("Downtime", v, dl, delta_color="inverse")
    if show_cost:
        diff = None if h["cost_gbp_prev"] is None else h["cost_gbp"] - h["cost_gbp_prev"]
        cols[4].metric("Operating cost", f"£{h['cost_gbp'] / 1000:,.1f}k",
                       None if diff is None else f"{'+' if diff >= 0 else '-'}£{abs(diff) / 1000:,.1f}k", delta_color="inverse")

    c1, c2 = st.columns(2)
    try:
        br = kpis.sla_breach_rate("last_quarter", "category")
    except (ValueError, IndexError, KeyError) as e:
        st.info(f"Quarterly comparison unavailable for this data: {e}")
        st.stop()
    df = pd.DataFrame(br["data"])
    fig = go.Figure()
    fig.add_bar(y=df.category, x=df.prev_breach_rate_pct, name=br["compared_with"], orientation="h", marker_color=SERIES[0])
    fig.add_bar(y=df.category, x=df.breach_rate_pct, name=br["period"], orientation="h", marker_color=SERIES[1])
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(hovermode="y unified")
    c1.plotly_chart(style(fig, f"SLA breach rate % by category - {br['period']} vs {br['compared_with']}", 360), width="stretch")

    tr = pd.DataFrame(kpis.incident_trend(None)["data"])
    fig = go.Figure()
    fig.add_scatter(x=tr.month, y=tr.breach_rate_pct, name="Breach rate %", mode="lines+markers", line_color=SERIES[0], marker=dict(size=8))
    fig.add_hline(y=10, line_dash="dot", line_color=MUTED, annotation_text="10% tolerance (POL-SLA-001)", annotation_font_color=MUTED)
    fig.update_layout(showlegend=False)
    c2.plotly_chart(style(fig, "Monthly SLA breach rate %", 360), width="stretch")

    c3, c4 = st.columns(2)
    rc = kpis.top_root_causes("last_quarter", rank_by="incidents")
    rdf = pd.DataFrame(rc["data"])
    fig = go.Figure()
    fig.add_bar(y=rdf.root_cause, x=rdf.prev_incidents, name=kpis.previous("quarter", rc["period"]), orientation="h", marker_color=SERIES[0])
    fig.add_bar(y=rdf.root_cause, x=rdf.incidents, name=rc["period"], orientation="h", marker_color=SERIES[1])
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(hovermode="y unified")
    c3.plotly_chart(style(fig, f"Incidents by root cause - {rc['period']} vs previous quarter", 380), width="stretch")

    vol = pd.DataFrame(kpis.incident_trend("business_unit")["data"])
    fig = go.Figure()
    for i, (k, g) in enumerate(vol.groupby("grp")):
        fig.add_scatter(x=g.month, y=g.incidents, name=k, mode="lines", line_color=SERIES[i])
    c4.plotly_chart(style(fig, "Monthly incidents by business unit", 380), width="stretch")

    if show_cost:
        ct = pd.DataFrame(kpis.cost_trend("business_unit")["data"])
        fig = go.Figure()
        for i, (k, g) in enumerate(ct.groupby("business_unit")):
            fig.add_bar(x=g.month, y=g.amount_gbp, name=k, marker_color=SERIES[i], marker_line_color="white", marker_line_width=2)
        fig.update_layout(barmode="stack")
        st.plotly_chart(style(fig, "Monthly operating cost by business unit (GBP)", 380), width="stretch")

    st.subheader("Emerging risks")
    a = anomaly.operational_anomalies()
    st.write(a["summary"])
    if a["data"]:
        st.dataframe(pd.DataFrame(a["data"])[["day", "service", "main_signal", "signal_value", "z_score", "anomaly_score"]],
                     hide_index=True, width="stretch")

# ---------------------------------------------------------------- assistant

elif page == "Ask OpsIntel":
    st.header("Ask OpsIntel")
    st.caption("Answers are computed from the operational data and knowledge base. Every figure cites its evidence; "
               "figures that do not trace back to evidence are flagged.")
    if "history" not in st.session_state:
        st.session_state.history = []
    ex_cols = st.columns(2)
    picked = None
    for i, q in enumerate(EXAMPLES):
        if ex_cols[i % 2].button(q, key=f"ex{i}", width="stretch"):
            picked = q
    prompt = st.chat_input("Ask a question about operations, SLAs, costs, risks or procedures") or picked
    if prompt:
        with st.spinner("Analysing..."):
            ans = ask(prompt, user.user_id, engine=engine, con=con())
        st.session_state.history.insert(0, ans)

    for n, ans in enumerate(st.session_state.history):
        with st.chat_message("user"):
            st.write(ans.question)
        with st.chat_message("assistant"):
            st.markdown(ans.answer)
            g = ans.grounding
            badge = "✅ all figures traced to evidence" if not g["ungrounded"] else f"⚠️ {len(g['ungrounded'])} figure(s) not found in evidence: {', '.join(g['ungrounded'])}"
            st.caption(f"Engine: {ans.engine} · {ans.latency_ms} ms · {g['figures']} figures · {badge}"
                       + (f" · {len(ans.injection_hits)} untrusted text fragment(s) withheld (possible prompt injection)" if ans.injection_hits else ""))
            for ev in ans.evidence:
                with st.expander(f"[{ev.evidence_id}] {ev.tool} - {ev.summary[:140]}", expanded=False):
                    if ev.is_error:
                        st.error(ev.result.get("error"))
                        continue
                    fig = chart_from_hint(ev.result)
                    if fig:
                        st.plotly_chart(fig, width="stretch", key=f"c{n}{ev.evidence_id}")
                    data = ev.result.get("data")
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        st.dataframe(pd.DataFrame(data).astype(str) if ev.tool in ("search_knowledge", "get_document") else pd.DataFrame(data),
                                     hide_index=True, width="stretch")
                    if ev.sql:
                        st.code(ev.sql, language="sql")
                    meta = {k: v for k, v in ev.result.items() if k not in ("data", "chart", "sql", "summary")}
                    if meta:
                        st.json(meta, expanded=False)
            if user.role.can_propose and ans.evidence and not ans.abstained:
                with st.popover("Propose an action from this answer"):
                    with st.form(f"prop{n}"):
                        title = st.text_input("Action title")
                        rationale = st.text_area("Rationale", value=ans.answer.split("\n")[0][:400])
                        ev_ids = st.multiselect("Evidence", [e.evidence_id for e in ans.evidence if not e.is_error],
                                                default=[e.evidence_id for e in ans.evidence if not e.is_error][:2])
                        prio = st.selectbox("Priority", ["P2", "P3", "P1", "P4"])
                        owner = st.text_input("Owner group", "Network Operations")
                        if st.form_submit_button("Submit for approval") and title and ev_ids:
                            evs = [{"evidence_id": e.evidence_id, "tool": e.tool, "args": e.args, "summary": e.summary, "sql": e.sql,
                                    "sources": e.sources} for e in ans.evidence if e.evidence_id in ev_ids]
                            act = actions.propose(con(), user, title, rationale, evs, prio, None, owner)
                            st.success(f"{act['action_id']} submitted - awaiting approval by a manager.")

# ---------------------------------------------------------------- risk

elif page == "Risk & anomalies":
    st.header("Predictive risk")
    try:
        r = risk.sla_risk_next_week()
    except risk.InsufficientData as e:
        r = None
        st.info(str(e))
    if r is not None:
        df = pd.DataFrame(r["data"]).sort_values("risk_pct")
        lo = df.risk_pct - df.interval_pct.str[0]
        hi = df.interval_pct.str[1] - df.risk_pct
        fig = go.Figure(go.Scatter(x=df.risk_pct, y=df.service, mode="markers", marker=dict(size=11, color=SERIES[0]),
                                   error_x=dict(type="data", array=hi, arrayminus=lo, color=MUTED, thickness=2, width=0),
                                   hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        fig.add_vline(x=60, line_dash="dot", line_color=MUTED, annotation_text="High ≥ 60%", annotation_font_color=MUTED)
        fig.update_xaxes(range=[0, 100], title="Probability of missing 90% SLA compliance (%)")
        fig.update_layout(showlegend=False, hovermode="closest")
        st.plotly_chart(style(fig, f"SLA risk for {r['forecast_week']} (dot = estimate, bar = 10th-90th percentile)", 460), width="stretch")
        st.caption(r["definition"] + " " + r["model"])
        tbl = pd.DataFrame([{"service": d["service"], "risk %": d["risk_pct"], "band": d["band"], "owner": d["owner_group"],
                             "main drivers": "; ".join(f"{x['factor']} = {x['value']}" for x in d["top_drivers"])} for d in r["data"]])
        st.dataframe(tbl, hide_index=True, width="stretch")
        ev = r["evaluation"]
        st.markdown("**Model evaluation (out-of-sample)**")
        m = st.columns(4)
        m[0].metric("Model AUC", ev["model_auc"], f"{ev['model_auc'] - ev['baseline_persistence_auc']:+.3f} vs persistence")
        m[1].metric("Model Brier", ev["model_brier"], f"{ev['model_brier'] - ev['baseline_persistence_brier']:+.3f}", delta_color="inverse")
        m[2].metric("Test windows", ev["test_windows"])
        m[3].metric("Positive rate (test)", f"{100 * ev['positive_rate_test']:.0f}%")

    st.header("Delivery risk - open service requests")
    d = risk.delivery_delay_risk(20)
    st.caption(d["summary"] + " Method: " + d["method"])
    st.dataframe(pd.DataFrame(d["data"]), hide_index=True, width="stretch")

    st.header("Anomalies")
    a = anomaly.operational_anomalies()
    st.caption(a["method"])
    if a["data"]:
        st.dataframe(pd.DataFrame(a["data"]), hide_index=True, width="stretch")
    if can_cost:
        c = anomaly.cost_anomalies()
        st.caption(c["method"])
        st.dataframe(pd.DataFrame(c["data"]), hide_index=True, width="stretch")

# ---------------------------------------------------------------- actions

elif page == "Actions & approvals":
    st.header("Actions & approvals")
    st.caption("Recommended actions are only carried out after an accountable manager approves them. "
               "Proposers cannot approve their own actions.")
    rows = actions.list_actions(con())
    if not rows:
        st.info("No actions yet. Propose one from an assistant answer.")
    for a in rows:
        with st.container(border=True):
            top = st.columns([5, 1, 1])
            top[0].markdown(f"**{a['title']}**  \n`{a['action_id']}` · {a['priority']} · owner: {a['owner_group'] or '-'} · "
                            f"proposed by {a['created_by']} at {a['created_at']}")
            top[1].markdown(f"**{a['status'].replace('_', ' ').title()}**")
            st.write(a["rationale"])
            with st.expander(f"Evidence ({len(a['evidence'])})"):
                st.json(a["evidence"], expanded=False)
            if a["decided_by"]:
                st.caption(f"Decision by {a['decided_by']} at {a['decided_at']}: {a['decision_note'] or ''}")
            if a["outcome"]:
                st.caption(f"Outcome: {a['outcome']}")
            note = st.text_input("Note / outcome", key=f"n{a['action_id']}")
            b = st.columns(4)
            try:
                if a["status"] == "proposed":
                    if b[0].button("Approve", key=f"a{a['action_id']}", disabled=not user.role.can_approve):
                        actions.decide(con(), user, a["action_id"], True, note)
                        st.rerun()
                    if b[1].button("Reject", key=f"r{a['action_id']}", disabled=not user.role.can_approve):
                        actions.decide(con(), user, a["action_id"], False, note)
                        st.rerun()
                elif a["status"] in ("approved", "in_progress"):
                    if a["status"] == "approved" and b[0].button("Start", key=f"s{a['action_id']}"):
                        actions.update_progress(con(), user, a["action_id"], "in_progress", note)
                        st.rerun()
                    if b[1].button("Mark done", key=f"d{a['action_id']}"):
                        actions.update_progress(con(), user, a["action_id"], "done", note)
                        st.rerun()
            except (AccessDenied, ValueError) as e:
                st.error(str(e))
    st.subheader("Notification outbox")
    st.dataframe(db.query_df("SELECT created_at, channel, recipient, subject, delivered FROM notifications ORDER BY notification_id DESC LIMIT 50",
                             con=con()), hide_index=True, width="stretch")

# ---------------------------------------------------------------- data quality

elif page == "Data quality & lineage":
    st.header("Data quality & lineage")
    run = con().execute("SELECT run_id, started_at, finished_at FROM etl_runs WHERE status='succeeded' ORDER BY started_at DESC LIMIT 1").fetchone()
    st.caption(f"Latest ETL run {run['run_id']} finished {run['finished_at']}")
    dq = db.query_df("SELECT source, stage, metric, value FROM dq_results WHERE run_id=?", (run["run_id"],), con())
    piv = dq.pivot_table(index=["source", "metric"], columns="stage", values="value").reset_index()
    piv = piv[piv.metric.isin(["rows", "exact_duplicate_rows", "duplicate_keys", "missing_required_cells", "schema_violations", "unmatched_references"])]
    st.subheader("Before vs after processing")
    st.dataframe(piv[["source", "metric", "before", "after"]], hide_index=True, width="stretch")
    st.subheader("Quarantined records")
    st.dataframe(db.query_df("SELECT source, reason, COUNT(*) AS records FROM etl_rejects WHERE run_id=? GROUP BY source, reason",
                             (run["run_id"],), con()), hide_index=True, width="stretch")
    st.subheader("Lineage")
    lin = db.query_df("SELECT target_table, source_name, source_type, source_uri, rows_in, rows_out, rows_rejected, transforms, source_sha256 "
                      "FROM lineage WHERE run_id=?", (run["run_id"],), con())
    lin["transforms"] = lin.transforms.map(lambda t: " → ".join(json.loads(t)))
    st.dataframe(lin, hide_index=True, width="stretch")
    st.subheader("Metric definitions")
    st.table(pd.DataFrame(db.METRIC_DEFINITIONS.items(), columns=["metric", "definition"]))

# ---------------------------------------------------------------- audit

elif page == "Audit log":
    st.header("Audit log")
    if not user.role.can_view_audit:
        st.warning("The audit log is restricted to auditors and executives.")
    else:
        ok, bad = audit.verify(con())
        (st.success if ok else st.error)("Hash chain intact - no entries altered or removed." if ok else f"Chain broken at entry {bad}.")
        log = db.query_df("SELECT seq, ts, user_id, role, event, detail, hash FROM audit_log ORDER BY seq DESC LIMIT 500", con=con())
        st.dataframe(log, hide_index=True, width="stretch")
