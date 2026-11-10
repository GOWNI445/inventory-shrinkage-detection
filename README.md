# Inventory Shrinkage Detection & Traceability System

A reproducible, end-to-end Python project that detects unusual inventory loss by reconciling receipts, sales, transfers, adjustments, returns and cycle counts. It exposes evidence-based alerts, investigation workflows, validation results and measurable evaluation metrics.

## Features

- Streamlit operations dashboard
- Deterministic synthetic data generator (fixed seed `20261022`)
- Master and transaction entities with deterministic IDs
- Inventory reconciliation and cycle-count variance analysis
- Explainable rule-based shrinkage detection
- Separate `ground_truth.csv` (never used as a detection input)
- Alert investigation lifecycle with append-only audit events
- Data-quality validation and deliberate negative scenarios
- CSV and JSON exports; SQLite schema and loader
- Reproducibility checks using row counts and SHA-256 checksums
- Unit tests

## Architecture

`app.py` is the Streamlit UI. Business logic lives in `src/`:
- `generator.py`: creates parent/master data before dependent events
- `detection.py`: calculates balances, evidence and alerts
- `validation.py`: primary/foreign key, enum, date and arithmetic checks
- `database.py`: SQLite persistence
- `reproducibility.py`: deterministic output comparison

## Quick start (Windows)

```powershell
cd inventory_shrinkage_detection
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the Local URL shown in the terminal (normally `http://localhost:8501`).

## Generate starter data

```powershell
python -m src.generator --profile starter --output data/generated
```

Starter profile: 10 stores, 200 SKUs, 20,000 movements, 500 cycle counts.

## Generate the challenge-scale dataset

```powershell
python -m src.generator --profile full --output data/full
```

Full profile: 100 stores, 5,000 SKUs, 1,000,000 movements, 20,000 cycle counts.
The full profile can require substantial RAM and disk space. Start with `starter`.

## Validate and compare reproducibility

```powershell
python -m src.validation --input data/generated
python -m src.reproducibility --profile starter
pytest -q
```

## Outputs

The generator exports:
- `stores.csv`, `skus.csv`, `employee_roles.csv`, `shifts.csv`
- `opening_balances.csv`, `promotions.csv`, `inventory_movements.csv`
- `cycle_counts.csv`, `returns.csv`
- `ground_truth.csv` (evaluation only; excluded from detection features)
- `edge_cases.csv` (deliberately malformed negative-test records)
- `manifest.json`, `generation_summary.json`

The Streamlit app can load the generated directory and create `shrinkage_alerts.csv`, `investigations.csv`, and audit-event records.

## Core stock equation

For each store and SKU:

`Expected closing stock = opening + receipts + transfer_in + customer_returns + positive_adjustments - sales - transfer_out - damage - negative_adjustments`

`Count variance = physical_count - expected_closing_stock`

A negative variance is a possible loss, not automatic proof of theft. Alerts include evidence and benign explanations (e.g. damage, returns processing and transfer timing).

## Detection rules

1. **COUNT_VARIANCE**: negative count variance exceeds the configured absolute/percentage threshold.
2. **REPEATED_ADJUSTMENTS**: multiple negative adjustments for the same store/SKU in the analysis period.
3. **UNEXPLAINED_LOSS**: negative count variance remains after known damage/returns/transfer events are reconciled.
4. **TRANSFER_TIMING**: paired transfer legs are checked so the same transfer is not treated as shrinkage at both source and destination.

Severity is based on evidence and estimated value. Ground-truth labels are generated from the planted scenario metadata and are not used to calculate alert scores.

## Data model and cardinality

- Store 1:N OpeningBalance, InventoryMovement, CycleCount, Shift, Investigation
- SKU 1:N OpeningBalance, InventoryMovement, CycleCount, Return
- EmployeeRole 1:N Shift; EmployeeRole 1:N InventoryMovement (actor role reference)
- Shift 1:N InventoryMovement
- Promotion 1:N InventoryMovement (optional promotion reference)
- InventoryMovement 1:N Return (optional source movement reference)
- Store/SKU 1:N ShrinkageAlert
- ShrinkageAlert 0:1 active Investigation; an alert may have multiple historical audit events
- Transfers use a shared `transfer_group_id` to link OUT and IN movement legs

Every entity has a primary key. Foreign keys are validated. IDs are immutable and zero-padded.

## Deliberate negative scenarios

`edge_cases.csv` holds isolated invalid examples so normal production-like tables remain internally consistent:
- movement references the wrong store
- adjustment has no reason
- count timestamp precedes a related stock movement
- transfer is incorrectly duplicated as shrinkage at both ends

Each negative case has an `issue_type` and expected validation outcome. It is not silently mixed into valid baseline data.

## Reproducibility

All random generation uses NumPy `default_rng(seed)`, default seed `20261022`. The generator is parameterized by profile and writes a manifest containing seed, parameters, output row counts and checksums. Running twice with the same seed and profile should yield identical CSV checksums.

## Evaluation metrics

The dashboard reports precision, recall, F1 and confusion-matrix counts by comparing detected alert entity keys with the separate ground-truth labels. This evaluation is meaningful only for the synthetic scenarios represented in `ground_truth.csv`.

## Lawful provenance

All records are synthetic. No personal, confidential or external business data is collected. Synthetic employee IDs and roles are used only to model authorization and shift relationships.
