"""
ALPHA ATTRIBUTION & SHADOW ENGINE
Manages empirical percentile transformations, solves multi-factor scaling,
and isolates statistical factor contributions without look-ahead bias.
"""
import numpy as np
import pandas as pd
from scipy.stats import percentileofscore, spearmanr
from sklearn.linear_model import LinearRegression

class AlphaAttributionEngine:
    def __init__(self, historical_window=504, forward_horizon=20):
        self.historical_window = historical_window
        self.forward_horizon = forward_horizon
        self.rolling_buffers = {}
        
    def update_buffer(self, key, value):
        if key not in self.rolling_buffers:
            self.rolling_buffers[key] = []
        self.rolling_buffers[key].append(value)
        if len(self.rolling_buffers[key]) > self.historical_window:
            self.rolling_buffers[key] = self.rolling_buffers[key][-self.historical_window:]

    def get_empirical_percentile(self, key, current_value):
        if key not in self.rolling_buffers or len(self.rolling_buffers[key]) < 30:
            return 0.5
        return percentileofscore(np.array(self.rolling_buffers[key]), current_value) / 100.0

    def decompose_prediction(self, ticker, tech_z, macro_score, regime_probs):
        """
        Transforms distinct data scales into unified percentile space
        and normalizes active component forces to sum to exactly 100%.
        """
        self.update_buffer(f"{ticker}_tech", tech_z)
        self.update_buffer(f"{ticker}_macro", macro_score)
        
        tech_pct = self.get_empirical_percentile(f"{ticker}_tech", tech_z)
        macro_pct = self.get_empirical_percentile(f"{ticker}_macro", macro_score)
        
        dominant_regime_idx = int(np.argmax(regime_probs))
        regime_pct = regime_probs[dominant_regime_idx]
        
        # Structural design weights
        w_tech, w_macro, w_regime = 0.5, 0.3, 0.2
        
        f_tech = tech_pct * w_tech
        f_macro = macro_pct * w_macro
        f_regime = regime_pct * w_regime
        total_force = f_tech + f_macro + f_regime
        
        shares = {
            "technical": round((f_tech / total_force) * 100, 1) if total_force > 0 else 33.3,
            "macro": round((f_macro / total_force) * 100, 1) if total_force > 0 else 33.3,
            "regime_context": round((f_regime / total_force) * 100, 1) if total_force > 0 else 33.4
        }
        
        raw_score = (w_tech * tech_pct) + (w_macro * macro_pct)
        combined_bias = (raw_score - 0.5) * 2.0
        
        return {
            "ticker": ticker,
            "raw_score": float(raw_score),
            "combined_bias": float(combined_bias),
            "component_shares": shares,
            "dominant_regime_id": dominant_regime_idx
        }

    def compute_metrics(self, closed_predictions):
        """
        Processes closed database records. Employs Spearman Rank (IC)
        and multi-variable OLS to isolate true alpha contribution.
        """
        if len(closed_predictions) < 30:
            return {"status": "Gathering Evidence", "sample_size": len(closed_predictions)}
            
        df = pd.DataFrame(closed_predictions)
        
        ic_tech, _ = spearmanr(df["tech_contrib"], df["actual_return"])
        ic_macro, _ = spearmanr(df["macro_contrib"], df["actual_return"])
        ic_regime, _ = spearmanr(df["regime_contrib"], df["actual_return"])
        ic_total, _ = spearmanr(df["combined_score"], df["actual_return"])
        
        X = df[["tech_contrib", "macro_contrib", "regime_contrib"]]
        y = df["actual_return"]
        reg = LinearRegression().fit(X, y)
        
        return {
            "status": "Active Validation",
            "sample_size": len(df),
            "information_coefficients": {
                "technical_ic": round(float(ic_tech), 4),
                "macro_ic": round(float(ic_macro), 4),
                "regime_ic": round(float(ic_regime), 4),
                "aggregated_engine_ic": round(float(ic_total), 4)
            },
            "variance_explained_r2": round(float(reg.score(X, y)), 4),
            "realized_betas": {
                "technical": round(float(reg.coef_[0]), 4),
                "macro": round(float(reg.coef_[1]), 4),
                "regime": round(float(reg.coef_[2]), 4)
            },
            "system_hit_rate": round(float((df["was_correct"] == True).mean()), 4)
}
