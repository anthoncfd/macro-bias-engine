"""
MACRO BIAS ENGINE - Telegram Bot with Live Price Support
Shows both current live price and daily close.
"""
import os
import sys
import logging
import threading
import asyncio
import time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# PATH SETUP
# ============================================
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

# ============================================
# TELEGRAM TOKEN
# ============================================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
    sys.exit(1)

# ============================================
# FLASK APP (Keep‑alive for Render)
# ============================================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Macro Bias Bot is running with Live Prices!"

@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route('/ping')
def ping():
    return "Pong", 200

# ============================================
# IMPORTS (Lazy load)
# ============================================
def get_engine():
    try:
        from src.analytics.bias_engine import calculate_bias_for_asset, run_bias_engine
        from src.ingestion.market_prices import ASSETS, FOREX_PAIRS, fetch_live_price
        return calculate_bias_for_asset, run_bias_engine, ASSETS, FOREX_PAIRS, fetch_live_price
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return None, None, None, None, None

calc_bias, run_bias, ASSETS, FOREX_PAIRS, fetch_live = get_engine()

# ============================================
# TELEGRAM HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏛️ **MACRO BIAS ENGINE**\n\n"
        "Send a ticker like `/eurusd`, `/gold`, `/btc`\n"
        "or just type `EURUSD`.\n\n"
        "Shows **Live Price** + **Close Price** + bias metrics.",
        parse_mode="Markdown"
    )

async def asset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text
    ticker = raw.replace("/", "").strip().upper()
    logger.info(f"📩 Received: '{raw}' → {ticker}")

    if calc_bias is None or ASSETS is None:
        await update.message.reply_text("❌ Engine not loaded. Check logs.")
        return

    if ticker not in ASSETS:
        if raw.startswith("/"):
            await update.message.reply_text(f"❌ `{ticker}` not tracked.", parse_mode="Markdown")
        return

    await update.message.reply_chat_action("typing")

    try:
        # 1. Get bias metrics (closing‑price based)
        metrics = calc_bias(ticker)
        if metrics.get("status") != "SUCCESS":
            await update.message.reply_text(
                f"⚠️ Insufficient data for {ticker}: {metrics.get('message')}",
                parse_mode="Markdown"
            )
            return

        # 2. Fetch live price (on‑demand)
        live_price = None
        if fetch_live:
            live_price = fetch_live(ASSETS[ticker])

        # 3. Format response
        direction = metrics["direction"]
        emoji = "🟢" if direction == "BULLISH" else "🔴" if direction == "BEARISH" else "⚪"
        is_forex = ticker in FOREX_PAIRS if FOREX_PAIRS else False

        close_fmt = f"{metrics['latest_close']:.4f}" if is_forex else f"${metrics['latest_close']:,.2f}"
        live_fmt = f"{live_price:.4f}" if live_price and is_forex else f"${live_price:,.2f}" if live_price else "N/A"

        report = (
            f"📊 **MACRO PROFILE: {ticker}**\n"
            f"📅 _As of: {metrics.get('last_update', 'N/A')}_\n\n"
            f"💵 **Live Price:** `{live_fmt}`\n"
            f"💵 **Close Price:** `{close_fmt}`\n"
            f"📉 **20‑Day SMA:** `{close_fmt}`\n"
            f"🎚️ **Z‑Score:** `{metrics['z_score']:+.2f}`\n"
            f"🚀 **Momentum:** `{metrics['momentum_pct']:+.2f}%`\n\n"
            f"🤖 **Bias:** {emoji} `{direction}`\n"
            f"🎯 **Probability:** `{metrics['probability']:.1f}%`\n"
            f"🛡️ **Confidence:** `{metrics['confidence']:.1f}%`"
        )
        await update.message.reply_text(report, parse_mode="Markdown")
        logger.info(f"✅ Sent report for {ticker}")

    except Exception as e:
        logger.error(f"❌ Error processing {ticker}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

async def bias_matrix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Generating full matrix...")
    if run_bias is None:
        await update.message.reply_text("❌ Engine not loaded.")
        return
    try:
        results = run_bias()
        report = "🏛️ **MACRO BIAS MATRIX**\n\n"
        for ticker, data in results.items():
            if data.get("status") == "SUCCESS":
                emoji = "🟢" if data["direction"] == "BULLISH" else "🔴" if data["direction"] == "BEARISH" else "⚪"
                report += f"{emoji} {ticker}: {data['direction']} ({data['probability']:.0f}%)\n"
            else:
                report += f"⚪ {ticker}: {data.get('message', 'No data')}\n"
        await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Matrix error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

# ============================================
# TELEGRAM BOT THREAD
# ============================================

def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("bias", bias_matrix))
    
    # Register asset commands and text handler
    if ASSETS:
        for asset in ASSETS.keys():
            app.add_handler(CommandHandler(asset.lower(), asset_handler))
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), asset_handler))
    app.add_handler(MessageHandler(filters.COMMAND, asset_handler))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    logger.info("🤖 Telegram bot started with Live Price support!")
    loop.run_until_complete(app.run_polling())

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Flask server on port {port}")
    flask_app.run(host="0.0.0.0", port=port)
