from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
from src.generator import generate_dataset
from src.detection import detect_shrinkage, evaluate_alerts
from src.validation import validate_tables, load_folder
from src.database import load_csv_folder_to_sqlite, append_investigation_event

st.set_page_config(page_title="Inventory Shrinkage Detection", page_icon="📦", layout="wide")
st.title("📦 Inventory Shrinkage Detection & Traceability")
st.caption("Evidence-based inventory reconciliation, alerts and investigations")

DATA_DIR=Path("data/generated")
if not (DATA_DIR/"inventory_movements.csv").exists():
    with st.spinner("Generating reproducible starter dataset..."):
        generate_dataset(DATA_DIR,"starter")

@st.cache_data(show_spinner=False)
def read_data(path):
    return load_folder(path)

with st.sidebar:
    st.header("Control Desk")
    st.write("**Dataset:**", str(DATA_DIR))
    if st.button("Regenerate starter dataset", width="stretch"):
        generate_dataset(DATA_DIR,"starter")
        st.cache_data.clear()
        st.rerun()
    threshold=st.slider("Count variance threshold (units)",1,15,3)
    repeat_threshold=st.slider("Repeated adjustment threshold",2,8,3)
    st.divider()
    st.caption("Synthetic dataset · Seed 20261022")

t=read_data(str(DATA_DIR))
alerts=detect_shrinkage(t["opening_balances"],t["inventory_movements"],
                        t["cycle_counts"],threshold,repeat_threshold)
gt=pd.read_csv(DATA_DIR/"ground_truth.csv")
metrics=evaluate_alerts(alerts,gt)
balances=t["opening_balances"].merge(
    t["inventory_movements"].groupby(["store_id","sku_id"],as_index=False).signed_quantity.sum(),
    on=["store_id","sku_id"],how="left")
balances["signed_quantity"]=balances.signed_quantity.fillna(0)
balances["closing_qty"]=(balances.opening_qty+balances.signed_quantity).clip(lower=0)

tabs=st.tabs(["Executive Dashboard","Alerts & Evidence","Inventory Explorer",
              "Data Quality","Investigation Desk","Data & Exports"])

with tabs[0]:
    st.subheader("Executive overview")
    a,b,c,d=st.columns(4)
    a.metric("Stores",f"{t['stores'].store_id.nunique():,}")
    b.metric("SKUs",f"{t['skus'].sku_id.nunique():,}")
    c.metric("Movements",f"{len(t['inventory_movements']):,}")
    d.metric("Shrinkage alerts",f"{len(alerts):,}")
    e,f,g=st.columns(3)
    e.metric("Estimated loss units",f"{alerts.estimated_loss_units.sum():,.0f}" if len(alerts) else "0")
    f.metric("Precision",f"{metrics['precision']:.1%}")
    g.metric("Recall",f"{metrics['recall']:.1%}")
    if len(alerts):
        left,right=st.columns(2)
        with left:
            st.plotly_chart(px.histogram(alerts,x="severity",color="severity",
                             title="Alerts by severity"),width="stretch")
        with right:
            by_store=alerts.groupby("store_id",as_index=False).size().sort_values("size",ascending=False).head(10)
            st.plotly_chart(px.bar(by_store,x="store_id",y="size",title="Top stores by alert count"),
                            width="stretch")
    st.info("A variance is an investigation signal, not proof of theft. Check evidence and benign explanations.")

with tabs[1]:
    st.subheader("Shrinkage alerts and explainable evidence")
    if alerts.empty: st.success("No alerts under the selected thresholds.")
    else:
        sev=st.multiselect("Severity",["HIGH","MEDIUM","LOW"],default=["HIGH","MEDIUM","LOW"])
        view=alerts[alerts.severity.isin(sev)]
        st.dataframe(view, width="stretch", hide_index=True)
        selected=st.selectbox("Select alert",view.alert_id.tolist())
        detail=view[view.alert_id.eq(selected)].iloc[0]
        st.markdown(f"**Why flagged:** {detail.alert_reasons}")
        st.write(f"Store `{detail.store_id}` · SKU `{detail.sku_id}` · Variance `{detail.variance_qty}` units")
        st.write(f"Negative adjustments in period: **{detail.negative_adjustment_count}**")
        st.download_button("Download alerts CSV",alerts.to_csv(index=False),
                           "shrinkage_alerts.csv","text/csv")

with tabs[2]:
    st.subheader("Inventory explorer")
    store=st.selectbox("Store",t["stores"].store_id.tolist())
    rows=balances[balances.store_id.eq(store)].merge(t["skus"][["sku_id","sku_name","category"]],
                                                      on="sku_id",how="left")
    st.dataframe(rows[["sku_id","sku_name","category","opening_qty","signed_quantity","closing_qty"]],
                 width="stretch",hide_index=True)
    st.metric("Store closing units",f"{rows.closing_qty.sum():,.0f}")

with tabs[3]:
    st.subheader("Data validation")
    report=validate_tables(t)
    st.metric("Validation checks passed",f"{report['passed_count']} / {report['total_checks']}")
    st.dataframe(pd.DataFrame(report["checks"]),width="stretch",hide_index=True)
    st.caption("Deliberately malformed edge cases are isolated in edge_cases.csv and tested separately.")

with tabs[4]:
    st.subheader("Investigation desk")
    st.write("Prototype workflow: select an alert, assign an owner, record findings and close with a disposition.")
    if "investigations" not in st.session_state:
        st.session_state.investigations=[]
    if not alerts.empty:
        alert_id=st.selectbox("Alert to investigate",alerts.alert_id.tolist(),key="invest_alert")
        owner=st.text_input("Assigned investigator role / employee ID",value="ROLE-000001")
        finding=st.text_area("Investigation notes","Review cycle count, transfer evidence and adjustment approvals.")
        disposition=st.selectbox("Disposition",["UNDER_REVIEW","CONFIRMED_SHRINKAGE","BENIGN_EXPLANATION","DATA_CORRECTION"])
        if st.button("Save investigation event"):
            saved=append_investigation_event("data/inventory.db",alert_id,owner,finding,disposition)
            st.session_state.investigations.append({
                "investigation_id":saved["investigation_id"], "event_id":saved["event_id"],
                "alert_id":alert_id,"assigned_to":owner,"finding":finding,
                "disposition":disposition,"event_timestamp":saved["event_timestamp"]
            })
            st.success(f"Investigation event {saved['event_id']} persisted in data/inventory.db.")
    if st.session_state.investigations:
        inv=pd.DataFrame(st.session_state.investigations)
        st.dataframe(inv,width="stretch",hide_index=True)
        st.download_button("Export investigation history",inv.to_csv(index=False),
                           "investigations.csv","text/csv")
    else:
        st.caption("No investigation events recorded in this session yet.")

with tabs[5]:
    st.subheader("Data generation and export")
    st.write("Starter data is generated automatically. Full challenge volume can be generated from the terminal.")
    st.code("python -m src.generator --profile full --output data/full")
    st.code("python -m src.validation --input data/generated")
    st.code("python -m src.reproducibility --profile starter")
    if st.button("Load generated CSVs into SQLite"):
        db=load_csv_folder_to_sqlite(DATA_DIR)
        st.success(f"Loaded dataset into {db}")
    for name in ["stores","skus","employee_roles","shifts","opening_balances",
                 "inventory_movements","cycle_counts","returns","ground_truth","edge_cases"]:
        path=DATA_DIR/f"{name}.csv"
        if path.exists():
            st.download_button(f"Download {name}.csv",path.read_bytes(),f"{name}.csv","text/csv",key=name)
