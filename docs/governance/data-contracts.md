# DATA CONTRACTS — LOCKED (V1)

## 1. Part Type & Procurement Strategy
- finished_good → MUST make
- raw_material → MUST buy
- consumable → MUST buy
- fixed_asset → MUST buy
- semi_finished → make OR buy (explicit seçim zorunlu)

## 2. BOM Safety
- Max depth: 10
- Circular reference kesinlikle yasak.
- finished_good BOM component olamaz.
- fixed_asset BOM component olamaz.

## 3. Costing Method
- Yalnızca WAC (Weighted Average Cost) kullanılır.
- FIFO/LIFO/Specific yasaktır.
- unit_cost alanı tüm stock-in hareketlerinde zorunludur.

## 4. QC Trigger Matrix
- Incoming QC → GR created
- In-process QC → operation.complete AND requires_inspection=true
- Final QC → finished_good için zorunlu

## 5. Lot & Release Invariants
- WorkOrder release sonrası:
  - lot_code immutable
  - routing immutable
- Release sonrası BOM veya routing değiştirilemez.

STATUS: LOCKED
