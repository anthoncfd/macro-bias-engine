"""
MACRO BIAS ENGINE - Telegram Bot (Production-Ready)
Runs on Render with Flask keep-alive and asynchronous polling setups.
"""
import os
import sys
import logging
import threading
import asyncio
import time
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================
# LOGGING SETUP (Visible in Render logs)
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
logger.info(f"📁 Repo root registered: {REPO_ROOT}")

# ============================================
# TELEGRAM TOKEN VALIDATION
# ============================================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("❌ CRITICAL: TELEGRAM_BOT_TOKEN not set in environment variables!")
    sys.exit(1)
logger.info("✅ Telegram token successfully verified.")

# ============================================
# FLASK WEB SERVER CONFIG
# ============================================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Macro Bias Engine Node is fully awake and operational!", 200

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
        "token_set": bool(TOKEN),
        "timestamp": time.time()
    }), 200

# ============================================
# LAZY-LOADED CORE ENGINES
# ============================================
def get_bias_engine():
    """Safely loads core computational engines to isolate initialization locks."""
    try:
        from src.analytics.bias_engine import calculate_bias_for_asset, run_bias_engine
        from src.ingestion.market_prices import ASSETS, FOREX_PAIRS
        return calculate_bias_for_asset, run_bias_engine, ASSETS, FOREX_PAIRS
    except ImportError as e:
        logger.error(f"❌ Core engine imports failed: {e}")
        return None, None, None, None

calculate_bias_for_asset, run_bias_engine, ASSETS, FOREX_PAIRS = get_bias_engine()

# Normalize asset array structures into direct matching dictionaries
TRACKED_MAP = {}
if ASSETS:
    if isinstance(ASSETS, dict):
        TRACKED_MAP = {k.upper(): v for k, v in ASSETS.items()}
    elif isinstance(ASSETS, list):
        TRACKED_MAP = {str(asset).upper(): [asset] for asset in ASSETS}
    logger.info(f"📊 Normalized asset tracking registry mapping: {list(TRACKED_MAP.keys())}")
else:
    logger.error("❌ Target tracker arrays missing or undefined inside dependency resources.")

# ============================================
# TELEGRAM SYSTEM HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets user and renders asset query syntax options."""
    await update.message.reply_text(
        "🏛️ **MACRO BIAS ENGINE TERMINAL**\n\n"
        "Send an explicit request token parameter to evaluate structural indices:\n"
        "`/eurusd`, `/xauusd`, `/btcusd`, `/bias`\n\n"
        "Or type plain text directly: `EURUSD`",
        parse_mode="Markdown"
    )
    logger.info(f"📱 User {update.effective_user.username or 'Unknown'} called /start")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)

async def asset_bias_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes asset-specific text matches and outputs tactical momentum reports."""
    raw_text = update.message.text
    if not raw_text:
        return
        
    clean_ticker = raw_text.replace("/", "").strip().upper()
    logger.info(f"📩 Input: '{raw_text}' → Parsed Key: '{clean_ticker}'")
    
    if not calculate_bias_for_asset or not TRACKED_MAP:
        await update.message.reply_text("❌ Subsystem processing fault: calculation engines missing.")
        return
    
    if clean_ticker not in TRACKED_MAP:
        if raw_text.startswith("/"):
            await update.message.reply_text(
                f"❌ Ticker `{clean_ticker}` is outside current analytical engine metrics.\n\n"
                f"Supported: {', '.join(list(TRACKED_MAP.keys())[:6])}..."
            )
        return

    await update.message.reply_chat_action(action="typing")
    
    try:
        metrics = calculate_bias_for_asset(clean_ticker)
        logger.info(f"📊 Evaluated {clean_ticker}: Status: {metrics.get('status')}")
        
        if metrics.get("status") != "SUCCESS":
            await update.message.reply_text(
                f"⚠️ **Insufficient History Depth: {clean_ticker}**\n\n{metrics.get('message', 'No history found.')}",
                parse_mode="Markdown"
            )
            return
            
        direction = metrics["direction"]
        emoji = "🟢" if direction == "BULLISH" else "🔴" if direction == "BEARISH" else "⚪"
        
        is_forex = clean_ticker in FOREX_PAIRS if FOREX_PAIRS else False
        price_fmt = f"{metrics['latest_close']:.4f}" if is_forex else f"${metrics['latest_close']:,.2f}"
        sma_fmt = f"{metrics['sma_20']:.4f}" if is_forex else f"${metrics['sma_20']:,.2f}"
        
        response = (
            f"📊 **MACRO PROFILE: {clean_ticker}**\n"
            f"📅 _As of: {metrics.get('last_update', 'N/A')}_\n"
            f"‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\n"
            f"💵 **Close:** `{price_fmt}`\n"
            f"📉 **20-Day SMA:** `{sma_fmt}`\n"
            f"🎚️ **Z-Score Boundary:** `{metrics['z_score']:+.2f}`\n"
            f"🚀 **Momentum Velocity:** `{metrics['momentum_pct']:+.2f}%`\n\n"
            f"🤖 **Engine Direction:** {emoji} `{direction}`\n"
            f"🎯 **Probability Weight:** `{metrics['probability']:.1f}%`\n"
            f"🛡️ **System Confidence:** `{metrics['confidence']:.1f}%`"
        )
        await update.message.reply_text(response, parse_mode="Markdown")
        logger.info(f"✅ Dispatched profile output for {clean_ticker}")
        
    except Exception as e:
        logger.error(f"❌ Analytics run failed for {clean_ticker}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Processing error encountered: {str(e)[:80]}")

async def full_bias_matrix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compiles multi-asset directional status overviews."""
    await update.message.reply_text("⏳ Processing global engine metrics matrix...")
    logger.info("📊 Matrix compile operation triggered.")
    
    if not run_bias_engine:
        await update.message.reply_text("❌ Subsystem processing fault: analytical matrix engine missing.")
        return
    
    try:
        results = run_bias_engine() or {}
        report = "🏛️ **GLOBAL MACRO BIAS MATRIX**\n\n"
        for ticker, data in results.items():
            if data.get("status") == "SUCCESS":
                emoji = "🟢" if data["direction"] == "BULLISH" else "🔴" if data["direction"] == "BEARISH" else "⚪"
                report += f"{emoji} `{ticker:8}`: **{data['direction']}** ({data['probability']:.0f}%)\n"
            else:
                report += f"⚪ `{ticker:8}`: Missing metric profiles\n"
        await update.message.reply_text(report, parse_mode="Markdown")
        logger.info("✅ Dispatched global matrix summary blueprint.")
    except Exception as e:
        logger.error(f"❌ Matrix compiling crash sequence: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Matrix computation error: {str(e)[:80]}")

# ============================================
# TELEGRAM RUNTIME INITIALIZATION
# ============================================

def run_telegram_bot():
    """Initializes and keeps the background Telegram polling cycle running."""
    logger.info("🚀 Building explicit structural context for bot instance...")
    
    try:
        # Create a dedicated, isolated async loop for this background worker thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        app = Application.builder().token(TOKEN).build()
        
        # Base commands mapping
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("bias", full_bias_matrix))
        
        # Explicitly register tracking commands to prevent network dropping behavior
        if TRACKED_MAP:
            for asset in TRACKED_MAP.keys():
                app.add_handler(CommandHandler(asset.lower(), asset_bias_handler))
                
        # Universal message capture fallback routes
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), asset_bias_handler))
        app.add_handler(MessageHandler(filters.COMMAND, asset_bias_handler))
        
        logger.info("🤖 Polling engine fully active. Listening for events...")
        
        # Correctly initialize, start, and block on long-polling operations
        loop.run_until_complete(app.initialize())
        loop.run_until_complete(app.updater.start_polling())
        loop.run_until_complete(app.start())
        
        # Keep loop ticking infinitely without locking system initialization resources
        loop.run_forever()
        
    except Exception as e:
        logger.error(f"❌ Critical error in bot loop execution context: {e}", exc_info=True)

# ============================================
# SYSTEM MAIN ENTRY PIPELINE
# ============================================

if __name__ == "__main__":
    # Launch Telegram background engine worker thread safely
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    logger.info("⚙️ Telegram background event loop thread activated.")
    
    # Extract operational web serving ports from Render platform profiles
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Initializing Keep-Alive Flask listener on port: {port}")
    
    # Launch core tracking gateway application
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
