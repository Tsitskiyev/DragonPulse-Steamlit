from __future__ import annotations
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from dataclasses import dataclass


@dataclass
class DelayForecastResult:
    port: str
    predicted_delay_hours: float
    model_name: str = "LinearRegressionBaseline"


class DelayPredictor:
    """
    MVP baseline:
    delay_hours ~ queue_index + weather_risk + news_risk + backlog_index
    """
    def __init__(self) -> None:
        self.model = LinearRegression()
        self.is_fitted = False

    def fit(self, df: pd.DataFrame) -> None:
        x = df[["queue_index", "weather_risk", "news_risk", "backlog_index"]].values
        y = df["delay_hours"].values
        self.model.fit(x, y)
        self.is_fitted = True

    def predict_one(self, port: str, queue_index: float, weather_risk: float, news_risk: float, backlog_index: float) -> DelayForecastResult:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")
        x = np.array([[queue_index, weather_risk, news_risk, backlog_index]])
        pred = float(self.model.predict(x)[0])
        pred = max(0.0, pred)
        return DelayForecastResult(port=port, predicted_delay_hours=round(pred, 2))


def load_sample_data(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)
