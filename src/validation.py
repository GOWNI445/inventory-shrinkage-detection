"""Data quality and referential-integrity checks."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

def validate_tables(t: dict[str,pd.DataFrame]) -> dict:
    checks = []
    def add(name, passed, detail):
        checks.append({"check":name,"passed":bool(passed),"detail":str(detail)})
    required = {
        "stores":["store_id"], "skus":["sku_id"], "employee_roles":["employee_role_id"],
        "shifts":["shift_id","store_id","employee_role_id"],
        "opening_balances":["opening_balance_id","store_id","sku_id","opening_qty"],
        "inventory_movements":["movement_id","store_id","sku_id","movement_type","quantity",
                               "signed_quantity","reason_code","employee_role_id","shift_id"],
        "cycle_counts":["cycle_count_id","store_id","sku_id","physical_qty","count_timestamp"],
        "returns":["return_id","movement_id","store_id","sku_id","quantity"],
    }
    pk = {"stores":"store_id","skus":"sku_id","employee_roles":"employee_role_id",
          "shifts":"shift_id","opening_balances":"opening_balance_id",
          "inventory_movements":"movement_id","cycle_counts":"cycle_count_id","returns":"return_id"}
    for table, cols in required.items():
        df=t.get(table,pd.DataFrame())
        add(f"{table}: required columns", set(cols).issubset(df.columns), cols)
        for col in cols:
            if col in df:
                add(f"{table}.{col}: no nulls", df[col].notna().all(), f"nulls={df[col].isna().sum()}")
    for table,col in pk.items():
        df=t.get(table,pd.DataFrame())
        if col in df:
            add(f"{table}: primary key unique", df[col].is_unique, f"duplicates={df[col].duplicated().sum()}")
    relations = [
        ("shifts","store_id","stores","store_id"),
        ("shifts","employee_role_id","employee_roles","employee_role_id"),
        ("opening_balances","store_id","stores","store_id"),
        ("opening_balances","sku_id","skus","sku_id"),
        ("inventory_movements","store_id","stores","store_id"),
        ("inventory_movements","sku_id","skus","sku_id"),
        ("inventory_movements","employee_role_id","employee_roles","employee_role_id"),
        ("inventory_movements","shift_id","shifts","shift_id"),
        ("cycle_counts","store_id","stores","store_id"),
        ("cycle_counts","sku_id","skus","sku_id"),
        ("returns","movement_id","inventory_movements","movement_id"),
    ]
    for child,cc,parent,pc in relations:
        if child in t and cc in t[child] and parent in t and pc in t[parent]:
            bad=~t[child][cc].isin(t[parent][pc])
            add(f"FK {child}.{cc} -> {parent}.{pc}", not bad.any(), f"invalid={bad.sum()}")
    if "inventory_movements" in t:
        m=t["inventory_movements"]
        allowed={"RECEIPT","SALE","TRANSFER_OUT","TRANSFER_IN","ADJUSTMENT","DAMAGE","RETURN"}
        add("movement types allowed", m.movement_type.isin(allowed).all(), "enum validation")
        adj=m[m.movement_type.eq("ADJUSTMENT")]
        add("adjustments have reason", adj.reason_code.fillna("").str.len().gt(0).all(),
            f"adjustment_rows={len(adj)}")
        add("movement quantity positive", m.quantity.gt(0).all(), "quantity is unsigned magnitude")
    if "cycle_counts" in t and {"physical_qty","system_qty","variance_qty"}.issubset(t["cycle_counts"].columns):
        c=t["cycle_counts"]
        add("cycle count arithmetic", (c.physical_qty-c.system_qty).eq(c.variance_qty).all(),
            "physical_qty - system_qty = variance_qty")
    return {"passed":all(x["passed"] for x in checks),"checks":checks,
            "passed_count":sum(x["passed"] for x in checks),"total_checks":len(checks)}

def load_folder(path: str|Path) -> dict:
    p=Path(path)
    names=["stores","skus","employee_roles","shifts","opening_balances",
           "inventory_movements","cycle_counts","returns"]
    return {n:pd.read_csv(p/f"{n}.csv") for n in names if (p/f"{n}.csv").exists()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="data/generated")
    args=ap.parse_args()
    result=validate_tables(load_folder(args.input))
    print(json.dumps(result,indent=2))
    if not result["passed"]:
        raise SystemExit(1)
if __name__=="__main__": main()
