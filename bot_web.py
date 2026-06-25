"""
MACRO BIAS ENGINE - Telegram Bot Web Gateway Server
Updated to safely import and utilize the updated V3.6 automated price ingestion module.
"""
import os
import sys
import logging
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
    logger.info("✅ Token loaded")
else:
    logger.error("❌ Critical Error: TELEGRAM_TOKEN environment variable is missing")

# =====================================================================
# 🔄 CORRECTED STRUCTURAL IMPORT ZONE (FIXES THE RENDER CRASH)
# =====================================================================
try:
    from src.ingestion.market_prices import ASSETS, FOREX_PAIRS, fetch_all_prices
    logger.info("✅ Market price ingestion sub-modules successfully bound")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    raise e

# Initialize core micro-web server
app = Flask(__name__)

@app.route('/')
def home():
    """Basic health check probe for the Render platform deployment monitoring."""
    return "Macro Bias Engine Telegram Web Gateway Status: ONLINE", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handles incoming payload updates from the Telegram webhook router."""
    if request.method == "POST":
        update_data = request.get_json()
        if update_data:
            # Process incoming messaging interactions here
            logger.info(f"Incoming Telegram payload: {update_data.get('update_id')}")
            return jsonify({"status": "success", "processed": True}), 200
    return "Invalid Request Context", 400

@app.route('/api/prices', methods=['GET'])
def get_processed_prices():
    """
    Internal administrative routing utility. 
    Exposes the newly mapped Twelve Data and Yahoo closing matrices via an API JSON node.
    """
    try:
        current_closes = fetch_all_prices()
        return jsonify({"status": "active", "data": current_closes}), 200
    except Exception as e:
        logger.error(f"API Execution exception occurred during price poll: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # Render binds dynamic traffic routing to the PORT environment variable automatically
    bind_port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting production web matrix on port {bind_port}...")
    app.run(host="0.0.0.0", port=bind_port)
