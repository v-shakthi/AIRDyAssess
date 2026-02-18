"""
dashboard/app.py
================
Streamlit dashboard for the AI Readiness Advisor.

Sections:
  1. Document upload
  2. Live progress tracking
  3. Overall score + radar chart
  4. Dimension deep-dives
  5. Use case candidates table
  6. Phased roadmap
  7. PDF download
"""

import time
import json
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_URL    = "http://localhost:8000"
API_KEY    = "sk-advisor-demo-001"
HEADERS    = {"X-API-Key": API_KEY}

MATURITY_COLORS = {
    "Nascent":    "#ef4444",
    "Emerging":   "#f97316",
    "Developing": "#eab308",
    "Advanced":   "#22c55e",
    "Leading":    "#3b82f6",
}

st.set_page_config(
    page_title="AI Readiness Advisor",
    page_icon="🧠",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "report" not in st.session_state:
    st.session_state.report = None
if "polling" not in st.session_state:
    st.session_state.polling = False


# ---------------------------------------------------------------------------
# Helper: radar chart
# ---------------------------------------------------------------------------

def render_radar(report: dict):
    scores = report["dimension_scores"]
    dims   = [s["dimension"] for s in scores]
    vals   = [s["score"] for s in scores]

    # Short labels for radar
    short_labels = [d.split(" & ")[0].split(" ")[0] for d in dims]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]],
        theta=short_labels + [short_labels[0]],
        fill="toself",
        fillcolor="rgba(59,130,246,0.2)",
        line=dict(color="#3b82f6", width=2),
        name="Readiness Score",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10], tickfont=dict(size=9)),
        ),
        showlegend=False,
        margin=dict(t=20, b=20, l=40, r=40),
        height=380,
    )
    return fig


# ---------------------------------------------------------------------------
# Helper: roadmap Gantt
# ---------------------------------------------------------------------------

def render_roadmap_gantt(phases: list[dict]):
    colors_map = {1: "#3b82f6", 2: "#22c55e", 3: "#8b5cf6"}
    rows = []
    for p in phases:
        rows.append({
            "Phase": f"Phase {p['phase']}: {p['title']}",
            "Timeline": p["timeline"],
            "Color": colors_map.get(p["phase"], "#64748b"),
        })
    df = pd.DataFrame(rows)

    # Simple horizontal bar chart as pseudo-Gantt
    fig = go.Figure()
    for i, row in df.iterrows():
        fig.add_trace(go.Bar(
            y=[row["Phase"]],
            x=[1],
            orientation="h",
            marker_color=row["Color"],
            text=row["Timeline"],
            textposition="inside",
            showlegend=False,
        ))
    fig.update_layout(
        barmode="stack",
        height=200,
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis=dict(showticklabels=False, showgrid=False),
        plot_bgcolor="white",
    )
    return fig


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_upload():
    st.title("🧠 AI Readiness & Migration Advisor")
    st.markdown(
        "Upload your enterprise documents (architecture diagrams, process docs, strategy papers, "
        "API specs) and receive a structured AI readiness assessment with a scored report, "
        "use case candidates, and a phased adoption roadmap."
    )
    st.divider()

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_files = st.file_uploader(
            "Upload enterprise documents",
            type=["pdf", "docx", "txt", "md"],
            accept_multiple_files=True,
            help="Supports PDF, Word (.docx), and plain text files.",
        )

    with col2:
        org_name = st.text_input("Organisation Name", value="Acme Corporation")
        context = st.text_area(
            "Additional Context (optional)",
            placeholder="e.g. Mid-size financial services firm, 2,000 employees, primarily on-prem infrastructure, exploring AI for fraud detection and customer service.",
            height=120,
        )

    if uploaded_files and st.button("▶ Start Assessment", type="primary", use_container_width=True):
        with st.spinner("Uploading documents..."):
            files = [("files", (f.name, f.read(), f.type)) for f in uploaded_files]
            data  = {"organisation_name": org_name, "additional_context": context}
            try:
                resp = requests.post(
                    f"{API_URL}/v1/assessment/upload",
                    headers=HEADERS,
                    files=files,
                    data=data,
                    timeout=30,
                )
                if resp.ok:
                    result = resp.json()
                    st.session_state.session_id = result["session_id"]
                    st.session_state.polling = True
                    st.session_state.report = None
                    st.rerun()
                else:
                    st.error(f"Upload failed: {resp.text}")
            except Exception as e:
                st.error(f"Could not connect to API: {e}\n\nMake sure the API is running: `python main.py`")

    with st.expander("💡 What makes a good document set?"):
        st.markdown("""
**Best documents to upload:**
- Current-state architecture diagrams or descriptions
- IT/Data strategy documents
- Process documentation or SOPs
- Existing automation / RPA documentation
- Data governance or data management policies
- Org charts or capability descriptions
- Any AI/ML project post-mortems or pilots

**The more context you provide, the more accurate and specific the assessment will be.**
        """)


def page_progress():
    st.title("⏳ Assessment In Progress")
    session_id = st.session_state.session_id

    placeholder = st.empty()
    progress_bar = st.progress(0)
    status_text  = st.empty()

    while st.session_state.polling:
        try:
            resp = requests.get(f"{API_URL}/v1/assessment/{session_id}", headers=HEADERS, timeout=5)
            if resp.ok:
                data = resp.json()
                pct  = data.get("progress_pct", 0)
                step = data.get("current_step", "Processing...")

                progress_bar.progress(pct / 100)
                status_text.info(f"**Step:** {step}")

                if data["status"] == "complete":
                    # Fetch full report
                    rr = requests.get(f"{API_URL}/v1/assessment/{session_id}/json", headers=HEADERS, timeout=10)
                    if rr.ok:
                        st.session_state.report = rr.json()
                    st.session_state.polling = False
                    st.rerun()

                elif data["status"] == "error":
                    st.error(f"Assessment failed: {data.get('error')}")
                    st.session_state.polling = False
                    break

        except Exception as e:
            status_text.warning(f"Waiting for API... ({e})")

        time.sleep(3)
        st.rerun()


def page_results():
    report = st.session_state.report
    if not report:
        st.warning("No report loaded.")
        return

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    overall = report["overall_score"]
    maturity = report["overall_maturity"]
    mat_color = MATURITY_COLORS.get(maturity, "#3b82f6")

    st.markdown(
        f"<h1 style='margin-bottom:0'>🧠 AI Readiness Report</h1>"
        f"<h3 style='color:#64748b;margin-top:4px'>{report['organisation_name']}</h3>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Score", f"{overall}/10")
    col2.metric("Maturity Level", maturity)
    col3.metric("Documents Analysed", len(report["documents_analysed"]))
    col4.metric("Pages Reviewed", report["total_pages_analysed"])

    st.divider()

    # -----------------------------------------------------------------------
    # Executive Summary + Radar
    # -----------------------------------------------------------------------
    left, right = st.columns([1.4, 1])

    with left:
        st.subheader("📋 Executive Summary")
        st.markdown(report["executive_summary"])

        qw_col, cb_col = st.columns(2)
        with qw_col:
            st.markdown("**⚡ Quick Wins**")
            for qw in report["quick_wins"]:
                st.markdown(f"✓ {qw}")
        with cb_col:
            st.markdown("**🚧 Critical Blockers**")
            for cb in report["critical_blockers"]:
                st.markdown(f"✗ {cb}")

    with right:
        st.subheader("🕸️ Readiness Radar")
        st.plotly_chart(render_radar(report), use_container_width=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Dimension Detail
    # -----------------------------------------------------------------------
    st.subheader("📊 Dimension Analysis")

    for ds in report["dimension_scores"]:
        score = ds["score"]
        mat   = ds["maturity_level"]
        color = MATURITY_COLORS.get(mat, "#3b82f6")

        with st.expander(f"**{ds['dimension']}** — {score}/10  ·  {mat}", expanded=False):
            st.progress(score / 10)

            s_col, g_col = st.columns(2)
            with s_col:
                st.markdown("**✅ Strengths**")
                for s in ds["key_strengths"]:
                    st.markdown(f"- {s}")
            with g_col:
                st.markdown("**❌ Gaps**")
                for g in ds["key_gaps"]:
                    st.markdown(f"- {g}")

            if ds.get("recommendations"):
                st.markdown("**💡 Recommendations**")
                for r in ds["recommendations"]:
                    st.markdown(f"→ {r}")

            if ds.get("evidence_excerpts"):
                st.caption("Evidence from documents:")
                for ex in ds["evidence_excerpts"]:
                    st.caption(f'_"{ex}"_')

    st.divider()

    # -----------------------------------------------------------------------
    # Use Case Candidates
    # -----------------------------------------------------------------------
    st.subheader("🎯 AI Use Case Candidates")

    uc_rows = []
    for uc in sorted(report["use_case_candidates"], key=lambda x: x["priority_rank"]):
        uc_rows.append({
            "Priority": f"#{uc['priority_rank']}",
            "Use Case": uc["title"],
            "AI Approach": uc["ai_approach"],
            "Complexity": uc["estimated_complexity"],
            "ROI Impact": uc["estimated_roi_impact"],
        })

    uc_df = pd.DataFrame(uc_rows)

    st.dataframe(
        uc_df,
        use_container_width=True,
        column_config={
            "Priority": st.column_config.TextColumn(width="small"),
            "ROI Impact": st.column_config.TextColumn(width="small"),
            "Complexity": st.column_config.TextColumn(width="small"),
        },
        hide_index=True,
    )

    # Detail cards
    for uc in sorted(report["use_case_candidates"], key=lambda x: x["priority_rank"]):
        with st.expander(f"#{uc['priority_rank']} — {uc['title']}"):
            st.markdown(uc["description"])
            st.markdown(f"**Process:** {uc['business_process']}")
            st.markdown(f"**AI Approach:** `{uc['ai_approach']}`")
            if uc.get("prerequisites"):
                st.markdown("**Prerequisites:**")
                for p in uc["prerequisites"]:
                    st.markdown(f"- {p}")

    st.divider()

    # -----------------------------------------------------------------------
    # Roadmap
    # -----------------------------------------------------------------------
    st.subheader("🗺️ Phased Adoption Roadmap")
    phase_colors = ["#3b82f6", "#22c55e", "#8b5cf6"]

    for phase in report["roadmap_phases"]:
        color = phase_colors[(phase["phase"] - 1) % len(phase_colors)]
        st.markdown(
            f"<div style='background:{color}15;border-left:4px solid {color};"
            f"padding:12px 16px;border-radius:6px;margin-bottom:12px'>"
            f"<b style='color:{color}'>Phase {phase['phase']}: {phase['title']}</b> "
            f"<span style='color:#64748b;font-size:13px'>· {phase['timeline']}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        p1, p2, p3 = st.columns(3)
        with p1:
            st.markdown("**Initiatives**")
            for i in phase["key_initiatives"]:
                st.markdown(f"- {i}")
        with p2:
            st.markdown("**Success Metrics**")
            for m in phase["success_metrics"]:
                st.markdown(f"- {m}")
        with p3:
            st.markdown("**Dependencies**")
            for d in phase.get("dependencies", []):
                st.markdown(f"- {d}")

    st.divider()

    # -----------------------------------------------------------------------
    # Downloads
    # -----------------------------------------------------------------------
    st.subheader("⬇️ Download Report")
    dl1, dl2, _ = st.columns([1, 1, 2])

    with dl1:
        if st.button("📄 Download PDF Report", type="primary", use_container_width=True):
            try:
                r = requests.get(
                    f"{API_URL}/v1/assessment/{st.session_state.session_id}/pdf",
                    headers=HEADERS,
                    timeout=15,
                )
                if r.ok:
                    st.download_button(
                        "Save PDF",
                        data=r.content,
                        file_name=f"AI_Readiness_{report['organisation_name'].replace(' ','_')}.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.error("PDF not ready.")
            except Exception as e:
                st.error(f"Error: {e}")

    with dl2:
        st.download_button(
            "📋 Download JSON Report",
            data=json.dumps(report, indent=2),
            file_name=f"AI_Readiness_{report['organisation_name'].replace(' ','_')}.json",
            mime="application/json",
            use_container_width=True,
        )

    if st.button("🔄 Start New Assessment", use_container_width=False):
        st.session_state.session_id = None
        st.session_state.report = None
        st.session_state.polling = False
        st.rerun()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if st.session_state.polling:
    page_progress()
elif st.session_state.report:
    page_results()
else:
    page_upload()
