import os
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. Read your hidden local lockbox file (.env) and load the keys into RAM
load_dotenv()

def get_supabase_client() -> Client:
    """
    Establishes and returns an authenticated connection pipeline 
    to your remote cloud Supabase database.
    """
    # 2. Extract your connection credentials out of your environment memory
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    # 3. Defensive Guard: Stop instantly if configurations are broken or missing
    if not supabase_url or not supabase_key:
        raise ValueError(
            "CRITICAL CONFIGURATION ERROR: 'SUPABASE_URL' or 'SUPABASE_KEY' could not be found. "
            "Please check that your local .env file contains your real credentials."
        )
        
    # 4. Perform the cryptographic handshake and return the live connection
    try:
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as error_message:
        raise RuntimeError(
            f"DATABASE INITIALIZATION FAILED: Could not securely connect to the Supabase API. "
            f"Details: {str(error_message)}"
        )
