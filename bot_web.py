"""
MACRO BIAS ENGINE - Telegram Bot (V3-Shadow Mode)
Launches immediately with professional attribution display,
silently accumulates evidence for validation.
"""
import os
import sys
import logging
import threading
import asyncio
from datetime import datetime

from flask import Flask
from telegram.ext import Application, CommandHandler

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

from src.analytics.macro_bias_engine_v3 import MacroBiasEngineV3Shadow
from src.pipeline.outcome_resolver import OutcomeResolver
from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import FOREX_PAIRS
from src.ingestion.macro_data_fetcher import fetch_macro_data

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logging.error("❌ TELEGRAM_BOT_TOKEN not set.")
    sys.exit(1)

# --- Flask App (for Render keep-alive) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Macro Bias Bot V3-Shadow is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route('/ping')
def ping():
    return "Pong", 200

# --- Initialize Engine ---
try:
    db = get_supabase_client()
    engine = MacroBiasEngineV3Shadow(db_client=db)
    resolver = OutcomeResolver(db_client=db, attribution_engine=engine.attribution)
    print("✅ Macro Bias Engine V3-Shadow initialized")
except Exception as e:
    print(f"⚠️ Engine initialization warning: {e}")
    engine = MacroBiasEngineV3Shadow(db_client=None)
    resolver = OutcomeResolver(db_client=None, attribution_engine=engine.attribution)

# --- Formatting Helpers ---
def format_price(ticker, price):
    if price is None:
        return "N/A"
    return f"{price:.4f}" if ticker in FOREX_PAIRS else f"${price:,.2f}"

# --- Command Handlers ---
async def start(update, context):
    await update.message.reply_text(
        "🤖 *Macro Bias Engine V3-Shadow*\n\n"
        "Commands:\n"
        "`/eurusd` - EUR/USD bias\n"
        "`/gbpusd` - GBP/USD bias\n"
        "`/audusd` - AUD/USD bias\n"
        "`/gold` - Gold bias\n"
        "`/btc` - Bitcoin bias\n"
        "`/bias` - Full market matrix\n"
        "`/help` - This message\n\n"
        "⚡ *Shadow Mode:* Attribution data is being accumulated.\n"
        "📊 Validation dashboard activates at 30 predictions.",
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
    
    await update.message.reply_text(f"⏳ Analyzing {asset}...")
    
    macro_data = fetch_macro_data()
    analysis = engine.generate_trading_report(macro_data)
    
    asset_data = analysis["assets"].get(asset)
    if not asset_data:
        await update.message.reply_text(f"❌ No data for {asset}")
        return
    
    direction = asset_data["direction"]
    bias = asset_data["bias"]
    shares = asset_data["shares"]
    
    emoji = "🟢" if direction == "BULLISH" else "🔴" if direction == "BEARISH" else "⚪"
    
    report = f"🏛️ *MACRO BIAS REPORT*\n"
    report += f"─── {asset} ───\n\n"
    report += f"🎯 *Direction:* {emoji} {direction}\n"
    report += f"📊 *Signal:* {bias:.2f}\n\n"
    report += f"📊 *Attribution:*\n"
    report += f"   🔧 Technical: {shares['technical']:.1f}%\n"
    report += f"   🌍 Macro: {shares['macro']:.1f}%\n"
    report += f"   🏛️ Regime: {shares['regime_context']:.1f}%\n\n"
    report += f"📅 {analysis['timestamp'][:10]}"
    
    await update.message.reply_text(report, parse_mode="Markdown")

async def full_bias_matrix(update, context):
    await update.message.reply_text("🏛️ Generating full matrix...")
    
    macro_data = fetch_macro_data()
    analysis = engine.generate_trading_report(macro_data)
    audit_report = resolver.fetch_active_attribution_report()
    
    report = "🏛️ *MACRO BIAS MATRIX (V3-Shadow)*\n"
    report += f"📅 {analysis['timestamp'][:10]} | Horizon: 20 Days\n"
    report += "──────────────────────────\n\n"
    
    for asset, data in analysis["assets"].items():
        direction = data["direction"]
        emoji = "🟢" if direction == "BULLISH" else "🔴" if direction == "BEARISH" else "⚪"
        bias = data["bias"]
        report += f"{emoji} *{asset}* ── {direction} (`{bias:.2f}`)\n"
        report += f"   └─ Tech `{data['shares']['technical']}%` | Macro `{data['shares']['macro']}%` | Regime `{data['shares']['regime_context']}%`\n\n"
    
    report += "──────────────────────────\n"
    
    if audit_report.get("status") == "Active Validation":
        report += "📈 *LIVE VALIDATION*\n"
        report += f"   • Samples: `{audit_report['sample_size']}`\n"
        report += f"   • Hit Rate: `{audit_report['system_hit_rate']*100:.1f}%`\n"
        report += f"   • R²: `{audit_report['variance_explained_r2']:.3f}`\n\n"
        report += "📊 *Information Coefficients:*\n"
        report += f"   • Tech IC: `{audit_report['information_coefficients']['technical_ic']}`\n"
        report += f"   • Macro IC: `{audit_report['information_coefficients']['macro_ic']}`\n"
        report += f"   • Regime IC: `{audit_report['information_coefficients']['regime_ic']}`\n"
    else:
        report += f"⏳ *Shadow Data:* {audit_report.get('sample_size', 0)}/30 predictions\n"
        report += "   Validation activates automatically at 30 resolved predictions."
    
    await update.message.reply_text(report, parse_mode="Markdown")

# --- Telegram Bot Runner ---
def run_telegram_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("bias", full_bias_matrix))
    
    for cmd in ["eurusd","gbpusd","audusd","eurjpy","gbpjpy","cadjpy","cadchf",
                "gold","silver","btc","nikkei","dow"]:
        app.add_handler(CommandHandler(cmd, asset_command))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print("🤖 Telegram bot is running (V3-Shadow Mode)!")
    loop.run_until_complete(app.run_polling())

# --- Main ---
if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Flask server running on port {port}")
    flask_app.run(host="0.0.0.0", port=port)
