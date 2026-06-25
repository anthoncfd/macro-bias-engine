"""
MACRO BIAS ENGINE - Telegram Bot (Fixed Signal Handler Issue)
"""
import os
import sys
import logging
import threading
import asyncio
import time
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ─── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─── Path Setup ──────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)
logger.info(f"📁 Repo root: {REPO_ROOT}")

# ─── Token ──────────────────────────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN missing!")
    sys.exit(1)
logger.info("✅ Token loaded")

# ─── Flask App ──────────────────────────────────────────────────────────
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

@flask_app.route('/debug')
def debug():
    return jsonify({
        "status": "running",
        "token_present": bool(TOKEN),
        "time": time.time()
    })

# ─── Lazy imports ──────────────────────────────────────────────────────
def load_bias_engine():
    try:
        from src.analytics.bias_engine import calculate_bias_for_asset, run_bias_engine
        from src.ingestion.market_prices import ASSETS, FOREX_PAIRS
        return calculate_bias_for_asset, run_bias_engine, ASSETS, FOREX_PAIRS
    except Exception as e:
        logger.error(f"❌ Import error: {e}", exc_info=True)
        return None, None, None, None

calc, run, ASSETS, FOREX = load_bias_engine()
if calc is None:
    logger.error("❌ Bias engine not loaded! Bot will not work.")

# ─── Handlers ────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏛️ **MACRO BIAS ENGINE**\n\n"
        "Send /eurusd or just type EURUSD",
        parse_mode="Markdown"
    )
    logger.info(f"📱 /start from {update.effective_user.username}")

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot is alive.")
    logger.info("📱 /ping")

async def asset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text
    ticker = raw.replace("/", "").strip().upper()
    logger.info(f"📩 Received: '{raw}' → '{ticker}'")

    if calc is None or ASSETS is None:
        await update.message.reply_text("❌ Bias engine not loaded.")
        return

    if ticker not in ASSETS:
        if raw.startswith("/"):
            await update.message.reply_text(f"❌ Asset '{ticker}' not tracked.")
        return

    await update.message.reply_chat_action("typing")
    try:
        metrics = calc(ticker)
        if metrics.get("status") != "SUCCESS":
            await update.message.reply_text(f"⚠️ {metrics.get('message')}")
            return

        is_fx = ticker in FOREX if FOREX else False
        price_str = f"{metrics['latest_close']:.4f}" if is_fx else f"${metrics['latest_close']:,.2f}"
        sma_str = f"{metrics['sma_20']:.4f}" if is_fx else f"${metrics['sma_20']:,.2f}"
        dir_emoji = "🟢" if metrics["direction"] == "BULLISH" else "🔴" if metrics["direction"] == "BEARISH" else "⚪"

        reply = (
            f"📊 **MACRO PROFILE: {ticker}**\n"
            f"📅 As of: {metrics.get('last_update', 'N/A')}\n\n"
            f"💵 Close: `{price_str}`\n"
            f"📉 20‑Day SMA: `{sma_str}`\n"
            f"🎚️ Z‑Score: `{metrics['z_score']:+.2f}`\n"
            f"🚀 Momentum: `{metrics['momentum_pct']:+.2f}%`\n\n"
            f"🤖 Direction: {dir_emoji} `{metrics['direction']}`\n"
            f"🎯 Probability: `{metrics['probability']:.1f}%`\n"
            f"🛡️ Confidence: `{metrics['confidence']:.1f}%`"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")
        logger.info(f"✅ Sent report for {ticker}")
    except Exception as e:
        logger.error(f"❌ Error in handler: {e}", exc_info=True)
        await update.message.reply_text("❌ Internal error. Check logs.")

async def matrix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Generating matrix...")
    if run is None:
        await update.message.reply_text("❌ Engine not loaded.")
        return
    try:
        results = run()
        report = "🏛️ **MACRO BIAS MATRIX**\n\n"
        for t, d in results.items():
            if d.get("status") == "SUCCESS":
                emoji = "🟢" if d["direction"] == "BULLISH" else "🔴" if d["direction"] == "BEARISH" else "⚪"
                report += f"{emoji} {t}: {d['direction']} ({d['probability']:.0f}%)\n"
            else:
                report += f"⚪ {t}: {d.get('message', 'No data')}\n"
        await update.message.reply_text(report, parse_mode="Markdown")
        logger.info("✅ Sent matrix")
    except Exception as e:
        logger.error(f"❌ Matrix error: {e}", exc_info=True)

# ─── Bot Runner ─────────────────────────────────────────────────────────
def run_bot():
    logger.info("🚀 Starting Telegram bot thread...")
    try:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", start))
        app.add_handler(CommandHandler("ping", ping_cmd))
        app.add_handler(CommandHandler("bias", matrix))
        if ASSETS:
            for a in ASSETS.keys():
                app.add_handler(CommandHandler(a.lower(), asset_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, asset_handler))
        app.add_handler(MessageHandler(filters.COMMAND, asset_handler))

        logger.info("🤖 Bot starting poller (signal_handlers=False)...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # 🔥 CRITICAL FIX: disable signal handlers to avoid thread error
        loop.run_until_complete(app.run_polling(signal_handlers=False))
    except Exception as e:
        logger.error(f"💥 Bot crashed: {e}", exc_info=True)

# ─── Main ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start bot in background thread
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    logger.info("🔄 Bot thread started, waiting 5s...")
    time.sleep(5)
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Flask starting on port {port}")
    flask_app.run(host="0.0.0.0", port=port)
