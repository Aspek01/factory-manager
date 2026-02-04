# Technical Invariants (LOCKED)

## 1) Multi-tenant Data Isolation
- Her domain kaydı `company_id` ile izole edilir.
- Cross-company erişim kesin yasaktır.
- Scope hiyerarşisi: SYSTEM → COMPANY → FACILITY → SECTION → WORKSTATION
- Alt scope, üst scope'u asla göremez.

## 2) Append-only Ledger Invariants
- Ledger/audit türü kayıtlar UPDATE/DELETE kabul etmez.
- Düzeltme yalnızca reverse/adjustment entry ile yapılır.
- "Soft delete" yasaktır.

## 3) Fail-fast
- Guard ihlallerinde try/except ile yutma yoktur.
- Guard ihlali = PermissionDenied/ValidationError ile işlem kesilir.

## 4) Deterministik idempotency (API Event Standardı)
- Event üreten endpoint'ler idempotency-key kabul eder.
- Aynı key + aynı scope + aynı payload → aynı sonuç; mükerrer kayıt yok.
- Idempotency kayıtları append-only audit ile izlenebilir.

## 5) UI Read-model Kuralı
- UI, ledger tablosundan doğrudan okumaz.
- UI için read-model zorunludur (materialized/denormalized view tabloları).
