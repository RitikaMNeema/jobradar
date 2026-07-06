"""
notifier.py — Step 4 of JobRadar.

Sends a Gmail digest of top-scored NEW jobs found in this run.
Only emails if there are new jobs with score >= MIN_SCORE.
No email if nothing interesting — no noise.

Requires env vars:
    GMAIL_ADDRESS       your Gmail address (sender + recipient)
    GMAIL_APP_PASSWORD  16-char app password from myaccount.google.com/apppasswords

Run standalone:
    export GMAIL_ADDRESS="you@gmail.com"
    export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
    python notifier.py
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from storage import get_connection

MIN_SCORE = 70      # only email jobs above this threshold
MAX_JOBS  = 15      # cap the digest length


# ─── Fetch new top jobs ───────────────────────────────────────────────────────

def get_new_top_jobs() -> list[dict]:
    """
    Returns top-scored jobs from the latest run only.
    'New' = fetched_at matches the most recent run's timestamp.
    """
    conn = get_connection()

    # Get the timestamp of the most recent fetch run
    latest = conn.execute(
        "SELECT MAX(fetched_at) as latest FROM jobs"
    ).fetchone()["latest"]

    if not latest:
        conn.close()
        return []

    rows = conn.execute(
        """SELECT company, title, location, url, score, score_reason, fetched_at
           FROM jobs
           WHERE fetched_at = ?
             AND score >= ?
           ORDER BY score DESC
           LIMIT ?""",
        (latest, MIN_SCORE, MAX_JOBS),
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


# ─── Build email ──────────────────────────────────────────────────────────────

def build_html_email(jobs: list[dict]) -> str:
    rows_html = ""
    for job in jobs:
        score = job["score"]
        # Color-code by score
        if score >= 85:
            badge_color = "#22c55e"   # green
            badge_label = "Strong Match"
        elif score >= 70:
            badge_color = "#f59e0b"   # amber
            badge_label = "Good Match"
        else:
            badge_color = "#94a3b8"   # gray
            badge_label = "Partial"

        reason = job.get("score_reason") or ""
        # Extract just the first sentence for the card
        reason_short = reason.split("|")[0].strip() if "|" in reason else reason[:120]

        rows_html += f"""
        <div style="border:1px solid #e2e8f0; border-radius:8px; padding:16px;
                    margin-bottom:12px; background:#fff;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
              <span style="font-size:11px; font-weight:600; color:#64748b;
                           text-transform:uppercase; letter-spacing:0.05em;">
                {job['company'].upper()}
              </span>
              <div style="font-size:16px; font-weight:600; color:#1e293b; margin-top:2px;">
                {job['title']}
              </div>
              <div style="font-size:13px; color:#64748b; margin-top:2px;">
                📍 {job['location']}
              </div>
            </div>
            <span style="background:{badge_color}; color:#fff; font-size:12px;
                         font-weight:600; padding:4px 10px; border-radius:20px;
                         white-space:nowrap; margin-left:12px;">
              {score}/100 · {badge_label}
            </span>
          </div>
          <div style="font-size:13px; color:#475569; margin-top:10px; line-height:1.5;">
            {reason_short}
          </div>
          <a href="{job['url']}"
             style="display:inline-block; margin-top:12px; padding:7px 16px;
                    background:#3b82f6; color:#fff; border-radius:6px;
                    font-size:13px; font-weight:600; text-decoration:none;">
            View Job →
          </a>
        </div>
        """

    return f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                        background:#f8fafc; padding:24px; color:#1e293b;">
      <div style="max-width:600px; margin:0 auto;">
        <div style="background:#3b82f6; color:#fff; border-radius:10px 10px 0 0;
                    padding:20px 24px;">
          <div style="font-size:20px; font-weight:700;">🎯 JobRadar</div>
          <div style="font-size:14px; opacity:0.85; margin-top:4px;">
            {len(jobs)} new top match{'es' if len(jobs) != 1 else ''} found
          </div>
        </div>
        <div style="background:#f1f5f9; padding:24px; border-radius:0 0 10px 10px;">
          {rows_html}
          <div style="font-size:12px; color:#94a3b8; text-align:center; margin-top:16px;">
            JobRadar · Scores ≥ {MIN_SCORE}/100 · Running on GitHub Actions
          </div>
        </div>
      </div>
    </body></html>
    """


def build_plain_text(jobs: list[dict]) -> str:
    lines = [f"JobRadar — {len(jobs)} new top match(es)\n"]
    for job in jobs:
        lines.append(f"{job['score']}/100  [{job['company'].upper()}] {job['title']}")
        lines.append(f"  Location : {job['location']}")
        lines.append(f"  URL      : {job['url']}")
        reason = (job.get("score_reason") or "").split("|")[0].strip()
        if reason:
            lines.append(f"  Why      : {reason}")
        lines.append("")
    return "\n".join(lines)


# ─── Send ─────────────────────────────────────────────────────────────────────

def send_digest(jobs: list[dict]):
    gmail_address      = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 JobRadar: {len(jobs)} new match{'es' if len(jobs) != 1 else ''} (top score: {jobs[0]['score']}/100)"
    msg["From"]    = gmail_address
    msg["To"]      = gmail_address

    msg.attach(MIMEText(build_plain_text(jobs), "plain"))
    msg.attach(MIMEText(build_html_email(jobs), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_app_password)
        server.send_message(msg)

    print(f"✓ Email sent: {len(jobs)} jobs to {gmail_address}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def notify():
    jobs = get_new_top_jobs()

    if not jobs:
        print(f"No new jobs with score ≥ {MIN_SCORE} — skipping email.")
        return

    print(f"Found {len(jobs)} new top-scored jobs. Sending digest...")
    for job in jobs:
        print(f"  {job['score']}/100  [{job['company'].upper()}] {job['title']}")

    send_digest(jobs)


if __name__ == "__main__":
    missing = [v for v in ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"] if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        print("  export GMAIL_ADDRESS='you@gmail.com'")
        print("  export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'")
        exit(1)

    notify()
