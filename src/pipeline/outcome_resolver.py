"""
WALK-FORWARD OUTCOME RESOLVER
Executes out-of-sample resolution loops to match historical predictions 
with realized forward returns without look-ahead contamination.
"""
import sys
import os
from datetime import datetime, timedelta

# Enforce root directory path visibility for cross-module imports within automated environments
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database.supabase_client import get_supabase_client
from src.analytics.alpha_attribution import AlphaAttributionEngine


class OutcomeResolver:
    def __init__(self, db_client, attribution_engine):
        self.db = db_client
        self.attribution = attribution_engine
        
    def resolve_historical_predictions(self):
        """
        Queries all expired signals (Prediction Date <= Today - 20 Trading Days),
        calculates forward percentage returns, and updates verification records.
        """
        print("🔄 Resolving historical predictions...")
        
        try:
            # Map calendar horizon buffer (~20 trading days equates to 28 calendar days)
            cutoff_date = (datetime.utcnow() - timedelta(days=28)).isoformat()
            
            response = self.db.table("shadow_predictions") \
                .select("*") \
                .eq("is_resolved", False) \
                .lte("prediction_timestamp", cutoff_date) \
                .execute()
            
            signals = response.data
            print(f"   📊 Found {len(signals)} expired predictions to resolve")
            
            if len(signals) == 0:
                print("   ✅ No predictions need resolution.")
                return
            
            resolved_count = 0
            for signal in signals:
                ticker = signal['ticker']
                pred_date = signal['prediction_timestamp']
                
                # Retrieve the pricing anchor on execution day t
                start_price = self._get_price_on_date(ticker, pred_date)
                if start_price is None:
                    print(f"   ⚠️ Could not fetch start price for {ticker} on {pred_date}. Skipping record.")
                    continue
                
                # Project out to evaluation termination target mark t+20
                end_date = datetime.fromisoformat(pred_date) + timedelta(days=28)
                end_price = self._get_price_on_date(ticker, end_date.isoformat())
                if end_price is None:
                    print(f"   ⚠️ Could not fetch end price for {ticker} on {end_date.isoformat()}. Skipping record.")
                    continue
                
                # Calculate real mathematical return parameters
                forward_return = (end_price - start_price) / start_price
                combined_score = signal['combined_score']
                
                # Evaluate direction relative to the center-line probability boundary
                was_bullish = combined_score > 0.5
                was_correct = (forward_return > 0) if was_bullish else (forward_return < 0)
                
                # Update relational database snapshot state
                self.db.table("shadow_predictions") \
                    .update({
                        "is_resolved": True,
                        "actual_return": float(forward_return),
                        "was_correct": bool(was_correct)
                    }) \
                    .eq("id", signal['id']) \
                    .execute()
                
                print(f"   ✅ Resolved {ticker}: Score: {combined_score:.2f} | Return: {forward_return:+.2%} | Hit: {was_correct}")
                resolved_count += 1
            
            print(f"✅ Resolved {resolved_count} predictions successfully.")
            
        except Exception as e:
            print(f"❌ Outcome resolver execution failed: {e}")
    
    def _get_price_on_date(self, ticker, date_str):
        """
        Fetches the closest historical closing price for a ticker on or immediately 
        preceding a specific target timestamp using a bi-directional lookback window.
        Prevents data drops caused by weekend gaps and global exchange holidays.
        """
        try:
            date_obj = datetime.fromisoformat(date_str.split('T')[0]) if 'T' in date_str else datetime.fromisoformat(date_str)
            
            # Construct a 4-day trailing lookback envelope to bridge deep holiday closures
            date_start = (date_obj - timedelta(days=4)).strftime("%Y-%m-%d")
            date_end = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Request logs ordered chronologically backwards to match the nearest active pricing point
            response = self.db.table("market_structure_logs") \
                .select("latest_close") \
                .eq("ticker", ticker) \
                .gte("created_at", date_start) \
                .lte("created_at", date_end) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            if response.data:
                return float(response.data[0]['latest_close'])
            return None
        except Exception as e:
            print(f"   ⚠️ Price fetch execution failure for {ticker} on {date_str}: {e}")
            return None
    
    def fetch_active_attribution_report(self):
        """
        Queries all completely processed predictions to generate 
        the statistical alpha distribution breakdown matrix.
        """
        try:
            response = self.db.table("shadow_predictions") \
                .select("*") \
                .eq("is_resolved", True) \
                .execute()
            
            resolved_history = response.data
            
            if len(resolved_history) == 0:
                return {
                    "status": "Gathering Evidence",
                    "sample_size": 0,
                    "message": "Building shadow verification pools. Advanced tracking matrices activate at 30 entries."
                }
            
            return self.attribution.compute_metrics(resolved_history)
            
        except Exception as e:
            return {
                "status": "Error",
                "message": f"Failed to calculate active alpha attribution reports: {e}"
            }


def run_outcome_resolution():
    """
    Main entry point function executed by your automated runner environments.
    Initializes system architecture modules and launches database resolution tasks.
    """
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - RUNNING OUTCOME RESOLVER")
    print(f"📅 UTC Execution Timestamp: {datetime.utcnow().isoformat()}")
    print("=" * 55)
    
    try:
        db = get_supabase_client()
        attribution = AlphaAttributionEngine(historical_window=504, forward_horizon=20)
        resolver = OutcomeResolver(db_client=db, attribution_engine=attribution)
        resolver.resolve_historical_predictions()
    except Exception as e:
        print(f"❌ Critical pipeline exception caught: {e}")
        raise


if __name__ == "__main__":
    run_outcome_resolution()
