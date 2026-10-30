"""
predictive.py — Predizione termica basata su EMA (Exponential Moving Average).

Stima la temperatura futura e calcola "minuti alla soglia" per permettere
all'orchestratore di rallentare prima di raggiungere il limite.

Usage (in thermal_manager.py):
    from MONITORING.predictive import ThermalPredictor
    predictor = ThermalPredictor()
    predictor.update(temp, load)
    pred = predictor.predict_minutes_to_threshold(80.0)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Prediction:
    """Risultato della predizione termica."""
    current_temp: float
    predicted_temp_1min: float
    predicted_temp_5min: float
    minutes_to_threshold: Optional[float]
    trend: str  # "rising" | "falling" | "stable"
    confidence: float  # 0.0 - 1.0


class ThermalPredictor:
    """Predittore termico basato su EMA e regressione lineare semplice.
    
    Usa solo stdlib, niente numpy. Adatto per modelli su CPU con poca RAM.
    """
    
    def __init__(self, alpha: float = 0.3, window_size: int = 10):
        self.alpha = alpha  # peso EMA (0.3 = reattivo, 0.1 = liscio)
        self.window_size = window_size
        self.samples = []  # [(timestamp, temp, load), ...]
        self.ema_temp = None
        self.ema_load = None
    
    def update(self, temp: float, load: float, timestamp: float = None):
        """Aggiunge un campione e aggiorna le EMA."""
        if timestamp is None:
            timestamp = time.time()
        
        self.samples.append((timestamp, temp, load))
        if len(self.samples) > self.window_size:
            self.samples = self.samples[-self.window_size:]
        
        # Aggiorna EMA
        if self.ema_temp is None:
            self.ema_temp = temp
            self.ema_load = load
        else:
            self.ema_temp = self.alpha * temp + (1 - self.alpha) * self.ema_temp
            self.ema_load = self.alpha * load + (1 - self.alpha) * self.ema_load
    
    def _linear_regression_slope(self) -> float:
        """Calcola la pendenza della retta di regressione sulla temperatura.
        Valore positivo = temperatura in aumento.
        """
        if len(self.samples) < 3:
            return 0.0
        
        n = len(self.samples)
        x_vals = list(range(n))
        y_vals = [s[1] for s in self.samples]  # temperature
        
        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def predict(self, threshold: float = 80.0) -> Prediction:
        """Predice la temperatura futura e i minuti alla soglia."""
        if not self.samples:
            return Prediction(0, 0, 0, None, "stable", 0.0)
        
        current_temp = self.samples[-1][1]
        current_load = self.samples[-1][2]
        
        # Slope (cambiamento per campione, ~30s)
        slope = self._linear_regression_slope()
        
        # Predizione 1 minuto (2 campioni a 30s)
        pred_1min = current_temp + slope * 2
        # Predizione 5 minuti (10 campioni)
        pred_5min = current_temp + slope * 10
        
        # Trend
        if slope > 0.5:
            trend = "rising"
        elif slope < -0.5:
            trend = "falling"
        else:
            trend = "stable"
        
        # Minuti alla soglia
        minutes_to_threshold = None
        if slope > 0 and current_temp < threshold:
            samples_to_threshold = (threshold - current_temp) / slope
            minutes_to_threshold = (samples_to_threshold * 30) / 60  # 30s per campione
            if minutes_to_threshold > 60:
                minutes_to_threshold = None  # troppo lontano
        
        # Confidence: più campioni abbiamo, più alta
        confidence = min(1.0, len(self.samples) / self.window_size)
        
        return Prediction(
            current_temp=current_temp,
            predicted_temp_1min=pred_1min,
            predicted_temp_5min=pred_5min,
            minutes_to_threshold=minutes_to_threshold,
            trend=trend,
            confidence=confidence,
        )
    
    def format_advice(self, threshold: float = 80.0) -> str:
        """Formatta il consiglio predittivo per il log/GUI."""
        pred = self.predict(threshold)
        
        if pred.minutes_to_threshold is not None and pred.minutes_to_threshold < 5:
            return (f"PREDICTION: {pred.minutes_to_threshold:.1f}min to {threshold}C "
                    f"(trend={pred.trend}, now={pred.current_temp:.0f}C, "
                    f"pred_1min={pred.predicted_temp_1min:.0f}C)")
        elif pred.trend == "rising":
            return (f"PREDICTION: rising ({pred.current_temp:.0f}C -> "
                    f"{pred.predicted_temp_5min:.0f}C in 5min)")
        else:
            return f"PREDICTION: {pred.trend} ({pred.current_temp:.0f}C)"
