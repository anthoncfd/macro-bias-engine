"""
MACRO BIAS ENGINE - Combined Web Server + Telegram Bot
Deploy on Render as a Web Service (Free Tier).
Auto-fetches historical data on first command if empty.
Displays CURRENT LIVE PRICE + BIAS REPORT.
"""
import os
import sys
import logging
import threading
import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import random
import requests

from flask import Flask
from telegram.ext import Application, CommandHandler

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

from src.analytics.bias_engine import run_bias_engine
from src.ingestion.market_prices import FOREX_PAIRS, ASSETS
from src.database.supabase_client import get_supabase_client

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

# --- Helper: Auto-Backfill on First Command ---
def auto_backfill_if_empty():
    """Check if database is empty. If so, backfill 10 days of data."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("market_structure_logs").select("id").limit(1).execute()
        if result.data:
            return True
        
        print("⚠️ Database is empty. Auto-backfilling 10 days...")
        run_backfill(days_back=10)
        return True
        
    except Exception as e:
        print(f"❌ Auto-backfill failed: {e}")
        return False

def run_backfill(days_back=10):
    """Backfill historical data into Supabase."""
    print(f"📥 Backfilling {days_back} days...")
    supabase = get_supabase_client()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    total_inserted = 0
    
    for display_name, tickers in ASSETS.items():
        print(f"   Processing {display_name}...")
        df = None
        for ticker in tickers:
            try:
                df = yf.download(
                    ticker,
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                    interval="1d",
                    progress=False,
                    auto_adjust=True
                )
                if not df.empty:
                    break
            except:
                continue
        
        if df is None or df.empty:
            continue
        
        for date_idx, row in df.iterrows():
            try:
                price = row['Close']
                if isinstance(price, pd.Series):
                    price = price.iloc[0]
                price = float(price)
            except:
                continue
            
            if pd.isna(price):
                continue
            
            check = supabase.table("market_structure_logs") \
                .select("id") \
                .eq("ticker", display_name) \
                .eq("created_at", date_idx.strftime("%Y-%m-%d")) \
                .execute()
            
            if check.data:
                continue
            
            row_data = {
                "ticker": display_name,
                "latest_close": price,
                "trend": "NEUTRAL",
                "momentum_score": 0.0,
                "created_at": date_idx.strftime("%Y-%m-%d")
            }
            
            try:
                supabase.table("market_structure_logs").insert(row_data).execute()
                total_inserted += 1
            except:
                pass
            
            time.sleep(0.05)
        
        time.sleep(0.3)
    
    print(f"✅ Backfill complete! Inserted {total_inserted} rows.")
    return total_inserted

# --- NEW: Fetch Current Live Price ---
def fetch_live_price(tickers):
    """Fetches the current intraday price using Yahoo Finance 5m bars."""
    for ticker in tickers:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {
                "range": "1d",
                "interval": "5m"
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                chart_data = data.get("chart", {}).get("result", [None])[0]
                if chart_data:
                    indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])
                    valid_closes = [c for c in closes if c is not None]
                    if valid_closes:
                        return float(valid_closes[-1])
        except Exception as e:
            print(f"   ⚠️ Live price error for {ticker}: {e}")
            continue
    
    return None  # No live price

# --- Telegram Helpers ---
def format_price(ticker, price):
    return f"{price:.4f}" if ticker in FOREX_PAIRS else f"${price:,.2f}"

def format_bias_report(ticker, bias_data, live_price=None):
    direction = bias_data.get("direction", "NEUTRAL")
    prob = bias_data.get("probability", 0)
    conf = bias_data.get("confidence", 0)
    close_price = bias_data.get("latest_close", 0)
    z = bias_data.get("z_score", 0)
    mom = bias_data.get("momentum_pct", 0)
    emoji = "🟢" if direction == "BULLISH" else "🔴" if direction == "BEARISH" else "⚪"
    conf_bar = "█" * int(conf / 10) + "░" * (10 - int(conf / 10))
    
    # Build the report
    report = f"🏛️ *MACRO BIAS REPORT*\n─── {ticker} ───\n\n"
    
    # Live Price (if available)
    if live_price is not None:
        report += f"📊 *Live Price:* {format_price(ticker, live_price)}\n"
    else:
        report += f"📊 *Live Price:* 🔴 Unavailable (market closed?)\n"
    
    # Closing Price
    report += f"📊 *Close Price:* {format_price(ticker, close_price)}\n\n"
    
    # Bias
    report += (
        f"🎯 *Direction:* {emoji} {direction}\n"
        f"📈 *Bullish Prob:* {prob:.1f}%\n"
        f"📊 *Confidence:* {conf:.1f}% {conf_bar}\n"
        f"⚡ *Momentum:* {mom:+.2f}%\n"
        f"📐 *Z-Score:* {z:+.2f}\n"
        f"🕐 *Updated:* {bias_data.get('last_update', 'N/A')}"
    )
    return report

# --- Command Handlers ---
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
    
    await update.message.reply_text(f"⏳ Fetching data for {asset}...")
    
    # 1. Ensure data exists (auto-backfill)
    auto_backfill_if_empty()
    
    # 2. Fetch Bias Report (from Supabase)
    results = run_bias_engine()
    bias_data = results.get(asset)
    
    if not bias_data or bias_data.get("status") != "SUCCESS":
        msg = bias_data.get("message", "No data available") if bias_data else "No data"
        await update.message.reply_text(f"❌ {msg}")
        return
    
    # 3. Fetch Current Live Price (Yahoo intraday)
    tickers = ASSETS.get(asset, [])
    live_price = fetch_live_price(tickers)
    
    # 4. Format and send report
    report = format_bias_report(asset, bias_data, live_price)
    await update.message.reply_text(report, parse_mode="Markdown")

async def full_bias_matrix(update, context):
    await update.message.reply_text("⏳ Generating full matrix...")
    auto_backfill_if_empty()
    
    results = run_bias_engine()
    report = "🏛️ *MACRO BIAS MATRIX*\n\n"
    for ticker, data in results.items():
        if data.get("status") == "SUCCESS":
            emoji = "🟢" if data["direction"] == "BULLISH" else "🔴" if data["direction"] == "BEARISH" else "⚪"
            report += f"{emoji} {ticker} | Prob: {data['probability']:.0f}% | Conf: {data['confidence']:.0f}%\n"
        else:
            report += f"⚫ {ticker} | {data.get('message', 'No data')}\n"
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
    print("🤖 Telegram bot is running!")
    loop.run_until_complete(app.run_polling())

# --- Main ---
if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Flask web server running on port {port}")
    flask_app.run(host="0.0.0.0", port=port)
