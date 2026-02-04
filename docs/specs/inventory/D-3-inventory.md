# D-3 — Inventory (LOCKED SPEC)

## 1) Purpose
Inventory modülü; Parça kartı (Part Master), BOM, append-only stok defteri (Stock Ledger), WAC maliyet yöntemi ve UI için read-model’leri sağlar.

## 2) Scope Boundaries
### In-scope
- Part Master (type/strategy constraints)
- BOM (multi-level, safety rules)
- Stock Ledger (append-only, cost-aware)
- WAC only
- Read-models:
  - PartStockSummary (available_qty, weighted_avg_cost, last_purchase_cost, last_production_cost, updated_at)

### Out-of-scope (MVP dışı)
- FIFO/LIFO/Specific costing
- Multi-location/bins
- Batch/serial full trace
- Barcode scanning
- Lot expiry
- Advanced inventory valuation reports

## 3) Data Model (Entities)
### 3.1 Part
- id (UUID)
- company_id (UUID, required)
- part_no (string, unique per company)
- name (string)
- part_type: finished_good | semi_finished | raw_material | consumable | fixed_asset
- procurement_strategy: make | buy
- is_saleable (bool)
- standard_cost (decimal, nullable) — manual (PE/CM)
- last_purchase_price (decimal, nullable, read-only) — GR’den güncellenir
- created_at, updated_at

**Constraints**
- finished_good MUST make
- raw_material/consumable/fixed_asset MUST buy
- semi_finished make OR buy

### 3.2 BOM
- id (UUID)
- company_id
- parent_part_id (FK Part) — only finished_good, semi_finished
- revision_index (int) (MVP: opsiyonel ama önerilen)
- is_active (bool)
- created_at

### 3.3 BOMItem
- id (UUID)
- company_id
- bom_id (FK BOM)
- component_part_id (FK Part) — only semi_finished, raw_material, consumable(direct)
- qty_per (decimal)
- is_direct (bool) (consumable için)
- created_at

**Safety**
- max depth 10
- circular reference forbidden

### 3.4 StockLedgerEntry (Append-only)
- id (UUID)
- company_id (required)
- part_id (FK Part)
- movement_type: in | out | adjustment
- source_type: purchase | production | sales | adjustment | subcontracting_send | subcontracting_receive
- qty (decimal; out negatif değil, movement_type ile ifade edilir)
- unit_cost (decimal; IN zorunlu, OUT için WAC snapshot yazılır)
- transaction_value (decimal; qty * unit_cost)
- reference_price (decimal, nullable; sales snapshot)
- source_ref (json) — {order_id, wo_id, po_id, gr_id, supplier_id...}
- created_at

**Invariants**
- UPDATE/DELETE yasak
- Düzeltme = reverse/adjustment entry

## 4) Domain Rules
### 4.1 WAC Calculation
- WAC sadece IN hareketlerinde güncellenir:
  - purchase_in, production_in, subcontracting_receive
- OUT hareketleri mevcut WAC snapshot’u ile unit_cost yazar.
- WAC read-model’de tutulur, UI ledger’dan okumaz.

### 4.2 last_purchase_price
- Sadece GR (D-4) PASS sonrası güncellenir.
- UI’da read-only.

## 5) Read-models (UI zorunlu)
### 5.1 PartStockSummary
- company_id, part_id
- available_qty
- weighted_avg_cost
- last_purchase_cost
- last_production_cost
- updated_at

**Update Source**
- StockLedgerEntry insert sonrası deterministic recompute (sync job / management command)
- MVP: synchronous update (transaction sonrası) kabul; async yok.

## 6) API Surface (Draft, locked after D-3.1)
- Part CRUD (create/edit by PE/CM)
- BOM CRUD (create/edit by PE/CM)
- Stock view endpoints read-model’den
- Controlled adjustment endpoint (PL/CM)

## 7) RBAC
- Part create/edit: PE ✅, CM ✅
- BOM create/edit: PE ✅, CM ✅
- Stock view: CM ✅, PE ✅, PL ✅, PU ✅, GR ✅; OP 👁️ (own material only)
- Adjustment: PL ✅ (controlled), CM ✅ (controlled)

## 8) UI (Draft)
- Part list/detail (responsive)
- BOM editor (tree + depth guard)
- Stock dashboard (PartStockSummary)
- Adjustment form (controlled, reason required)

## 9) Validation & Guardrails
- Part constraints enforce on create/update
- BOM safety checks on add/update:
  - depth <= 10
  - circular forbidden
- Ledger append-only enforced model-level
- Read-model required for UI endpoints

## 10) Migrations
- New tables: Part, BOM, BOMItem, StockLedgerEntry, PartStockSummary
- All with company_id indexes.

## 11) Acceptance Criteria
- Spec dosyası LOCKED olarak repo’da var
- Governance dosyaları var (yoksa oluşturuldu)
- D-3.1’e geçiş için hazır: “Model/Migration implement” task’ı üretilebilir
