"""
config.py — Central config for JobRadar.
All company targets, ATS routing, and keyword filters live here.
"""

# ─── Keywords ────────────────────────────────────────────────────────────────
KEYWORDS = [
    "data engineer",
    "ml engineer",
    "machine learning engineer",
    "ai engineer",
    "data scientist",
    "analytics engineer",
    "platform engineer",
    "mlops",
    "llm engineer",
]

# ─── Greenhouse companies (verified ✅) ───────────────────────────────────────
GREENHOUSE_TOKENS = [
    "anthropic",
    "databricks",
    "stripe",
    "figma",
    "airbnb",
    "reddit",
    "scaleai",
    "xai",
    "coreweave",
    "datadog",
]

# ─── Lever companies (verified ✅) ────────────────────────────────────────────
# All previous Lever tokens were wrong — these companies moved off Lever.
# Leaving this list empty for now; will populate in Step 3 when we add custom portals.
LEVER_TOKENS = []

# ─── Custom portals (Step 3 — not yet active) ────────────────────────────────
CUSTOM_PORTALS = {
    "apple":        "https://jobs.apple.com/en-us/search?team=machine-learning-and-ai",
    "google":       "https://careers.google.com/jobs/results/",
    "amazon":       "https://www.amazon.jobs/en/search?category=data-science",
    "microsoft":    "https://jobs.microsoft.com/us/en/search#q=data+engineer",
    "salesforce":   "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site",
    "meta":         "https://www.metacareers.com/jobs",
    "nvidia":       "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
    "snowflake":    "https://careers.snowflake.com/us/en/search-results",
    "netflix":      "https://explore.jobs.netflix.net/careers",
    "adobe":        "https://adobe.wd5.myworkdayjobs.com/external_experienced",
    "openai":       "https://openai.com/careers",
    "linkedin":     "https://careers.linkedin.com/",
    "confluent":    "https://confluent.wd5.myworkdayjobs.com/confluent",
    "uber":         "https://www.uber.com/us/en/careers/",
    "huggingface":  "https://apply.workable.com/huggingface/",
    "mistral":      "https://mistral.ai/careers/",
    "cohere":       "https://cohere.com/careers",
    "dropbox":      "https://jobs.dropbox.com/",
}