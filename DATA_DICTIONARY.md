# Data Dictionary

All IDs are immutable strings. Quantities are in `each` units; costs are in the dataset's currency-neutral units. Timestamps use ISO-8601 local synthetic time.

| Entity | Field | Type | Required | Validation / allowed values |
|---|---|---:|---|---|
| Store | store_id | string | Yes | PK, `STORE-000001` |
| Store | store_name | string | Yes | Non-empty |
| Store | region | enum | Yes | North/South/East/West |
| Store | store_type | enum | Yes | RETAIL/WAREHOUSE |
| Store | active | boolean | Yes | true/false |
| Store | effective_from | date | Yes | ISO date |
| SKU | sku_id | string | Yes | PK, `SKU-000001` |
| SKU | sku_name | string | Yes | Non-empty |
| SKU | category | enum | Yes | Grocery/Electronics/Apparel/Home |
| SKU | unit_cost | decimal | Yes | >= 0 |
| SKU | unit | string | Yes | `each` |
| InventoryMovement | movement_id | string | Yes | PK, `MOV-2026-00000001` |
| InventoryMovement | store_id, sku_id | string | Yes | FK to Store and SKU |
| InventoryMovement | movement_type | enum | Yes | RECEIPT/SALE/TRANSFER_OUT/TRANSFER_IN/ADJUSTMENT/DAMAGE/RETURN |
| InventoryMovement | quantity | integer | Yes | Positive magnitude |
| InventoryMovement | signed_quantity | integer | Yes | Positive adds stock; negative removes stock |
| InventoryMovement | reason_code | string | Yes | Non-empty; adjustment requires reason |
| InventoryMovement | employee_role_id, shift_id | string | Yes | FK to EmployeeRole and Shift |
| InventoryMovement | promotion_id | string | No | Optional FK to Promotion |
| InventoryMovement | transfer_group_id | string | No | Shared key for paired transfer legs |
| InventoryMovement | event_timestamp | datetime | Yes | ISO timestamp |
| CycleCount | cycle_count_id | string | Yes | PK, `CNT-2026-000001` |
| CycleCount | store_id, sku_id | string | Yes | FK to Store and SKU |
| CycleCount | system_qty, physical_qty | integer | Yes | >= 0 |
| CycleCount | variance_qty | integer | Yes | physical_qty - system_qty |
| CycleCount | counted_by_role_id | string | Yes | FK to EmployeeRole |
| CycleCount | count_timestamp | datetime | Yes | Must follow included movement events |
| EmployeeRole | employee_role_id | string | Yes | PK |
| EmployeeRole | employee_id | string | Yes | Unique synthetic employee ID |
| EmployeeRole | role | enum | Yes | OPERATOR/ANALYST/MANAGER/ADMIN |
| EmployeeRole | authorized_actions | string | Yes | Pipe-delimited action list |
| EmployeeRole | effective_from/to | date | Yes/No | Role effective period |
| Shift | shift_id | string | Yes | PK |
| Shift | store_id | string | Yes | FK to Store |
| Shift | employee_role_id | string | Yes | FK to EmployeeRole |
| Shift | shift_name | enum | Yes | MORNING/EVENING/NIGHT |
| Shift | start_time/end_time | datetime | Yes | end after start |
| Promotion | promotion_id | string | Yes | PK |
| Promotion | promotion_name | string | Yes | Non-empty |
| Promotion | discount_pct | decimal | Yes | 0–100 percent |
| Promotion | start_date/end_date | date | Yes | end >= start |
| Return | return_id | string | Yes | PK |
| Return | movement_id | string | Yes | FK to return movement |
| Return | store_id, sku_id | string | Yes | FK to Store and SKU |
| Return | quantity | integer | Yes | > 0 |
| Return | return_reason | enum | Yes | CUSTOMER_CHANGED_MIND/DAMAGED_ON_ARRIVAL/WRONG_ITEM |
| Return | disposition | enum | Yes | RESTOCK/QUARANTINE/WRITE_OFF |
| ShrinkageAlert | alert_id | string | Yes | PK, `SHR-2026-000001` |
| ShrinkageAlert | store_id, sku_id | string | Yes | FK to Store and SKU |
| ShrinkageAlert | severity | enum | Yes | LOW/MEDIUM/HIGH |
| ShrinkageAlert | status | enum | Yes | OPEN/UNDER_REVIEW/RESOLVED |
| Investigation | investigation_id | string | Yes | PK, `INV-2026-000001` |
| Investigation | alert_id | string | Yes | FK to ShrinkageAlert |
| Investigation | lifecycle_state | enum | Yes | OPEN/UNDER_REVIEW/CLOSED |
| Investigation | assigned_to | string | Yes | Synthetic role/employee reference |
| InvestigationEvent | event_id | string | Yes | PK; append-only audit event |
| Ground truth | case_id | string | Yes | PK; evaluation-only label |
| Ground truth | ground_truth_label | enum | Yes | ANOMALY/BENIGN |

## Relationship cardinality

- Store 1:N Shift, OpeningBalance, InventoryMovement, CycleCount, ShrinkageAlert.
- SKU 1:N OpeningBalance, InventoryMovement, CycleCount, Return, ShrinkageAlert.
- EmployeeRole 1:N Shift and InventoryMovement.
- Shift 1:N InventoryMovement.
- Promotion 1:N InventoryMovement; movement promotion is optional.
- InventoryMovement 1:0..1 Return record in this synthetic generator; a return references its source return movement.
- ShrinkageAlert 1:0..N InvestigationEvent through an Investigation.
- ShrinkageAlert 1:0..1 active Investigation in the operational workflow.
- Transfers are paired logically using `transfer_group_id`; a transfer group can contain source and destination legs.

## Lifecycle

Alert: OPEN → UNDER_REVIEW → RESOLVED.
Investigation: OPEN → UNDER_REVIEW → CLOSED.
State changes must append an InvestigationEvent; do not overwrite prior events.
