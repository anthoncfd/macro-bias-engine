"""
MACRO BIAS ENGINE - Telegram Bot (Final, Robust)
"""
import os
import sys
import logging
import threading
import time
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ─── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── Path Setup ──────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

# ─── Token ──────────────────────────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN missing!")
    sys.exit(1)
logger.info("✅ Token loaded")

# ─── Import market_prices (with error handling) ──────────────────────
try:
    from src.ingestion.market_prices import ASSETS, FOREX_PAIRS, fetch_live_price
    from src.analytics.bias_engine import calculate_bias_for_asset
    logger.info("✅ market_prices and bias_engine loaded")
except Exception as e:
    logger.error(f"❌ Import failed: {e}", exc_info=True)
    sys.exit(1)

# ─── Flask App (keep‑alive) ───────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Bot is running"

@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route('/ping')
def ping():
    return "Pong", 200

@flask_app.route('/debug')
def debug():
    return jsonify({"status": "running", "token_set": bool(TOKEN), "time": time.time()})

# ─── Handlers ────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏛️ Macro Bias Engine. Send /eurusd or just type EURUSD.")

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot is alive.")

async def asset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text
    ticker = raw.replace("/", "").strip().upper()
    logger.info(f"📩 Received: {raw} → {ticker}")

    if ticker not in ASSETS:
        if raw.startswith("/"):
            await update.message.reply_text(f"❌ Asset '{ticker}' not tracked.")
        return

    await update.message.reply_chat_action("typing")
    try:
        metrics = calculate_bias_for_asset(ticker)
        if metrics.get("status") != "SUCCESS":
            await update.message.reply_text(f"⚠️ {metrics.get('message')}")
            return

        is_fx = ticker in FOREX_PAIRS if FOREX_PAIRS else False
        close_str = f"{metrics['latest_close']:.4f}" if is_fx else f"${metrics['latest_close']:,.2f}"
        sma_str = f"{metrics['sma_20']:.4f}" if is_fx else f"${metrics['sma_20']:,.2f}"
        dir_emoji = "🟢" if metrics["direction"] == "BULLISH" else "🔴" if metrics["direction"] == "BEARISH" else "⚪"

        # Fetch live price
        tickers = ASSETS.get(ticker, [])
        live = fetch_live_price(tickers)
        live_str = f"{live:.4f}" if live and is_fx else f"${live:,.2f}" if live else "❌ Unavailable"

        reply = (
            f"📊 **MACRO PROFILE: {ticker}**\n"
            f"📅 As of: {metrics.get('last_update', 'N/A')}\n\n"
            f"💰 **Live:** `{live_str}`\n"
            f"💵 **Close:** `{close_str}`\n"
            f"📉 **20‑Day SMA:** `{sma_str}`\n"
            f"🎚️ **Z‑Score:** `{metrics['z_score']:+.2f}`\n"
            f"🚀 **Momentum:** `{metrics['momentum_pct']:+.2f}%`\n\n"
            f"🤖 **Direction:** {dir_emoji} `{metrics['direction']}`\n"
            f"🎯 **Probability:** `{metrics['probability']:.1f}%`\n"
            f"🛡️ **Confidence:** `{metrics['confidence']:.1f}%`"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")
        logger.info(f"✅ Sent report for {ticker}")
    except Exception as e:
        logger.error(f"❌ Handler error: {e}", exc_info=True)
        await update.message.reply_text("❌ Internal error. Check logs.")

async def matrix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (optional, can be added later)
    await update.message.reply_text("Matrix command coming soon.")

# ─── Flask runner (background) ────────────────────────────────────────
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Flask starting on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

# ─── Bot runner (main thread) ──────────────────────────────────────────
def run_bot():
    logger.info("🤖 Starting Telegram bot in main thread...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("bias", matrix))
    # Register all asset commands
    for asset in ASSETS:
        app.add_handler(CommandHandler(asset.lower(), asset_handler))
    # Catch-all for text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, asset_handler))
    # Catch-all for unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, asset_handler))

    logger.info("🤖 Starting polling (main thread)...")
    app.run_polling()

# ─── Main ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Flask in background
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🔄 Flask thread started")
    # Bot in main thread (blocking)
    run_bot()
