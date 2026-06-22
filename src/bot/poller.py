"""
MACRO BIAS ENGINE - Telegram Bot (Polling Mode)
Listens for Telegram commands and responds with bias reports.
"""
import os
import sys
import asyncio
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext

# Import the Bias Engine
from src.analytics.bias_engine import run_bias_engine
from src.ingestion.market_prices import FOREX_PAIRS

# --- Configuration ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not set in environment variables.")
    sys.exit(1)

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def format_price(ticker, price):
    """Format price based on asset type."""
    if ticker in FOREX_PAIRS:
        return f"{price:.4f}"
    else:
        return f"${price:,.2f}"

def format_bias_report(bias_data):
    """Format the bias report for Telegram."""
    ticker = bias_data.get("ticker", "Unknown")
    direction = bias_data.get("direction", "NEUTRAL")
    probability = bias_data.get("probability", 0)
    confidence = bias_data.get("confidence", 0)
    z_score = bias_data.get("z_score", 0)
    price = bias_data.get("latest_close", 0)
    momentum = bias_data.get("momentum_pct", 0)
    
    # Emoji based on direction
    if direction == "BULLISH":
        emoji = "🟢"
        direction_text = "BULLISH 📈"
    elif direction == "BEARISH":
        emoji = "🔴"
        direction_text = "BEARISH 📉"
    else:
        emoji = "⚪"
        direction_text = "NEUTRAL ⏸️"
    
    # Confidence bar
    conf_bar = "█" * int(confidence / 10) + "░" * (10 - int(confidence / 10))
    
    # Format price
    price_str = format_price(ticker, price)
    
    # Build report
    report = (
        f"🏛️ *MACRO BIAS REPORT*\n"
        f"─── {ticker} ───\n\n"
        f"📊 *Price:* {price_str}\n"
        f"🎯 *Direction:* {emoji} {direction_text}\n"
        f"📈 *Probability:* {probability:.1f}%\n"
        f"📊 *Confidence:* {confidence:.1f}% {conf_bar}\n"
        f"⚡ *Momentum:* {momentum:+.2f}%\n"
        f"📐 *Z-Score:* {z_score:+.2f}\n"
        f"🕐 *Updated:* {bias_data.get('last_update', 'N/A')}\n"
        f"\n_Data from Macro Bias Engine v1.0_"
    )
    return report

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_message = (
        "🤖 *Macro Bias Engine*\n\n"
        "Welcome to your quantitative macro intelligence bot.\n\n"
        "*Available Commands:*\n"
        "`/eurusd` - EUR/USD bias report\n"
        "`/gbpusd` - GBP/USD bias report\n"
        "`/audusd` - AUD/USD bias report\n"
        "`/eurjpy` - EUR/JPY bias report\n"
        "`/gbpjpy` - GBP/JPY bias report\n"
        "`/cadjpy` - CAD/JPY bias report\n"
        "`/cadchf` - CAD/CHF bias report\n"
        "`/gold` - Gold (XAUUSD) bias report\n"
        "`/silver` - Silver (XAGUSD) bias report\n"
        "`/btc` - Bitcoin bias report\n"
        "`/nikkei` - Nikkei 225 bias report\n"
        "`/dow` - Dow Jones bias report\n"
        "`/bias` - Complete market matrix\n"
        "`/help` - Show this message"
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await start(update, context)

async def bias_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate bias report for a specific asset."""
    # Get the asset name from the command
    command = update.message.text.strip().lower()
    asset_map = {
        "/eurusd": "EURUSD",
        "/gbpusd": "GBPUSD",
        "/audusd": "AUDUSD",
        "/eurjpy": "EURJPY",
        "/gbpjpy": "GBPJPY",
        "/cadjpy": "CADJPY",
        "/cadchf": "CADCHF",
        "/gold": "XAUUSD",
        "/silver": "XAGUSD",
        "/btc": "BTCUSD",
        "/nikkei": "JP225",
        "/dow": "US30"
    }
    
    asset = asset_map.get(command)
    if not asset:
        await update.message.reply_text("❌ Unknown asset. Use /help for available commands.")
        return
    
    await update.message.reply_text(f"⏳ Fetching bias report for {asset}...")
    
    try:
        # Run the bias engine and get results
        results = run_bias_engine()
        bias_data = results.get(asset)
        
        if not bias_data or bias_data.get("status") != "SUCCESS":
            if bias_data and bias_data.get("status") == "INSUFFICIENT_DATA":
                msg = f"⚠️ Insufficient data for {asset}. Need 10 days of history, have {bias_data.get('data_points', 0)}."
            else:
                msg = f"❌ No bias data available for {asset}."
            await update.message.reply_text(msg)
            return
        
        report = format_bias_report(bias_data)
        await update.message.reply_text(report, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating report: {str(e)}")

async def full_bias_matrix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bias command - shows all assets."""
    await update.message.reply_text("⏳ Generating full market matrix...")
    
    try:
        results = run_bias_engine()
        
        # Build summary table
        report = "🏛️ *MACRO BIAS MATRIX*\n"
        report += "─── All Assets ───\n\n"
        
        for ticker, data in results.items():
            if data.get("status") == "SUCCESS":
                direction = data["direction"]
                prob = data["probability"]
                conf = data["confidence"]
                
                if direction == "BULLISH":
                    emoji = "🟢"
                elif direction == "BEARISH":
                    emoji = "🔴"
                else:
                    emoji = "⚪"
                
                price_str = format_price(ticker, data["latest_close"])
                report += f"{emoji} *{ticker}* | {price_str} | {direction} | {prob:.0f}% | {conf:.0f}%\n"
            else:
                report += f"⚫ *{ticker}* | Insufficient data\n"
        
        report += f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}_"
        await update.message.reply_text(report, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating matrix: {str(e)}")

# --- Main Entry Point ---
async def main():
    """Initialize and run the bot."""
    # Create Application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("bias", full_bias_matrix))
    
    # Asset-specific handlers
    asset_commands = [
        "eurusd", "gbpusd", "audusd", "eurjpy", "gbpjpy", "cadjpy", "cadchf",
        "gold", "silver", "btc", "nikkei", "dow"
    ]
    for cmd in asset_commands:
        app.add_handler(CommandHandler(cmd, bias_report))
    
    # Initialize and start the bot
    await app.initialize()
    await app.start()
    
    print("🤖 Macro Bias Bot is running!")
    print("📊 Press Ctrl+C to stop.")
    
    # Run polling (this will block until interrupted)
    await app.updater.start_polling()
    
    # Keep the bot running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
