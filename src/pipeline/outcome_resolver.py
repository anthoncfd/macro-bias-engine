"""
WALK-FORWARD OUTCOME RESOLVER
Executes daily tracking routines to match t-20 day historical records
with contemporary closing data, computing precise tracking values.
"""
from datetime import datetime, timedelta

class OutcomeResolver:
    def __init__(self, db_client, attribution_engine):
        self.db = db_client
        self.attribution = attribution_engine
        
    def resolve_historical_predictions(self):
        """
        Queries all expired signals (Prediction Date <= Today - 20 Trading Days),
        calculates forward percentage metrics, and updates verification logs.
        """
        try:
            # Get unresolved predictions older than 20 trading days
            # In production, you'd query Supabase here
            # For now, we'll simulate the logic
            print("🔄 Resolving historical predictions...")
            
            # This would be:
            # expiration_threshold = datetime.utcnow() - timedelta(days=28)
            # open_signals = self.db.table("shadow_predictions")
            #     .eq("is_resolved", False)
            #     .lte("prediction_timestamp", expiration_threshold)
            #     .execute()
            
            # For demonstration, we'll use mock data
            open_signals = self._fetch_unresolved_signals()
            
            for signal in open_signals:
                # Fetch actual forward return over the horizon
                forward_return = self._fetch_forward_return(
                    signal['ticker'],
                    signal['prediction_timestamp']
                )
                
                if forward_return is None:
                    continue
                
                # Determine if prediction was correct
                bias_positive = signal["combined_score"] > 0.5
                is_correct = (forward_return > 0) if bias_positive else (forward_return < 0)
                
                # Update database
                # self.db.table("shadow_predictions").update({
                #     "is_resolved": True,
                #     "actual_return": forward_return,
                #     "was_correct": is_correct
                # }).eq("id", signal["id"]).execute()
                
                print(f"   ✅ Resolved {signal['ticker']}: {forward_return:+.2%}")
                
        except Exception as e:
            print(f"❌ Outcome resolver failed: {e}")
    
    def _fetch_unresolved_signals(self):
        """Simulates fetching unresolved signals from database"""
        # In production, this queries Supabase
        return []
    
    def _fetch_forward_return(self, ticker, pred_date):
        """Fetches the actual return over the forward horizon"""
        # In production, this queries price history
        return 0.0145  # Mock value
    
    def fetch_active_attribution_report(self):
        """
        Queries all resolved prediction cases from historical records
        and feeds them through the Attribution model for live user viewing.
        """
        try:
            # In production:
            # resolved_history = self.db.table("shadow_predictions")
            #     .eq("is_resolved", True)
            #     .execute()
            
            # For now, return empty with status
            resolved_history = []
            
            if len(resolved_history) == 0:
                return {
                    "status": "Gathering Evidence",
                    "sample_size": 0,
                    "message": "Building shadow data. Validation activates at 30 predictions."
                }
            
            return self.attribution.compute_metrics(resolved_history)
            
        except Exception as e:
            return {
                "status": "Error",
                "message": f"Failed to fetch attribution report: {e}"
              }
