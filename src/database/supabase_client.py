import os
from supabase import create_client

def get_supabase_client():
    """
    Creates and returns a connection to your Supabase database.
    Reads credentials from environment variables (GitHub Secrets).
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "CRITICAL ERROR: SUPABASE_URL or SUPABASE_KEY not found in environment."
        )

    return create_client(supabase_url, supabase_key)
