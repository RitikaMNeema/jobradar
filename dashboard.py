"""
dashboard.py — Step 5 of JobRadar.
Run: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from storage import get_all_jobs, update_feedback, get_run_stats, get_connection

st.set_page_config(page_title="JobRadar", page_icon="🎯", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
  .stApp { background-color: #0f1117; color: #e2e8f0; }
  [data-testid="stSidebar"] {
    background-color: #1a1f2e;
    border-right: 1px solid #2d3748;
  }
  .badge-green    { background:#166534; color:#bbf7d0; padding:2px 10px;
                    border-radius:12px; font-size:12px; font-weight:600; }
  .badge-amber    { background:#92400e; color:#fde68a; padding:2px 10px;
                    border-radius:12px; font-size:12px; font-weight:600; }
  .badge-gray     { background:#374151; color:#9ca3af; padding:2px 10px;
                    border-radius:12px; font-size:12px; font-weight:600; }
  .badge-contract { background:#1e3a5f; color:#93c5fd; padding:2px 10px;
                    border-radius:12px; font-size:12px; font-weight:600; }
  .job-card {
    background: #1a1f2e;
    border: 1px solid #2d3748;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
    transition: border-color 0.15s;
  }
  .job-card:hover { border-color: #3b82f6; }
  .job-title  { font-size: 16px; font-weight: 600; color: #f1f5f9; }
  .job-meta   { font-size: 13px; color: #64748b; margin-top: 3px; }
  .job-reason { font-size: 13px; color: #94a3b8; margin-top: 8px;
                line-height: 1.5; font-style: italic; }
  [data-testid="stMetric"] {
    background: #1a1f2e;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 12px 16px;
  }
  #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar filters ──────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎯 JobRadar")
    st.markdown("---")

    conn = get_connection()
    companies = [r[0] for r in conn.execute(
        "SELECT DISTINCT company FROM jobs ORDER BY company"
    ).fetchall()]
    conn.close()

    selected_companies = st.multiselect(
        "Companies", options=companies, default=[], placeholder="All companies"
    )

    min_score = st.slider("Min score", 0, 100, 0, step=5)

    feedback_filter = st.selectbox(
        "Status",
        ["All", "Unreviewed", "⭐ Starred", "✅ Applied", "❌ Not interested"],
    )

    # ── State filter ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Location**")

    us_only      = st.checkbox("🇺🇸 US only", value=False)
    ca_only      = st.checkbox("📍 California only", value=False)
    remote_only  = st.checkbox("💻 Remote only", value=False)
    hide_contract = st.checkbox("Hide contract roles", value=False)

    st.markdown("---")
    st.markdown("**Run history**")
    runs = get_run_stats()
    for run in runs[:5]:
        st.markdown(
            f"<div style='font-size:11px; color:#64748b;'>"
            f"{run['ran_at'][:16].replace('T',' ')} · "
            f"<span style='color:#22c55e'>+{run['jobs_new']}</span> new"
            f"</div>",
            unsafe_allow_html=True,
        )

# ─── Load & filter data ───────────────────────────────────────────────────────

all_jobs = get_all_jobs(limit=1000)
df = pd.DataFrame(all_jobs)

if df.empty:
    st.info("No jobs in DB yet. Run `python storage.py` first.")
    st.stop()

if "feedback" not in df.columns:
    df["feedback"] = None

# Company filter
if selected_companies:
    df = df[df["company"].isin(selected_companies)]

# Score filter
if min_score > 0:
    df = df[df["score"].notna() & (df["score"] >= min_score)]

# Status filter
if feedback_filter == "Unreviewed":
    df = df[df["feedback"].isna()]
elif feedback_filter == "⭐ Starred":
    df = df[df["feedback"] == "starred"]
elif feedback_filter == "✅ Applied":
    df = df[df["feedback"] == "applied"]
elif feedback_filter == "❌ Not interested":
    df = df[df["feedback"] == "not_interested"]

# Location filters (applied to location column text)
if ca_only:
    df = df[df["location"].str.contains(
        r"California|San Francisco|Los Angeles|San Jose|San Diego|CA\b",
        case=False, na=False, regex=True
    )]
elif us_only:
    # Exclude clearly non-US locations (India, China, Australia, UK, etc.)
    df = df[~df["location"].str.contains(
        r"India|China|Australia|United Kingdom|UK|Canada|Germany|France|Singapore|Brazil",
        case=False, na=False, regex=True
    )]

if remote_only:
    df = df[df["location"].str.contains(r"Remote|remote", na=False, regex=True)]

# Hide contract roles
if hide_contract:
    df = df[~df["title"].str.contains(
        r"\bContract\b|\bContr\b|\bTemp\b|\bTemporary\b",
        case=False, na=False, regex=True
    )]

df = df.sort_values("score", ascending=False, na_position="last")

# ─── Top metrics ──────────────────────────────────────────────────────────────

all_df    = pd.DataFrame(all_jobs)
total     = len(all_df)
scored    = int(all_df["score"].notna().sum())
top_match = int((all_df["score"] >= 70).sum())
applied   = int((all_df.get("feedback", pd.Series()) == "applied").sum())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total jobs", total)
col2.metric("Scored", scored)
col3.metric("Top matches (≥70)", top_match)
col4.metric("Applied", applied)

st.markdown(f"### Showing {len(df)} jobs")
st.markdown("---")

# ─── Job cards ────────────────────────────────────────────────────────────────

def is_contract(title: str) -> bool:
    import re
    return bool(re.search(r"\bContract\b|\bContr\b|\bTemp\b", title or "", re.IGNORECASE))

def score_badge(score, title):
    contract_tag = ""
    if is_contract(title):
        contract_tag = "<span class='badge-contract' style='margin-right:6px;'>Contract</span>"

    if score is None or (isinstance(score, float) and pd.isna(score)):
        return f"{contract_tag}<span class='badge-gray'>Unscored</span>"
    elif score >= 85:
        return f"{contract_tag}<span class='badge-green'>{int(score)}/100 · Strong</span>"
    elif score >= 70:
        return f"{contract_tag}<span class='badge-amber'>{int(score)}/100 · Good</span>"
    else:
        return f"{contract_tag}<span class='badge-gray'>{int(score)}/100</span>"


for _, job in df.iterrows():
    badge        = score_badge(job.get("score"), job.get("title", ""))
    reason       = job.get("score_reason") or ""
    reason_short = reason.split("|")[0].strip()[:160] if reason else ""

    st.markdown(f"""
    <div class="job-card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
          <span style="font-size:11px; font-weight:700; color:#3b82f6;
                       text-transform:uppercase; letter-spacing:0.06em;">
            {job['company']}
          </span>
          <div class="job-title">{job['title']}</div>
          <div class="job-meta">📍 {job['location'] or 'Location unknown'}</div>
        </div>
        <div style="text-align:right; flex-shrink:0; margin-left:12px;">
          {badge}
        </div>
      </div>
      {"<div class='job-reason'>" + reason_short + "</div>" if reason_short else ""}
      <div style="margin-top:12px;">
        <a href="{job['url']}" target="_blank"
           style="font-size:13px; color:#3b82f6; text-decoration:none; font-weight:600;">
          View job →
        </a>
      </div>
    </div>
    """, unsafe_allow_html=True)

    current = job.get("feedback") or "none"
    b1, b2, b3, b4 = st.columns([1, 1, 1, 5])
    with b1:
        if st.button("⭐", key=f"star_{job['id']}", help="Star",
                     type="primary" if current == "starred" else "secondary"):
            update_feedback(job["id"], "starred")
            st.rerun()
    with b2:
        if st.button("✅", key=f"apply_{job['id']}", help="Applied",
                     type="primary" if current == "applied" else "secondary"):
            update_feedback(job["id"], "applied")
            st.rerun()
    with b3:
        if st.button("❌", key=f"skip_{job['id']}", help="Not interested",
                     type="primary" if current == "not_interested" else "secondary"):
            update_feedback(job["id"], "not_interested")
            st.rerun()