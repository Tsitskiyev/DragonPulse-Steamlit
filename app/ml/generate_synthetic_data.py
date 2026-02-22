from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path


def main(out_path: str = "data/port_delay_training.csv", n: int = 300, seed: int = 42):
    rng = np.random.default_rng(seed)

    # Базовые факторы риска 0..1
    queue = np.clip(rng.beta(2.2, 2.0, n), 0, 1)
    weather = np.clip(rng.beta(1.8, 4.5, n), 0, 1)
    news = np.clip(rng.beta(2.0, 3.2, n), 0, 1)
    ops = np.clip(rng.beta(2.1, 3.4, n), 0, 1)

    # backlog коррелирует с queue
    backlog = np.clip(0.62 * queue + 0.38 * rng.random(n), 0, 1)

    # Нелинейная целевая переменная (delay_hours)
    # Добавляем взаимодействия + шум
    delay = (
        3.5
        + 18.0 * queue
        + 9.0 * weather
        + 11.0 * news
        + 13.0 * backlog
        + 7.0 * ops
        + 7.5 * (queue * backlog)
        + 3.0 * (weather * news)
        + rng.normal(0, 1.6, n)
    )

    # Порог/клип
    delay = np.clip(delay, 1.0, None)

    df = pd.DataFrame(
        {
            "queue_index": np.round(queue, 3),
            "weather_risk": np.round(weather, 3),
            "news_risk": np.round(news, 3),
            "backlog_index": np.round(backlog, 3),
            "ops_risk": np.round(ops, 3),
            "delay_hours": np.round(delay, 2),
        }
    )

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"[OK] Saved: {out_path}")
    print(f"[OK] Shape: {df.shape}")
    print(df.head(8).to_string(index=False))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/port_delay_training.csv")
    parser.add_argument("--rows", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    main(out_path=args.out, n=args.rows, seed=args.seed)
