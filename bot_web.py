"""
MACRO BIAS ENGINE - Telegram Interface
Listens for commands and asset text triggers to render directional profiles.
"""
import os
import sys
import logging
import asyncio
import threading

from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

# Load configuration architectures
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logging.error("❌ TELEGRAM_BOT_TOKEN not set.")
    sys.exit(1)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask App (for Render keep-alive) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Macro Bias Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route('/ping')
def ping():
    return "Pong", 200

# --- Telegram Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcomes the developer or user."""
    await update.message.reply_text(
        "🏛️ **Welcome to the Macro Bias Engine Terminal**\n\n"
        "Send me a ticker parameter command (e.g., `/eurusd` or `/xauusd`) "
        "to view the current rolling directional momentum metrics.\n\n"
        "**Supported Assets:**\n"
        "`EURUSD`, `GBPUSD`, `AUDUSD`, `EURJPY`, `GBPJPY`, `CADJPY`, `CADCHF`,\n"
        "`XAUUSD` (Gold), `XAGUSD` (Silver), `BTCUSD`, `JP225`, `US30`",
        parse_mode="Markdown"
    )

async def asset_bias_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dynamic routing catcher. Cleans inputs from commands like '/eurusd'
    or plain text requests like 'btcusd' and pulls calculated analytical stats.
    """
    # Isolate and format string inputs (e.g. "/EURUSD" -> "EURUSD")
    raw_text = update.message.text
    clean_ticker = raw_text.replace("/", "").strip().upper()
    
    # Import calculation methods safely inline to capture updated database matrices
    from src.analytics.bias_engine import calculate_bias_for_asset
    from src.ingestion.market_prices import ASSETS, FOREX_PAIRS
    
    if clean_ticker not in ASSETS:
        # Avoid replying to miscellaneous chat text unless it resembles a monitored token asset
        if raw_text.startswith("/"):
            await update.message.reply_text(f"❌ Asset `{clean_ticker}` is not tracked by the engine matrix.", parse_mode="Markdown")
        return

    await update.message.reply_chat_action(action="typing")
    
    # Extract calculations from the analytical layers
    metrics = calculate_bias_for_asset(clean_ticker)
    
    if metrics.get("status") != "SUCCESS":
        await update.message.reply_text(
            f"⚠️ **Insufficient History for {clean_ticker}**\n\n{metrics.get('message')}",
            parse_mode="Markdown"
        )
        return
        
    # Render premium typography layouts for output display blocks
    direction_emoji = "🟢" if metrics["direction"] == "BULLISH" else "🔴" if metrics["direction"] == "BEARISH" else "⚪"
    price_fmt = f"{metrics['latest_close']:.4f}" if clean_ticker in FOREX_PAIRS else f"${metrics['latest_close']:,.2f}"
    sma_fmt = f"{metrics['sma_20']:.4f}" if clean_ticker in FOREX_PAIRS else f"${metrics['sma_20']:,.2f}"
    
    response_msg = (
        f"📊 **MACRO ENGINE PROFILE: {clean_ticker}**\n"
        f"📅 _As of: {metrics['last_update']}_\n"
        f"‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\n"
        f"💵 **Latest Close:** `{price_fmt}`\n"
        f"📉 **20-Day SMA:** `{sma_fmt}`\n"
        f"🎚️ **Z-Score:** `{metrics['z_score']:+}`\n"
        f"🚀 **24h Momentum:** `{metrics['momentum_pct']:+}%`\n\n"
        f"🤖 **Directional Bias:** {direction_emoji} `{metrics['direction']}`\n"
        f"🎯 **Probability Score:** `{metrics['probability']}%`\n"
        f"🛡️ **Engine Confidence:** `{metrics['confidence']}%`"
    )
    
    await update.message.reply_text(response_msg, parse_mode="Markdown")

def run_telegram_bot():
    """Starts the Telegram bot in a background thread."""
    if not TOKEN:
        logger.error("CRITICAL: TELEGRAM_BOT_TOKEN environment variable is missing.")
        return
        
    app = Application.builder().token(TOKEN).build()
    
    # Handlers configurations
    app.add_handler(CommandHandler("start", start_command))
    
    # Regex text catch-all filters ensure both strings and command inputs are directed properly
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), asset_bias_handler))
    app.add_handler(MessageHandler(filters.COMMAND, asset_bias_handler))
    
    logger.info("🤖 Macro Engine Telegram worker activated and listening...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(app.run_polling())

# --- Main ---
if __name__ == "__main__":
    # Start Telegram bot in a background thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Flask server running on port {port}")
    flask_app.run(host="0.0.0.0", port=port)
