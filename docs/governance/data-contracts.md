# Data Contracts (LOCKED)

## 1) Part Type + Procurement Strategy Constraints
- part_type: finished_good | semi_finished | raw_material | consumable | fixed_asset
- procurement_strategy: make | buy
- Constraints:
  - finished_good MUST make
  - raw_material/consumable/fixed_asset MUST buy
  - semi_finished make OR buy
- is_saleable: raw/semi/consumable için opsiyonel; finished_good genelde true

## 2) BOM Safety Rules
- Multi-level BOM desteklenir.
- Max depth: 10
- Circular reference forbidden.

## 3) Costing Method
- WAC only (Weighted Average Cost)
- WAC yalnız “IN” hareketleriyle güncellenir:
  - purchase_in, production_in, subcontracting_receive
- “OUT” hareketleri WAC snapshot kullanır.

## 4) Stock Ledger Contract (Append-only)
- movement_type: in | out | adjustment
- source_type: purchase | production | sales | adjustment | subcontracting_send | subcontracting_receive
- required fields:
  - qty
  - unit_cost (IN için zorunlu; OUT için WAC snapshot)
  - transaction_value = qty * unit_cost
  - company_id zorunlu
  - source_ref ilişkilendirme zorunlu (order_id/wo_id/po_id/gr_id vb.)

## 5) QC Trigger Matrix (Minimum)
- Incoming QC: GR created → QI executes → PASS stock-in / FAIL block
- In-process QC: op complete & requires_inspection → PASS next op / FAIL manual
- Final QC: last op complete → finished_good için zorunlu → PASS production_in / FAIL manual

## 6) Lot Tracking (MVP)
- WorkOrder release sonrası lot_code immutable.
- Serial yok, full trace yok; lot_code linkleme var.
