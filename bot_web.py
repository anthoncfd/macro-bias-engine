"""
MACRO BIAS ENGINE - Telegram Bot Web Gateway Server
Fully production-hardened build with case-insensitive search and automated webhook registration.
"""
import os
import sys
import logging
import requests
from flask import Flask, request, jsonify

# Configure logging format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Verify application context path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environmental variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if TELEGRAM_TOKEN:
    logger.info("✅ Token loaded successfully")
else:
    logger.error("❌ Critical Error: TELEGRAM_TOKEN environment variable is missing")

# Try importing the internal price ingestion system
try:
    from src.ingestion.market_prices import ASSETS, FOREX_PAIRS, fetch_all_prices
    logger.info("✅ Market price ingestion sub-modules successfully bound")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    raise e

# Initialize core web server
app = Flask(__name__)

def send_telegram_message(chat_id, text):
    """Dispatches a direct text response back to the user via Telegram API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, json=payload, timeout=8)
        logger.info(f"Telegram dispatch status: {res.status_code}")
    except Exception as e:
        logger.error(f"Failed to transmit Telegram message back: {e}")

def set_telegram_webhook():
    """
    Registers the public webhook URL with Telegram automatically on startup.
    """
    if not TELEGRAM_TOKEN:
        logger.error("❌ Cannot set webhook – token missing")
        return

    webhook_url = "https://macro-bias-engine01.onrender.com/webhook"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    
    try:
        resp = requests.post(url, json={"url": webhook_url}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                logger.info(f"✅ Webhook set successfully to {webhook_url}")
            else:
                logger.error(f"❌ Telegram API error: {data.get('description')}")
        else:
            logger.error(f"❌ Webhook HTTP error: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"❌ Webhook request error: {e}")

@app.route('/')
def home():
    """Basic health check probe for Render platform monitoring."""
    return "Macro Bias Engine Telegram Web Gateway Status: ONLINE", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handles incoming payload updates from Telegram and replies instantly."""
    if request.method == "POST":
        update_data = request.get_json()
        if not update_data:
            return "Empty Payload", 400
            
        logger.info(f"Incoming Telegram payload: {update_data.get('update_id')}")
        
        # Pull message details out of the payload structure safely
        message = update_data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_text = message.get("text", "").strip().lower()
        
        if not chat_id:
            return jsonify({"status": "ignored"}), 200

        # Processing Command Logic Router
        if user_text == "/start":
            reply = (
                "<b>Welcome to the Macro Bias Engine Bot!</b>\n\n"
                "Available commands:\n"
                "👉 <code>/prices</code> - Fetch live settled market closings\n"
                "👉 Type an asset name (e.g., <code>xauusd</code>) for specific matrix info"
            )
            send_telegram_message(chat_id, reply)
            
        elif user_text in ["/prices", "prices"]:
            send_telegram_message(chat_id, "⏳ Querying price execution nodes, please wait...")
            try:
                prices = fetch_all_prices()
                lines = ["<b>📊 Macro Engine Market Closes</b>\n"]
                for asset, details in prices.items():
                    val = details.get("price") if details else "Fetch Error"
                    lines.append(f"• <b>{asset.upper()}:</b> {val}")
                reply = "\n".join(lines)
            except Exception as e:
                reply = f"❌ Error retrieving macro data stream: {e}"
            send_telegram_message(chat_id, reply)
            
        elif user_text in [k.lower() for k in ASSETS.keys()]:
            # Match specific asset lookup requests case-insensitively
            send_telegram_message(chat_id, f"⏳ Fetching standard metric node for {user_text.upper()}...")
            try:
                prices = fetch_all_prices()
                # Normalize response keys to lowercase for foolproof validation matching
                normalized_prices = {k.lower(): v for k, v in prices.items()}
                asset_data = normalized_prices.get(user_text)
                
                if asset_data and asset_data.get("price"):
                    reply = f"🎯 <b>{user_text.upper()} Close:</b> {asset_data['price']}"
                else:
                    reply = f"⚠️ Could not resolve live pricing data context for {user_text.upper()}."
            except Exception as e:
                reply = f"❌ Error during search: {e}"
            send_telegram_message(chat_id, reply)
            
        else:
            # Fallback for unrecognized entry inputs
            reply = f"🤔 Command '{message.get('text')}' unmapped. Try using <code>/prices</code>."
            send_telegram_message(chat_id, reply)

        return jsonify({"status": "success", "processed": True}), 200
        
    return "Invalid Request Context", 400

if __name__ == "__main__":
    bind_port = int(os.getenv("PORT", 5000))
    
    # Register the webhook with Telegram before starting the server
    set_telegram_webhook()
    
    logger.info(f"Starting production web matrix on port {bind_port}...")
    app.run(host="0.0.0.0", port=bind_port)
