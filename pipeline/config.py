"""Shared config: env loading, paths, and lazy client factories."""
import os
from pathlib import Path
from dotenv import load_dotenv

PIPELINE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PIPELINE_DIR.parent
# override=True so values in .env win over any empty/placeholder vars already in
# the shell (e.g. an inherited blank ANTHROPIC_API_KEY).
load_dotenv(PIPELINE_DIR / ".env", override=True)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

TEXTBOOK_DIR = Path(os.environ.get("TEXTBOOK_DIR", "")).expanduser()
CHUNK_DB = (PIPELINE_DIR / os.environ.get("CHUNK_DB", "../data/chunks.db")).resolve()

# Generation model: latest Sonnet for cost-effective grounded MCQ writing.
GEN_MODEL = os.environ.get("GEN_MODEL", "claude-sonnet-4-6")
VERIFY_MODEL = os.environ.get("VERIFY_MODEL", "claude-sonnet-4-6")


def anthropic_client():
    from anthropic import Anthropic
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in pipeline/.env")
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def supabase_admin():
    """Service-role client — bypasses RLS, used for bulk inserts only."""
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
