"""Deterministic synthetic inventory dataset generator."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 20261022
PROFILES = {
    "starter": dict(stores=10, skus=200, movements=20_000, counts=500),
    "full": dict(stores=100, skus=5_000, movements=1_000_000, counts=20_000),
}
MOVEMENT_TYPES = ["RECEIPT", "SALE", "TRANSFER_OUT", "TRANSFER_IN",
                  "ADJUSTMENT", "DAMAGE", "RETURN"]
REASONS = ["supplier_delivery", "customer_sale", "store_transfer",
           "cycle_count_correction", "damaged_goods", "customer_return",
           "promotion", "system_correction"]

def ids(prefix: str, n: int, year: bool = False) -> list[str]:
    if year:
        return [f"{prefix}-2026-{i:08d}" for i in range(1, n + 1)]
    return [f"{prefix}-{i:06d}" for i in range(1, n + 1)]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def generate_dataset(output: str | Path, profile: str = "starter",
                     seed: int = SEED, scale: dict | None = None) -> dict:
    p = dict(PROFILES[profile])
    if scale:
        p.update(scale)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    ns, nk, nm, nc = (p[k] for k in ("stores", "skus", "movements", "counts"))

    stores = pd.DataFrame({
        "store_id": ids("STORE", ns),
        "store_name": [f"Store {i:03d}" for i in range(1, ns+1)],
        "region": rng.choice(["South", "North", "West", "East"], ns),
        "store_type": rng.choice(["RETAIL", "WAREHOUSE"], ns, p=[.85, .15]),
        "active": True,
        "effective_from": "2026-01-01",
    })
    skus = pd.DataFrame({
        "sku_id": ids("SKU", nk),
        "sku_name": [f"Product {i:05d}" for i in range(1, nk+1)],
        "category": rng.choice(["Grocery", "Electronics", "Apparel", "Home"], nk),
        "unit_cost": np.round(rng.uniform(2, 250, nk), 2),
        "unit": "each",
        "active": True,
    })
    roles = pd.DataFrame({
        "employee_role_id": ids("ROLE", max(8, min(40, ns*3))),
        "employee_id": [f"EMP-{i:06d}" for i in range(1, max(8, min(40, ns*3))+1)],
        "role": rng.choice(["OPERATOR", "ANALYST", "MANAGER", "ADMIN"], max(8, min(40, ns*3))),
        "authorized_actions": ["RECEIVE|SELL|COUNT|ADJUST|TRANSFER"] * max(8, min(40, ns*3)),
        "effective_from": "2026-01-01",
        "effective_to": "",
    })
    nshift = max(ns * 3, 12)
    shifts = pd.DataFrame({
        "shift_id": ids("SHIFT", nshift),
        "store_id": np.resize(stores.store_id.to_numpy(), nshift),
        "employee_role_id": rng.choice(roles.employee_role_id, nshift),
        "shift_name": rng.choice(["MORNING", "EVENING", "NIGHT"], nshift),
        "start_time": "2026-10-01T08:00:00",
        "end_time": "2026-10-01T16:00:00",
    })
    nopen = ns * nk
    opening = pd.DataFrame({
        "opening_balance_id": ids("OPEN", nopen),
        "store_id": np.repeat(stores.store_id.to_numpy(), nk),
        "sku_id": np.tile(skus.sku_id.to_numpy(), ns),
        "opening_qty": rng.integers(20, 151, nopen),
        "as_of_date": "2026-10-01",
    })
    promotions = pd.DataFrame({
        "promotion_id": ids("PROMO", max(1, min(100, nk // 2))),
        "promotion_name": [f"Promotion {i:03d}" for i in range(1, max(1, min(100, nk // 2))+1)],
        "discount_pct": np.round(rng.uniform(5, 40, max(1, min(100, nk // 2))), 1),
        "start_date": "2026-10-01", "end_date": "2026-12-31",
        "active": True,
    })

    # Valid baseline movement events. Quantity is always positive; signed_quantity
    # expresses its effect on the store's on-hand balance.
    mstore = rng.choice(stores.store_id.to_numpy(), nm)
    msku = rng.choice(skus.sku_id.to_numpy(), nm)
    mtype = rng.choice(MOVEMENT_TYPES, nm, p=[.12, .52, .07, .07, .10, .06, .06])
    qty = rng.integers(1, 8, nm)
    sign = np.select(
        [np.isin(mtype, ["RECEIPT", "TRANSFER_IN", "RETURN"]),
         np.isin(mtype, ["SALE", "TRANSFER_OUT", "DAMAGE"])],
        [1, -1],
        default=np.where(rng.random(nm) < .5, 1, -1)
    )
    signed = qty * sign
    reason = np.select(
        [mtype == "RECEIPT", mtype == "SALE", mtype == "DAMAGE",
         mtype == "RETURN", mtype == "TRANSFER_IN", mtype == "TRANSFER_OUT"],
        ["supplier_delivery", "customer_sale", "damaged_goods",
         "customer_return", "store_transfer", "store_transfer"],
        default="cycle_count_correction"
    )
    dates = pd.Timestamp("2026-10-01") + pd.to_timedelta(rng.integers(0, 31, nm), unit="D")
    role_idx = rng.integers(0, len(roles), nm)
    shift_idx = rng.integers(0, len(shifts), nm)
    transfer_mask = np.isin(mtype, ["TRANSFER_IN", "TRANSFER_OUT"])
    transfer_groups = np.full(nm, "", dtype=object)
    promo_mask = (mtype == "SALE") & (rng.random(nm) < .12)
    promo_ids = np.where(promo_mask, rng.choice(promotions.promotion_id, nm), "")
    movements = pd.DataFrame({
        "movement_id": ids("MOV", nm, year=True),
        "store_id": mstore, "sku_id": msku, "movement_type": mtype,
        "quantity": qty, "signed_quantity": signed,
        "unit_cost": np.round(rng.uniform(2, 250, nm), 2),
        "reason_code": reason,
        "employee_role_id": roles.employee_role_id.to_numpy()[role_idx],
        "shift_id": shifts.shift_id.to_numpy()[shift_idx],
        "promotion_id": promo_ids,
        "transfer_group_id": transfer_groups,
        "event_timestamp": dates.astype(str) + "T12:00:00",
        "issue_type": "",
    })
    # Pair transfer legs: same SKU, same quantity, distinct source/destination stores.
    out_idx = movements.index[movements.movement_type.eq("TRANSFER_OUT")].to_numpy()
    in_idx = movements.index[movements.movement_type.eq("TRANSFER_IN")].to_numpy()
    pair_n = min(len(out_idx), len(in_idx))
    if pair_n:
        for pair_no, (oi, ii) in enumerate(zip(out_idx[:pair_n], in_idx[:pair_n]), start=1):
            source = movements.at[oi, "store_id"]
            dest_choices = stores.loc[stores.store_id.ne(source), "store_id"].to_numpy()
            dest = rng.choice(dest_choices) if len(dest_choices) else source
            sku = movements.at[oi, "sku_id"]
            amount = int(movements.at[oi, "quantity"])
            movements.at[ii, "store_id"] = dest
            movements.at[ii, "sku_id"] = sku
            movements.at[ii, "quantity"] = amount
            movements.at[oi, "signed_quantity"] = -amount
            movements.at[ii, "signed_quantity"] = amount
            group = f"TRF-{pair_no:08d}"
            movements.at[oi, "transfer_group_id"] = group
            movements.at[ii, "transfer_group_id"] = group

    # Align shift and employee-role references to the movement's actual store.
    first_shift = shifts.drop_duplicates("store_id").set_index("store_id")
    shift_map = first_shift.shift_id.to_dict()
    role_map = first_shift.employee_role_id.to_dict()
    movements["shift_id"] = movements.store_id.map(shift_map)
    movements["employee_role_id"] = movements.store_id.map(role_map)

    # Plant deterministic adjustment anomalies in clusters (3+ per store/SKU).
    nplant_groups = max(1, min(nm // 1000, 100))
    plant_rows = []
    available = movements.index[~movements.movement_type.isin(["TRANSFER_IN", "TRANSFER_OUT"])].to_numpy()
    for group_no in range(nplant_groups):
        chosen = rng.choice(available, min(3, len(available)), replace=False)
        available = np.setdiff1d(available, chosen, assume_unique=False)
        if len(chosen) < 3:
            break
        base_store = movements.at[chosen[0], "store_id"]
        base_sku = movements.at[chosen[0], "sku_id"]
        movements.loc[chosen, "store_id"] = base_store
        movements.loc[chosen, "sku_id"] = base_sku
        movements.loc[chosen, "movement_type"] = "ADJUSTMENT"
        movements.loc[chosen, "signed_quantity"] = -rng.integers(3, 12, len(chosen))
        movements.loc[chosen, "quantity"] = movements.loc[chosen, "signed_quantity"].abs()
        movements.loc[chosen, "reason_code"] = "cycle_count_correction"
        movements.loc[chosen, "issue_type"] = "REPEATED_NEGATIVE_ADJUSTMENT"
        plant_rows.extend(chosen.tolist())
    plant_idx = np.asarray(plant_rows, dtype=int)
    # Re-align authorization and shift after the planted rows are reassigned to a store.
    movements["shift_id"] = movements.store_id.map(shift_map)
    movements["employee_role_id"] = movements.store_id.map(role_map)

    # Generate cycle counts from calculated baseline system stock.
    key = ["store_id", "sku_id"]
    movement_totals = movements.groupby(key).signed_quantity.sum()
    opening_idx = opening.set_index(key).opening_qty
    expected = opening_idx.add(movement_totals, fill_value=0).clip(lower=0)
    count_pairs = rng.integers(0, nopen, nc)
    selected = opening.iloc[count_pairs][["store_id", "sku_id"]].reset_index(drop=True)
    expected_values = np.array([
        expected.get((s, k), 0) for s, k in zip(selected.store_id, selected.sku_id)
    ], dtype=int)
    count_variance = np.zeros(nc, dtype=int)
    planted_count_n = max(1, min(nc // 20, 500))
    count_plant_idx = rng.choice(np.arange(nc), planted_count_n, replace=False)
    count_variance[count_plant_idx] = -rng.integers(3, 16, planted_count_n)
    # Some benign discrepancies are explicitly represented as damage/counting errors.
    benign_n = max(1, min(nc // 30, 300))
    remaining = np.setdiff1d(np.arange(nc), count_plant_idx)
    benign_idx = rng.choice(remaining, min(benign_n, len(remaining)), replace=False)
    count_variance[benign_idx] = -rng.integers(1, 4, len(benign_idx))
    physical = np.maximum(0, expected_values + count_variance)
    # Counts occur after the movement window so the included system quantity is time-consistent.
    count_dates = pd.Timestamp("2026-11-01") + pd.to_timedelta(rng.integers(0, 6, nc), unit="D")
    counts = pd.DataFrame({
        "cycle_count_id": [f"CNT-2026-{i:06d}" for i in range(1, nc+1)],
        "store_id": selected.store_id, "sku_id": selected.sku_id,
        "system_qty": expected_values, "physical_qty": physical,
        "variance_qty": physical - expected_values,
        "counted_by_role_id": rng.choice(roles.employee_role_id, nc),
        "count_timestamp": count_dates.astype(str) + "T18:00:00",
        "status": "APPROVED",
    })

    # Returns table references a subset of return movement rows.
    ret_mov = movements[movements.movement_type == "RETURN"].head(max(1, nm // 100))
    returns = pd.DataFrame({
        "return_id": ids("RET", len(ret_mov)),
        "movement_id": ret_mov.movement_id.to_numpy(),
        "store_id": ret_mov.store_id.to_numpy(),
        "sku_id": ret_mov.sku_id.to_numpy(),
        "quantity": ret_mov.quantity.to_numpy(),
        "return_reason": rng.choice(["CUSTOMER_CHANGED_MIND", "DAMAGED_ON_ARRIVAL", "WRONG_ITEM"], len(ret_mov)),
        "return_timestamp": ret_mov.event_timestamp.to_numpy(),
        "disposition": rng.choice(["RESTOCK", "QUARANTINE", "WRITE_OFF"], len(ret_mov)),
    })

    # Separate evaluation labels; never included in detector input.
    gt_count = counts.loc[count_plant_idx]
    gt_adj = movements.loc[plant_idx]
    gt = pd.concat([
        pd.DataFrame({"case_id": gt_count.cycle_count_id, "entity_type": "CYCLE_COUNT",
                      "entity_id": gt_count.cycle_count_id, "store_id": gt_count.store_id,
                      "sku_id": gt_count.sku_id, "ground_truth_label": "ANOMALY",
                      "scenario": "PLANTED_UNEXPLAINED_COUNT_LOSS"}),
        pd.DataFrame({"case_id": gt_adj.movement_id, "entity_type": "MOVEMENT",
                      "entity_id": gt_adj.movement_id, "store_id": gt_adj.store_id,
                      "sku_id": gt_adj.sku_id, "ground_truth_label": "ANOMALY",
                      "scenario": "REPEATED_NEGATIVE_ADJUSTMENT"}),
    ], ignore_index=True)
    # Label benign count discrepancies separately, so not every variance is suspicious.
    gt_benign = counts.loc[benign_idx]
    gt = pd.concat([gt, pd.DataFrame({
        "case_id": gt_benign.cycle_count_id, "entity_type": "CYCLE_COUNT",
        "entity_id": gt_benign.cycle_count_id, "store_id": gt_benign.store_id,
        "sku_id": gt_benign.sku_id, "ground_truth_label": "BENIGN",
        "scenario": "SMALL_BENIGN_VARIANCE"
    })], ignore_index=True)

    # Isolated malformed examples used by negative tests; not mixed into baseline tables.
    edge_cases = pd.DataFrame([
        {"case_id":"EDGE-0001","issue_type":"WRONG_STORE_REFERENCE","entity":"InventoryMovement",
         "description":"Movement store_id does not match the source transfer store.","expected":"FAIL_FOREIGN_KEY_OR_TRANSFER_PAIR"},
        {"case_id":"EDGE-0002","issue_type":"ADJUSTMENT_MISSING_REASON","entity":"InventoryMovement",
         "description":"Adjustment has an empty reason_code.","expected":"FAIL_REQUIRED_FIELD"},
        {"case_id":"EDGE-0003","issue_type":"COUNT_BEFORE_MOVEMENT","entity":"CycleCount",
         "description":"Count timestamp is earlier than a movement included in its system quantity.","expected":"FAIL_DATE_ORDER"},
        {"case_id":"EDGE-0004","issue_type":"TRANSFER_DOUBLE_SHRINKAGE","entity":"ShrinkageAlert",
         "description":"One transfer group is incorrectly labelled as loss at both ends.","expected":"FAIL_DUPLICATE_TRANSFER_LOSS"},
    ])

    tables = {
        "stores": stores, "skus": skus, "employee_roles": roles, "shifts": shifts,
        "opening_balances": opening, "promotions": promotions,
        "inventory_movements": movements, "cycle_counts": counts,
        "returns": returns, "ground_truth": gt, "edge_cases": edge_cases,
    }
    manifest = {"project":"Inventory Shrinkage Detection", "seed":seed, "profile":profile,
                "parameters":p, "generated_at":"2026-11-10T00:00:00",
                "lawful_provenance":"Synthetic data generated locally; no external personal data."}
    summary = {}
    for name, df in tables.items():
        path = out / f"{name}.csv"
        df.to_csv(path, index=False)
        summary[name] = {"rows":len(df), "sha256":sha256(path)}
        # JSON is provided for interoperability; CSV remains the efficient large-data format.
        if name in {"stores","skus","employee_roles","cycle_counts","ground_truth"}:
            df.to_json(out / f"{name}.json", orient="records", indent=2)
    manifest["outputs"] = summary
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "generation_summary.json").write_text(json.dumps(
        {"seed":seed, "profile":profile, "row_counts":{k:v["rows"] for k,v in summary.items()}}, indent=2))
    return manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, default="starter")
    parser.add_argument("--output", default="data/generated")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    result = generate_dataset(args.output, args.profile, args.seed)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
