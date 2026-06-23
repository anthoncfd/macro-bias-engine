"""
MACRO BIAS ENGINE V3 - SHADOW ORCHESTRATOR
Sustains the live user-facing production pipeline while feeding
the historical background audit architecture.
"""
from datetime import datetime
from src.analytics.alpha_attribution import AlphaAttributionEngine
from src.analytics.bias_engine import calculate_bias_for_asset
from src.ingestion.macro_data_fetcher import fetch_macro_data

class MacroBiasEngineV3Shadow:
    def __init__(self, db_client=None):
        self.db = db_client
        self.attribution = AlphaAttributionEngine(historical_window=504, forward_horizon=20)
        
    def generate_trading_report(self, macro_data=None):
        """
        Generates public user-facing responses while generating back-end shadow telemetry.
        """
        if macro_data is None:
            macro_data = fetch_macro_data()
        
        assets = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "USDJPY", "AUDUSD"]
        payload = {"timestamp": datetime.utcnow().isoformat(), "assets": {}}
        
        # Get regime probabilities (simplified for now)
        regime_probs = self._get_regime_probs(macro_data)
        
        for asset in assets:
            # 1. Fetch market structure Z-score
            market_bias = calculate_bias_for_asset(asset)
            tech_z = market_bias.get("z_score", 0.0)
            
            # 2. Calculate macro score
            macro_score = (
                macro_data.get("dxy_z", 0.0) * -0.3 +
                macro_data.get("vix_z", 0.0) * -0.1 +
                macro_data.get("spread_z", 0.0) * 0.2
            )
            
            # 3. Decompose through shadow attribution layer
            shadow_metrics = self.attribution.decompose_prediction(
                asset, tech_z, macro_score, regime_probs
            )
            
            # 4. Persist shadow signal to database
            self._persist_shadow_signal(asset, shadow_metrics)
            
            # 5. Build production payload
            payload["assets"][asset] = {
                "bias": shadow_metrics["combined_bias"],
                "shares": shadow_metrics["component_shares"],
                "dominant_regime": shadow_metrics["dominant_regime_id"],
                "direction": "BULLISH" if shadow_metrics["combined_bias"] > 0.2 else "BEARISH" if shadow_metrics["combined_bias"] < -0.2 else "NEUTRAL"
            }
            
        return payload
    
    def _get_regime_probs(self, macro_data):
        """Simplified regime probabilities (placeholder for HMM)"""
        dxy = macro_data.get("dxy_z", 0.0)
        vix = macro_data.get("vix_z", 0.0)
        
        if dxy > 0.5 and vix > 0.3:
            return [0.70, 0.20, 0.10]  # Risk-Off
        elif dxy < -0.5 and vix < -0.3:
            return [0.10, 0.20, 0.70]  # Risk-On
        else:
            return [0.30, 0.40, 0.30]  # Neutral
    
    def _persist_shadow_signal(self, asset, metrics):
        """Saves predictions to database for walk-forward evaluation"""
        try:
            if self.db:
                record = {
                    "ticker": asset,
                    "prediction_timestamp": datetime.utcnow().isoformat(),
                    "combined_score": metrics["raw_score"],
                    "tech_contrib": metrics["component_shares"]["technical"],
                    "macro_contrib": metrics["component_shares"]["macro"],
                    "regime_contrib": metrics["component_shares"]["regime_context"],
                    "is_resolved": False,
                    "actual_return": None,
                    "was_correct": None
                }
                self.db.table("shadow_predictions").insert(record).execute()
        except Exception as e:
            print(f"⚠️ Shadow log failed for {asset}: {e}")
