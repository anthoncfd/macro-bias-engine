"""
MACRO BIAS ENGINE - Combined Web Server + Telegram Bot
Deploy on Render as a Web Service (Free Tier).
Uses Flask to respond to HTTP pings to keep the service awake.
"""
import os
import sys
import logging
import threading
import time

from flask import Flask, request, jsonify
from telegram.ext import Application, CommandHandler

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

from src.analytics.bias_engine import run_bias_engine
from src.ingestion.market_prices import FOREX_PAIRS

# --- Configuration ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logging.error("❌ TELEGRAM_BOT_TOKEN not set.")
    sys.exit(1)

# --- Flask App ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Macro Bias Bot is running 24/7!"

@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route('/ping')
def ping():
    return "Pong", 200

# --- Telegram Bot Helpers ---
def format_price(ticker, price):
    return f"{price:.4f}" if ticker in FOREX_PAIRS else f"${price:,.2f}"

def format_bias_report(bias_data):
    ticker = bias_data.get("ticker", "Unknown")
    direction = bias_data.get("direction", "NEUTRAL")
    prob = bias_data.get("probability", 0)
    conf = bias_data.get("confidence", 0)
    price = bias_data.get("latest_close", 0)
    z = bias_data.get("z_score", 0)
    mom = bias_data.get("momentum_pct", 0)
    emoji = "🟢" if direction == "BULLISH" else "🔴" if direction == "BEARISH" else "⚪"
    conf_bar = "█" * int(conf / 10) + "░" * (10 - int(conf / 10))
    return (
        f"🏛️ *MACRO BIAS REPORT*\n"
        f"─── {ticker} ───\n\n"
        f"📊 Price: {format_price(ticker, price)}\n"
        f"🎯 Direction: {emoji} {direction}\n"
        f"📈 Bullish Prob: {prob:.1f}%\n"
        f"📊 Confidence: {conf:.1f}% {conf_bar}\n"
        f"⚡ Momentum: {mom:+.2f}%\n"
        f"📐 Z-Score: {z:+.2f}\n"
        f"🕐 Updated: {bias_data.get('last_update', 'N/A')}"
    )

# --- Telegram Command Handlers ---
async def start(update, context):
    await update.message.reply_text(
        "🤖 *Macro Bias Engine*\n\n"
        "Commands: `/eurusd`, `/gbpusd`, `/audusd`, `/eurjpy`, `/gbpjpy`, `/cadjpy`, `/cadchf`,\n"
        "`/gold`, `/silver`, `/btc`, `/nikkei`, `/dow`, `/bias`, `/help`",
        parse_mode="Markdown"
    )

async def help_command(update, context):
    await start(update, context)

async def asset_command(update, context):
    cmd = update.message.text.strip().lower()
    asset_map = {
        "/eurusd": "EURUSD", "/gbpusd": "GBPUSD", "/audusd": "AUDUSD",
        "/eurjpy": "EURJPY", "/gbpjpy": "GBPJPY", "/cadjpy": "CADJPY",
        "/cadchf": "CADCHF", "/gold": "XAUUSD", "/silver": "XAGUSD",
        "/btc": "BTCUSD", "/nikkei": "JP225", "/dow": "US30"
    }
    asset = asset_map.get(cmd)
    if not asset:
        await update.message.reply_text("❌ Unknown command.")
        return
    await update.message.reply_text(f"⏳ Fetching {asset}...")
    results = run_bias_engine()
    data = results.get(asset)
    if not data or data.get("status") != "SUCCESS":
        msg = data.get("message", "No data available") if data else "No data"
        await update.message.reply_text(f"❌ {msg}")
        return
    await update.message.reply_text(format_bias_report(data), parse_mode="Markdown")

async def full_bias_matrix(update, context):
    await update.message.reply_text("⏳ Generating full matrix...")
    results = run_bias_engine()
    report = "🏛️ *MACRO BIAS MATRIX*\n\n"
    for ticker, data in results.items():
        if data.get("status") == "SUCCESS":
            emoji = "🟢" if data["direction"] == "BULLISH" else "🔴" if data["direction"] == "BEARISH" else "⚪"
            report += f"{emoji} {ticker} | Prob: {data['probability']:.0f}% | Conf: {data['confidence']:.0f}%\n"
        else:
            report += f"⚫ {ticker} | Insufficient data\n"
    await update.message.reply_text(report, parse_mode="Markdown")

# --- Telegram Bot Runner ---
def run_telegram_bot():
    """Starts the Telegram bot in a separate thread."""
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("bias", full_bias_matrix))
    for cmd in ["eurusd","gbpusd","audusd","eurjpy","gbpjpy","cadjpy","cadchf",
                "gold","silver","btc","nikkei","dow"]:
        app.add_handler(CommandHandler(cmd, asset_command))

    print("🤖 Telegram bot is running in the background!")
    app.run_polling()

# --- Main Entry Point ---
if __name__ == "__main__":
    # Start Telegram bot in a background thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # Start Flask web server (this keeps Render from sleeping)
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Flask web server running on port {port}")
    flask_app.run(host="0.0.0.0", port=port)
