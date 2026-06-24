"""
MACRO BIAS ENGINE - Web Entrypoint & Background Polling Daemon
Runs a lightweight Flask web loop for Render HTTP health binding,
alongside an asynchronous background thread driving the Telegram event stream.
"""
import asyncio
import logging
import os
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update

# 1. Logging Infrastructure Configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. Flask Application Setup (Required for Render Health Bindings)
web_app = Flask(__name__)

@web_app.route("/")
def health_check():
    """Handles platform route monitoring checks."""
    return "MACRO_BIAS_ENGINE_ALIVE", 200

@web_app.route("/health")
def internal_health():
    """Backup endpoint path for service verification checks."""
    return {"status": "healthy", "engine": "active"}, 200

# 3. Layout Formatting Output Engines
def generate_help_markdown() -> str:
    """Generates an elegant operational manual for the chat interface."""
    msg = (
        "🤖 *MACRO BIAS ENGINE DIRECTORY*\n"
        "‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\n"
        "Query quantitative asset deviation statistics using the following handles:\n\n"
        "💱 *Forex Pairs:*\n"
        "• `/eurusd` | `/gbpusd` | `/audusd` \n"
        "• `/eurjpy` | `/gbpjpy` | `/cadjpy` | `/cadchf` \n\n"
        "🪙 *Commodities & Crypto:*\n"
        "• `/xauusd` _(Spot Gold)_\n"
        "• `/xagusd` _(Spot Silver)_\n"
        "• `/btcusd` _(Bitcoin Context)_\n\n"
        "📈 *Equity Indices:*\n"
        "• `/us30` | `/jp225` \n\n"
        "⚙️ *System Macros:*\n"
        "• `/bias [ticker]` — Run an arbitrary pair custom evaluation\n"
        "• `/help` — Output this active documentation matrix"
    )
    return msg

def generate_telegram_markdown(ticker: str, data: dict) -> str:
    """Transforms raw empirical metrics into professionally precise copy layouts."""
    direction_emoji = "🟢 BULLISH" if data["direction"] == "BULLISH" else "🔴 BEARISH" if data["direction"] == "BEARISH" else "⚪ NEUTRAL"

    msg = (
        f"📊 *MACRO PROFILE: {ticker}*\n"
        f"📅 _As of: {data['last_update']}_\n"
        f"‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\n"
        f"💵 *Current Price:* {data['latest_close']:.4f}\n"
        f"📉 *20-Day SMA:* {data['sma_20']:.4f}\n"
        f"🎚️ *Z-Score Boundary:* {data['z_score']:.2f}\n"
        f"🚀 *Momentum Velocity:* {data['momentum_pct']:+.2f}%\n\n"
        f"🤖 *Engine Direction:* {direction_emoji}\n"
        f"🎯 *Directional Score:* {data['directional_score']:.1f}/100\n"
        f"⚡ *Signal Strength Rank:* {data['signal_strength']:.1f}%\n"
        f"🛡️ *System Conviction:* {data.get('conviction', 'LOW')}\n"
    )
    return msg

# 4. Telegram Interactive Command Handlers
async def handle_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Outputs system documentation cleanly."""
    await update.message.reply_text(generate_help_markdown(), parse_mode="Markdown")

async def handle_bias_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes asset requests by pulling true live market price arrays dynamically."""
    user_input = " ".join(context.args).upper().strip() if context.args else ""
    
    # Text router tracking fallback logic
    if not user_input and update.message and update.message.text:
        raw_cmd = update.message.text.split()[0].lower()
        if len(raw_cmd) > 1:
            user_input = raw_cmd[1:].upper()

    if not user_input or user_input == "BIAS":
        await update.message.reply_text("⚠️ Please pass a valid asset ticker. (Example: `/bias EURUSD` or `/eurusd`)", parse_mode="Markdown")
        return

    try:
        from src.analytics.bias_engine import calculate_bias_for_asset
        # Dynamic middleware hook connecting to your live raw provider API or scraper feed
        from src.ingestion.market_prices import fetch_live_feed_price 
        
        await update.message.reply_chat_action("typing")
        
        # 1. Fetch real-time market value right on demand
        live_spot_price = fetch_live_feed_price(user_input) 
        
        # 2. Route real-time price directly into the updated analytical framework
        metrics = calculate_bias_for_asset(user_input, live_price_override=live_spot_price)
        
        if metrics.get("status") == "SUCCESS":
            formatted_text = generate_telegram_markdown(user_input, metrics)
            await update.message.reply_text(formatted_text, parse_mode="Markdown")
        elif metrics.get("status") == "SKIP" or metrics.get("status") == "ERROR":
            await update.message.reply_text(f"❌ Processing fault: {metrics.get('message')}")
        else:
            await update.message.reply_text(f"🔍 Ticker '{user_input}' could not be resolved by the matrix.")
            
    except Exception as e:
        logger.error(f"Telegram execution exception context: {e}")
        await update.message.reply_text("💥 Internal processor calculation exception occurred.")

# 5. Dedicated Background Thread Lifecycle Polling Loop
def run_telegram_bot():
    """Initializes and runs the background bot process using an active event loop."""
    # 🛡️ HARDENED SECURITY FIX: Program crashes immediately if credentials aren't set up properly
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        critical_error = "CRITICAL RUNTIME ERROR: TELEGRAM_BOT_TOKEN environment variable is missing!"
        logger.critical(critical_error)
        raise RuntimeError(critical_error)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = ApplicationBuilder().token(token).build()
    
    # System operation registration commands
    app.add_handler(CommandHandler("help", handle_help_command))
    app.add_handler(CommandHandler("bias", handle_bias_command))
    
    # Explicit ticker mapping rules
    app.add_handler(CommandHandler("gbpusd", handle_bias_command))
    app.add_handler(CommandHandler("eurusd", handle_bias_command))
    app.add_handler(CommandHandler("eurjpy", handle_bias_command))
    
    for asset in ["AUDUSD", "GBPJPY", "CADJPY", "CADCHF", "XAUUSD", "XAGUSD", "BTCUSD", "JP225", "US30"]:
        app.add_handler(CommandHandler(asset.lower(), handle_bias_command))

    logger.info("🤖 Polling engine fully active. Overriding competing handles...")
    
    loop.run_until_complete(app.initialize())
    # Drop pending updates to clean old deployment web hooks out of the stack instantly
    loop.run_until_complete(app.updater.start_polling(drop_pending_updates=True))
    loop.run_until_complete(app.start())
    
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.run_until_complete(app.stop())
        loop.run_until_complete(app.shutdown())
        loop.close()

# 6. Primary Orchestration Execution block
if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"📡 Web routing framework initializing server loop on port: {port}")
    web_app.run(host="0.0.0.0", port=port, debug=False)
