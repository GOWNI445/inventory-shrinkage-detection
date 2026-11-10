"""Explainable inventory reconciliation and shrinkage detection."""
from __future__ import annotations
import pandas as pd
import numpy as np

def calculate_balances(opening: pd.DataFrame, movements: pd.DataFrame) -> pd.DataFrame:
    keys = ["store_id", "sku_id"]
    m = movements.groupby(keys, as_index=False).signed_quantity.sum().rename(
        columns={"signed_quantity":"net_movement_qty"})
    result = opening.merge(m, on=keys, how="left")
    result["net_movement_qty"] = result.net_movement_qty.fillna(0)
    result["expected_closing_qty"] = result.opening_qty + result.net_movement_qty
    result["expected_closing_qty"] = result.expected_closing_qty.clip(lower=0)
    return result

def detect_shrinkage(opening: pd.DataFrame, movements: pd.DataFrame,
                     counts: pd.DataFrame, variance_threshold: int = 3,
                     repeated_adjustment_threshold: int = 3) -> pd.DataFrame:
    """Ground truth is intentionally not accepted by this function."""
    balances = calculate_balances(opening, movements)
    adj = movements[movements.movement_type.eq("ADJUSTMENT")].copy()
    adj["negative_adjustment"] = adj.signed_quantity.lt(0).astype(int)
    repeated = (adj.groupby(["store_id","sku_id"], as_index=False)
                .negative_adjustment.sum().rename(columns={"negative_adjustment":"negative_adjustment_count"}))
    evidence = counts.merge(balances[["store_id","sku_id","expected_closing_qty"]],
                            on=["store_id","sku_id"], how="left", suffixes=("_count",""))
    evidence["variance_qty"] = evidence.physical_qty - evidence.expected_closing_qty
    evidence = evidence.merge(repeated, on=["store_id","sku_id"], how="left")
    evidence["negative_adjustment_count"] = evidence.negative_adjustment_count.fillna(0).astype(int)
    evidence["count_loss_flag"] = evidence.variance_qty <= -abs(variance_threshold)
    evidence["repeated_adjustment_flag"] = evidence.negative_adjustment_count >= repeated_adjustment_threshold
    # Also retain repeated-adjustment cases that do not happen to have a cycle count row.
    counted_keys = set(zip(evidence.store_id, evidence.sku_id))
    extra = repeated[repeated.negative_adjustment_count >= repeated_adjustment_threshold].copy()
    extra = extra[[ (s,k) not in counted_keys for s,k in zip(extra.store_id, extra.sku_id) ]]
    if not extra.empty:
        extra["cycle_count_id"] = ""
        extra["physical_qty"] = np.nan
        extra["expected_closing_qty"] = np.nan
        extra["variance_qty"] = 0
        extra["count_loss_flag"] = False
        extra["repeated_adjustment_flag"] = True
        evidence = pd.concat([evidence, extra], ignore_index=True, sort=False)
    evidence["alert_reasons"] = evidence.apply(
        lambda r: "; ".join(x for x, ok in [
            ("COUNT_VARIANCE", bool(r.count_loss_flag)),
            ("REPEATED_NEGATIVE_ADJUSTMENTS", bool(r.repeated_adjustment_flag))
        ] if ok), axis=1)
    evidence = evidence[evidence.alert_reasons.ne("")].copy()
    evidence["estimated_loss_units"] = (-evidence.variance_qty).clip(lower=0)
    evidence["severity"] = np.select(
        [evidence.estimated_loss_units >= 10, evidence.estimated_loss_units >= 5],
        ["HIGH","MEDIUM"], default="LOW")
    evidence["alert_id"] = [f"SHR-2026-{i:06d}" for i in range(1,len(evidence)+1)]
    evidence["status"] = "OPEN"
    evidence["detected_at"] = pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S")
    cols = ["alert_id","cycle_count_id","store_id","sku_id","variance_qty",
            "estimated_loss_units","negative_adjustment_count","alert_reasons",
            "severity","status","detected_at"]
    return evidence[cols].reset_index(drop=True)

def evaluate_alerts(alerts: pd.DataFrame, ground_truth: pd.DataFrame) -> dict:
    """Evaluate at store/SKU grain; benign labels count as negatives."""
    gt = ground_truth[ground_truth.ground_truth_label.isin(["ANOMALY","BENIGN"])].copy()
    if gt.empty:
        return {"tp":0,"fp":0,"fn":0,"tn":0,"precision":0.0,"recall":0.0,"f1":0.0}
    truth_keys = set(zip(gt.store_id, gt.sku_id))
    positive_keys = set(zip(gt[gt.ground_truth_label.eq("ANOMALY")].store_id,
                            gt[gt.ground_truth_label.eq("ANOMALY")].sku_id))
    negative_keys = set(zip(gt[gt.ground_truth_label.eq("BENIGN")].store_id,
                            gt[gt.ground_truth_label.eq("BENIGN")].sku_id))
    predicted_keys = set(zip(alerts.store_id, alerts.sku_id)) if not alerts.empty else set()
    tp = len(predicted_keys & positive_keys)
    fp = len(predicted_keys & negative_keys) + len(predicted_keys - truth_keys)
    fn = len(positive_keys - predicted_keys)
    tn = max(0, len(negative_keys - predicted_keys))
    precision = tp/(tp+fp) if tp+fp else 0.0
    recall = tp/(tp+fn) if tp+fn else 0.0
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
    return {"tp":tp,"fp":fp,"fn":fn,"tn":tn,
            "precision":round(precision,4),"recall":round(recall,4),"f1":round(f1,4)}
