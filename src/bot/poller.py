"""
MACRO BIAS ENGINE - One-Shot Telegram Poller
Fetches pending updates once, processes them, and exits.
Designed for GitHub Actions (short-lived runs).
"""
import os
import sys
import logging
from datetime import datetime

# Path setup
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import FOREX_PAIRS

# --- Configuration ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
FMP_API_KEY = os.environ.get("FMP_API_KEY")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN not set.")

# --- Import handlers from the main bot file ---
from src.bot.telegram_bot import (
    start, help_command, daily_bias, asset_command,
    get_today_fundamental_vectors, calculate_hybrid_confluence,
    FOREX_PAIRS
)

# --- Build the application ---
app = Application.builder().token(TOKEN).build()

# Register handlers (same as main bot)
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("daily_bias", daily_bias))
for cmd in ["eurusd", "gbpusd", "audusd", "eurjpy", "gbpjpy", "cadjpy", "cadchf", "gold", "silver", "btc", "nikkei", "dow"]:
    app.add_handler(CommandHandler(cmd, asset_command))

# --- Poll once and exit ---
def poll_once():
    print("⏳ Fetching pending updates...")
    # Get updates from Telegram (limit=100)
    updates = app.bot.get_updates(limit=100, timeout=5)
    
    if not updates:
        print("ℹ️ No pending updates.")
        return
    
    print(f"📥 Processing {len(updates)} updates...")
    for update in updates:
        # Process each update
        app.process_update(update)
    
    print("✅ Done.")

if __name__ == "__main__":
    poll_once()
