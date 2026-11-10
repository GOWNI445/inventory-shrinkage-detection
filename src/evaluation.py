"""Evaluate inventory shrinkage detection results."""

import pandas as pd
from src.detection import detect_shrinkage, evaluate_alerts


def run_evaluation(data_dir="data/full"):
    """Run shrinkage detection and calculate evaluation metrics."""

    opening = pd.read_csv(f"{data_dir}/opening_balances.csv")
    movements = pd.read_csv(f"{data_dir}/inventory_movements.csv")
    counts = pd.read_csv(f"{data_dir}/cycle_counts.csv")
    ground_truth = pd.read_csv(f"{data_dir}/ground_truth.csv")

    alerts = detect_shrinkage(opening, movements, counts)

    metrics = evaluate_alerts(alerts, ground_truth)

    print("\nINVENTORY SHRINKAGE EVALUATION")
    print("-" * 40)
    print("Total alerts:", len(alerts))

    for metric, value in metrics.items():
        print(f"{metric.upper()}: {value}")

    alerts.to_csv(f"{data_dir}/shrinkage_alerts.csv", index=False)

    print("\nAlerts saved to:", f"{data_dir}/shrinkage_alerts.csv")

    return alerts, metrics


if __name__ == "__main__":
    run_evaluation()