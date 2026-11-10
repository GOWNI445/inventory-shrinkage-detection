PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Store (
  store_id TEXT PRIMARY KEY, store_name TEXT NOT NULL, region TEXT NOT NULL,
  store_type TEXT NOT NULL CHECK(store_type IN ('RETAIL','WAREHOUSE')),
  active INTEGER NOT NULL, effective_from TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS SKU (
  sku_id TEXT PRIMARY KEY, sku_name TEXT NOT NULL, category TEXT NOT NULL,
  unit_cost REAL NOT NULL CHECK(unit_cost >= 0), unit TEXT NOT NULL, active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS EmployeeRole (
  employee_role_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK(role IN ('OPERATOR','ANALYST','MANAGER','ADMIN')),
  authorized_actions TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT
);
CREATE TABLE IF NOT EXISTS Shift (
  shift_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  employee_role_id TEXT NOT NULL REFERENCES EmployeeRole(employee_role_id),
  shift_name TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS Promotion (
  promotion_id TEXT PRIMARY KEY, promotion_name TEXT NOT NULL,
  discount_pct REAL NOT NULL CHECK(discount_pct BETWEEN 0 AND 100),
  start_date TEXT NOT NULL, end_date TEXT NOT NULL, active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS OpeningBalance (
  opening_balance_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  sku_id TEXT NOT NULL REFERENCES SKU(sku_id), opening_qty INTEGER NOT NULL CHECK(opening_qty >= 0),
  as_of_date TEXT NOT NULL, UNIQUE(store_id,sku_id)
);
CREATE TABLE IF NOT EXISTS InventoryMovement (
  movement_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  sku_id TEXT NOT NULL REFERENCES SKU(sku_id),
  movement_type TEXT NOT NULL CHECK(movement_type IN
    ('RECEIPT','SALE','TRANSFER_OUT','TRANSFER_IN','ADJUSTMENT','DAMAGE','RETURN')),
  quantity INTEGER NOT NULL CHECK(quantity > 0), signed_quantity INTEGER NOT NULL,
  unit_cost REAL NOT NULL, reason_code TEXT NOT NULL,
  employee_role_id TEXT NOT NULL REFERENCES EmployeeRole(employee_role_id),
  shift_id TEXT NOT NULL REFERENCES Shift(shift_id),
  promotion_id TEXT REFERENCES Promotion(promotion_id),
  transfer_group_id TEXT, event_timestamp TEXT NOT NULL, issue_type TEXT
);
CREATE TABLE IF NOT EXISTS CycleCount (
  cycle_count_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  sku_id TEXT NOT NULL REFERENCES SKU(sku_id), system_qty INTEGER NOT NULL,
  physical_qty INTEGER NOT NULL, variance_qty INTEGER NOT NULL,
  counted_by_role_id TEXT NOT NULL REFERENCES EmployeeRole(employee_role_id),
  count_timestamp TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ReturnRecord (
  return_id TEXT PRIMARY KEY, movement_id TEXT NOT NULL REFERENCES InventoryMovement(movement_id),
  store_id TEXT NOT NULL REFERENCES Store(store_id), sku_id TEXT NOT NULL REFERENCES SKU(sku_id),
  quantity INTEGER NOT NULL, return_reason TEXT NOT NULL, return_timestamp TEXT NOT NULL,
  disposition TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ShrinkageAlert (
  alert_id TEXT PRIMARY KEY, cycle_count_id TEXT REFERENCES CycleCount(cycle_count_id),
  store_id TEXT NOT NULL REFERENCES Store(store_id), sku_id TEXT NOT NULL REFERENCES SKU(sku_id),
  variance_qty INTEGER NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL,
  alert_reasons TEXT NOT NULL, detected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS Investigation (
  investigation_id TEXT PRIMARY KEY, alert_id TEXT NOT NULL REFERENCES ShrinkageAlert(alert_id),
  assigned_to TEXT NOT NULL, lifecycle_state TEXT NOT NULL,
  created_at TEXT NOT NULL, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS InvestigationEvent (
  event_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL REFERENCES Investigation(investigation_id),
  event_type TEXT NOT NULL, event_payload TEXT NOT NULL, event_timestamp TEXT NOT NULL
);
