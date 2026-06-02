import os

# ─── API Keys ───────────────────────────────────────────────
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
NETLIFY_TOKEN     = os.getenv("NETLIFY_TOKEN", "")
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN", "")

# ─── Directories ────────────────────────────────────────────
# Use absolute path relative to this config file — works regardless of working directory
_BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(_BASE_DIR, "projects")
LOGS_DIR     = os.path.join(_BASE_DIR, "logs")

for d in [PROJECTS_DIR, LOGS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ─── App Settings ───────────────────────────────────────────
APP_TITLE       = "AI Website Builder PRO"
APP_VERSION     = "2.0"
AUTOSAVE_MS     = 30_000
MAX_UNDO_STEPS  = 100

# ─── AI Providers ───────────────────────────────────────────
AI_PROVIDERS = {
    "OpenAI":    {"models": ["gpt-5-mini-2025-08-07", "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]},
    "Anthropic": {"models": ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"]},
    "Gemini":    {"models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"]},
}

DEFAULT_PROVIDER = "OpenAI"
DEFAULT_MODEL    = "gpt-5-mini-2025-08-07"