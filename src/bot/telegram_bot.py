"""
MACRO BIAS ENGINE - Hybrid Intelligence Telegram Bot
Combines quantitative technical models (Z-Score/SMA) with real-time fundamental 
economic calendar deviations (Actual vs. Forecast) to produce an institutional confluence matrix.
"""
import os
import sys
import logging
import requests
from datetime import datetime, date

# --- Path Setup ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import FOREX_PAIRS

# --- Configuration ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
FMP_API_KEY = os.environ.get("FMP_API_KEY")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN not set in environment variables.")

# Key macro components tracking core inflation, jobs, and cost of capital
HIGH_IMPACT_KEYWORDS = ["CPI", "FOMC", "INTEREST RATE", "NON FARM PAYROLL", "UNEMPLOYMENT RATE", "FED RATE", "GDP"]

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Hybrid Intelligence Analytics Core ---

def parse_clean_float(value):
    """Safely extracts numeric values from messy economic calendar strings (e.g., '3.2%', '250K')."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        clean_str = str(value).replace('%', '').replace('K', '').replace('M', '').replace('B', '').strip()
        return float(clean_str)
    except ValueError:
        return None

def analyze_macro_deviation(event_name, actual_raw, forecast_raw):
    """
    Evaluates institutional economic data deviations.
    Standard Macro Rule: Higher growth/inflation/employment is BULLISH for the domestic currency.
    Exception Rule: Higher Unemployment is BEARISH for the domestic currency.
    """
    actual = parse_clean_float(actual_raw)
    forecast = parse_clean_float(forecast_raw)
    
    if actual is None or forecast is None:
        return "NEUTRAL"
        
    deviation = actual - forecast
    if abs(deviation) < 0.001:
        return "NEUTRAL"
        
    name = event_name.upper()
    
    if "UNEMPLOYMENT" in name or "JOBLESS CLAIMS" in name:
        return "BEARISH" if deviation > 0 else "BULLISH"
        
    return "BULLISH" if deviation > 0 else "BEARISH"

def get_today_fundamental_vectors():
    """
    Fetches today's live calendar releases and determines the fundamental direction
    for affected currency components.
    Returns: Dict mapping Currency -> {'vector': 'BULLISH/BEARISH/NEUTRAL', 'event': 'Name'}
    """
    vectors = {}
    if not FMP_API_KEY:
        return vectors
        
    today_str = date.today().strftime("%Y-%m-%d")
    url = f"https://financialmodelingprep.com/api/v3/economic_calendar?from={today_str}&to={today_str}&apikey={FMP_API_KEY}"
    
    try:
        response = requests.get(url, timeout=8).json()
        if not isinstance(response, list):
            return vectors
            
        for event in response:
            event_name = event.get("event", "")
            impact = event.get("impact", "").upper()
            currency = event.get("currency", "").upper()
            
            if not currency:
                continue
                
            is_high_impact = impact == "HIGH" or any(kw in event_name.upper() for kw in HIGH_IMPACT_KEYWORDS)
            if not is_high_impact:
                continue
                
            actual = event.get("actual")
            forecast = event.get("forecast")
            
            if actual is None or str(actual).strip() == "":
                if currency not in vectors:
                    vectors[currency] = {"vector": "PENDING", "event": event_name}
                continue
                
            vector = analyze_macro_deviation(event_name, actual, forecast)
            
            if vector != "NEUTRAL":
                vectors[currency] = {"vector": vector, "event": event_name}
                
    except Exception as e:
        logging.error(f"Failed parsing real-time macroeconomic execution stream: {e}")
        
    return vectors

def calculate_hybrid_confluence(ticker, technical_bias, macro_vectors):
    """
    Merges Technical Bias with Fundamental News Vectors to establish 
    a single Confluence Matrix framework.
    """
    tech_dir = technical_bias.upper()
    fund_dir = "NEUTRAL"
    active_event = None
    
    applicable_currency = None
    if ticker in ["XAUUSD", "XAGUSD", "BTCUSD", "US30"]:
        applicable_currency = "USD"
    else:
        for curr in ["EUR", "GBP", "AUD", "JPY", "CAD", "CHF"]:
            if ticker.startswith(curr):
                applicable_currency = curr
                break

    if applicable_currency and applicable_currency in macro_vectors:
        fund_dir = macro_vectors[applicable_currency]["vector"]
        active_event = macro_vectors[applicable_currency]["event"]
        
        if applicable_currency == "USD" and ticker in ["XAUUSD", "XAGUSD", "BTCUSD", "US30"]:
            if fund_dir == "BULLISH": fund_dir = "BEARISH"
            elif fund_dir == "BEARISH": fund_dir = "BULLISH"

    if fund_dir == "PENDING":
        return "⚠️ PAUSE (PENDING NEWS)", f"Awaiting high-impact release: {active_event}"
        
    if fund_dir == "NEUTRAL":
        return tech_dir, "Pure Quant Mode (No active macro deviations)"
        
    if tech_dir == fund_dir:
        return f"💎 STRONG {tech_dir}", f"Aligned with structural data from {active_event}"
        
    if tech_dir != fund_dir and fund_dir in ["BULLISH", "BEARISH"]:
        return f"⚡ MACRO DIVERGENCE ({tech_dir})", f"Quant is {tech_dir} but {active_event} data prints {fund_dir} (Expect Sweep)"
        
    return tech_dir, "Quant Dominant Balance"

# --- Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome menu detailing the institutional framework architecture."""
    welcome = (
        r"🏛️ *MACRO BIAS ENGINE — HYBRID V1* 🤖" "\n"
        r"━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━" "\n"
        r"*Confluence Model: Pure Quant + Fundamental Deviation*" "\n\n"
        r"📌 *Available Commands:*" "\n"
        r"• `/daily_bias` \- Institutional Hybrid Matrix" "\n"
        r"• `/eurusd` \| `/gbpusd` \| `/audusd` \- FX Majors" "\n"
        r"• `/gold` \| `/silver` \- Precious Metals" "\n"
        r"• `/btc` \- Crypto Systems" "\n"
        r"• `/nikkei` \| `/dow` \- Equity Indices" "\n"
        r"• `/help` \- Show this system specification manual" "\n\n"
        r"📈 _1% better everyday. 37X better._"
    )
    await update.message.reply_text(welcome, parse_mode="MarkdownV2")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def daily_bias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates the advanced, real-time combined macro matrix."""
    status_msg = await update.message.reply_text("⏳ Synchronizing quantitative grids and evaluating fundamental calendar deviations...")
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("macro_bias_summary").select("*").execute()
        
        if not response.data:
            await status_msg.edit_text("❌ Central cloud matrix database cache is unpopulated.")
            return
            
        macro_vectors = get_today_fundamental_vectors()
        
        def priority_rank(row):
            tech_bias = row.get("direction", "NEUTRAL")
            ticker = row.get("ticker")
            hybrid_label, _ = calculate_hybrid_confluence(ticker, tech_bias, macro_vectors)
            if "STRONG" in hybrid_label: return 0
            if "DIVERGENCE" in hybrid_label: return 1
            if "PAUSE" in hybrid_label: return 2
            return 3

        sorted_data = sorted(response.data, key=priority_rank)
        
        lines = []
        lines.append("🏛️ *INSTITUTIONAL HYBRID BIAS MATRIX*")
        lines.append(f"📅 Session Open: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━\n")
        
        for row in sorted_data:
            ticker = row["ticker"]
            tech_bias = row["direction"].replace("🟢 ", "").replace("🔴 ", "").replace("⚪ ", "")
            prob = row["probability"]
            conf = row["confidence"]
            
            hybrid_bias, summary_note = calculate_hybrid_confluence(ticker, tech_bias, macro_vectors)
            
            if "STRONG BULLISH" in hybrid_bias: emoji = "💎🟢"
            elif "STRONG BEARISH" in hybrid_bias: emoji = "💎🔴"
            elif "DIVERGENCE" in hybrid_bias: emoji = "⚡"
            elif "PAUSE" in hybrid_bias: emoji = "⚠️"
            elif "BULLISH" in hybrid_bias: emoji = "🟢"
            elif "BEARISH" in hybrid_bias: emoji = "🔴"
            else: emoji = "⚪"
            
            clean_note = summary_note.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
            
            lines.append(f"{emoji} *{ticker}* | `{hybrid_bias}`")
            lines.append(f"     Metrics: Prob `{prob}%` | Conf `{conf}%`")
            lines.append(f"     Context: _{clean_note}_\n")
            
        lines.append("━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━")
        lines.append("📊 _Confluence models align 20-period technical vectors with fundamental economic data deviations._")
        
        await status_msg.delete()
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Global hybrid matrix compilation failure: {e}")
        await update.message.reply_text(f"❌ Structural execution error: {e}")

async def asset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deep-dive lookups for specialized singular asset profiles."""
    command = update.message.text[1:].split('@')[0].lower()
    
    asset_map = {
        "eurusd": "EURUSD", "gbpusd": "GBPUSD", "audusd": "AUDUSD",
        "eurjpy": "EURJPY", "gbpjpy": "GBPJPY", "cadjpy": "CADJPY",
        "cadchf": "CADCHF", "gold": "XAUUSD", "silver": "XAGUSD",
        "btc": "BTCUSD", "nikkei": "JP225", "dow": "US30"
    }
    
    ticker = asset_map.get(command)
    if not ticker:
        await update.message.reply_text(f"❌ Invalid operational ticker routing code: /{command}")
        return
        
    try:
        supabase = get_supabase_client()
        response = supabase.table("macro_bias_summary").select("*").eq("ticker", ticker).maybe_single().execute()
        
        if not response.data:
            await update.message.reply_text(f"❌ Log tracking file for {ticker} is currently unavailable.")
            return
            
        data = response.data
        price = float(data['latest_close'])
        price_str = f"{price:.4f}" if ticker in FOREX_PAIRS else f"${price:,.2f}"
        
        macro_vectors = get_today_fundamental_vectors()
        hybrid_bias, summary_note = calculate_hybrid_confluence(ticker, data['direction'], macro_vectors)
        
        clean_note = summary_note.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
        
        lines = [
            f"🏛️ *HYBRID ASSET PROFILE: {ticker}*",
            "━ ━ ━ ━ ━ ━ ━ ━ ━ ━",
            f"💰 Market Price: `{price_str}`",
            f"🎯 Unified Bias: *{hybrid_bias}*",
            f"📊 Z-Score Band: `{data['z_score']}`",
            f"⚡ Daily Momentum: `{data['momentum_pct']}%`",
            f"🔒 Model Confidence: `{data['confidence']}%`",
            "━ ━ ━ ━ ━ ━ ━ ━ ━ ━",
            f"📝 Structural State: _{clean_note}_",
            f"🕐 Pipeline Sync: `{data['updated_at'][:16].replace('T', ' ')} UTC`"
        ]
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Single profiling error for {ticker}: {e}")
        await update.message.reply_text("❌ High-fidelity data rendering crash.")

def main():
    """Starts the persistent telegram polling engine application runtime server."""
    print("=" * 60)
    print("🧠 MACRO BIAS ENGINE - HYBRID ORCHESTRATION LAYER STARTED")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("daily_bias", daily_bias))
    
    for cmd in ["eurusd", "gbpusd", "audusd", "eurjpy", "gbpjpy", "cadjpy", "cadchf", "gold", "silver", "btc", "nikkei", "dow"]:
        app.add_handler(CommandHandler(cmd, asset_command))
        
    print("✅ Webhook-free server listening loop fully operational.")
    print("=" * 60)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
