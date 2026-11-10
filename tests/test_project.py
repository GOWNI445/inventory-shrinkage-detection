import pandas as pd
from src.detection import calculate_balances, detect_shrinkage, evaluate_alerts
from src.validation import validate_tables
from src.generator import generate_dataset
from src.reproducibility import compare

def test_stock_equation():
    opening=pd.DataFrame([{"store_id":"S1","sku_id":"K1","opening_qty":20}])
    moves=pd.DataFrame([
        {"store_id":"S1","sku_id":"K1","signed_quantity":10},
        {"store_id":"S1","sku_id":"K1","signed_quantity":-4},
    ])
    result=calculate_balances(opening,moves)
    assert result.iloc[0].expected_closing_qty==26

def test_detector_flags_count_variance():
    opening=pd.DataFrame([{"store_id":"S1","sku_id":"K1","opening_qty":20}])
    moves=pd.DataFrame(columns=["store_id","sku_id","signed_quantity","movement_type"])
    counts=pd.DataFrame([{"cycle_count_id":"C1","store_id":"S1","sku_id":"K1",
                          "physical_qty":10,"system_qty":20}])
    alerts=detect_shrinkage(opening,moves,counts,variance_threshold=3)
    assert len(alerts)==1
    assert "COUNT_VARIANCE" in alerts.iloc[0].alert_reasons

def test_evaluation_metrics():
    alerts=pd.DataFrame([{"store_id":"S1","sku_id":"K1"}])
    gt=pd.DataFrame([{"store_id":"S1","sku_id":"K1","ground_truth_label":"ANOMALY"}])
    m=evaluate_alerts(alerts,gt)
    assert m["precision"]==1 and m["recall"]==1

def test_generator_and_validation(tmp_path):
    generate_dataset(tmp_path,"starter",seed=123,scale={"stores":2,"skus":5,"movements":100,"counts":20})
    from src.validation import load_folder
    t=load_folder(tmp_path)
    report=validate_tables(t)
    assert report["passed"], report

def test_reproducibility():
    assert compare("starter",123)["reproducible"]

def test_investigation_event_is_persisted(tmp_path):
    from src.database import append_investigation_event
    db=tmp_path/'audit.db'
    a=append_investigation_event(db,'SHR-2026-000001','ROLE-000001','checked count','UNDER_REVIEW')
    b=append_investigation_event(db,'SHR-2026-000001','ROLE-000002','checked transfer','CLOSED')
    import sqlite3
    with sqlite3.connect(db) as con:
        assert con.execute('select count(*) from InvestigationEvent').fetchone()[0]==2
        assert con.execute('select count(*) from Investigation').fetchone()[0]==1
    assert a['investigation_id']==b['investigation_id']
    assert a['event_id']!=b['event_id']
