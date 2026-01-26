# DATA CONTRACTS — LOCKED (V1)

## Part & Procurement
- finished_good → MUST make
- raw_material / consumable / fixed_asset → MUST buy
- semi_finished → make OR buy

## BOM Safety
- Max depth: 10
- Circular reference YASAK

## Costing
- Yalnızca WAC
- unit_cost zorunlu

## QC
- Incoming QC → GR
- In-process QC → requires_inspection
- Final QC → finished_good

STATUS: LOCKED
