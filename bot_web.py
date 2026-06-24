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

# 3. Core Analytical Signal Formatters
def generate_telegram_markdown(ticker: str, data: dict) -> str:
    """Transforms structural raw macro engine profiles into highly polished Telegram copy."""
    direction_emoji = "🟢 BULLISH" if data["direction"] == "BULLISH" else "🔴 BEARISH" if data["direction"] == "BEARISH" else "⚪ NEUTRAL"
    
    msg = (
        f"📊 *MACRO PROFILE: {ticker}*\n"
        f"📅 _As of: {data['last_update']}_\n"
        f"‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\n"
        f"💵 *Close:* {data['latest_close']:.4f}\n"
        f"📉 *20-Day SMA:* {data['sma_20']:.4f}\n"
        f"🎚️ *Z-Score Boundary:* {data['z_score']:.2f}\n"
        f"🚀 *Momentum Velocity:* {data['momentum_pct']:+.2f}%\n\n"
        f"🤖 *Engine Direction:* {direction_emoji}\n"
        f"🎯 *Probability Weight:* {data['probability']:.1f}%\n"
        f"🛡️ *System Confidence:* {data['confidence']:.1f}%\n"
    )
    return msg

# 4. Telegram Asynchronous Interactive Command Handlers
async def handle_bias_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes asset requests by pulling from the multi-factor analytical engine model."""
    user_input = " ".join(context.args).upper().strip() if context.args else ""
    
    # Extract structural route trigger name from raw command handle text fallback
    if not user_input and update.message and update.message.text:
        raw_cmd = update.message.text.split()[0].lower()
        if len(raw_cmd) > 1:
            user_input = raw_cmd[1:].upper()

    if not user_input:
        await update.message.reply_text("⚠️ Please pass a valid asset ticker. (Example: /gbpusd)")
        return

    try:
        from src.analytics.bias_engine import calculate_bias_for_asset
        
        await update.message.reply_chat_action("typing")
        metrics = calculate_bias_for_asset(user_input)
        
        if metrics.get("status") == "SUCCESS":
            formatted_text = generate_telegram_markdown(user_input, metrics)
            await update.message.reply_text(formatted_text, parse_mode="Markdown")
        elif metrics.get("status") == "SKIP" or metrics.get("status") == "ERROR":
            await update.message.reply_text(f"❌ Core processing fault: {metrics.get('message')}")
        else:
            await update.message.reply_text(f"🔍 Ticker '{user_input}' could not be evaluated by the macro matrix.")
            
    except Exception as e:
        logger.error(f"Telegram execution exception context: {e}")
        await update.message.reply_text("💥 Internal processor calculation exception occurred.")

# 5. Background Thread Core Polling Loop
def run_telegram_bot():
    """Initializes and runs the background bot process using an active event loop."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "8891572600:AAFLd6ba9DBj0w8rcrWQqMo6Q6QV8ib727I")
    
    # Allocate a completely independent, dedicated event thread context loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = ApplicationBuilder().token(token).build()
    
    # Universal fallback route matching pattern to process arbitrary currency profiles
    app.add_handler(CommandHandler("gbpusd", handle_bias_command))
    app.add_handler(CommandHandler("eurusd", handle_bias_command))
    app.add_handler(CommandHandler("eurjpy", handle_bias_command))
    
    # Catch-all text generic string router for commands not explicitly mapped above
    for asset in ["AUDUSD", "GBPJPY", "CADJPY", "CADCHF", "XAUUSD", "XAGUSD", "BTCUSD", "JP225", "US30"]:
        app.add_handler(CommandHandler(asset.lower(), handle_bias_command))

    logger.info("🤖 Polling engine fully active. Overriding competing handles...")
    
    [span_2](start_span)# Step-by-step lifecycle initialization block[span_2](end_span)
    loop.run_until_complete(app.initialize())
    
    [span_3](start_span)# HARDENED EXTENSION FIX: Passing drop_pending_updates=True instructs Telegram 
    # to drop old updates and disconnect the competing container[span_3](end_span).
    loop.run_until_complete(app.updater.[span_4](start_span)start_polling(drop_pending_updates=True))[span_4](end_span)
    loop.run_until_complete(app.start())
    
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.run_until_complete(app.stop())
        loop.run_until_complete(app.shutdown())
        loop.close()

# 6. Monitored Main Core Orchestration Block
if __name__ == "__main__":
    # 1. Spin up the background bot daemon thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    # 2. Spin up the primary Flask thread server web runner 
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"📡 Web routing framework initializing server loop on port: {port}")
    web_app.run(host="0.0.0.0", port=port, debug=False)
