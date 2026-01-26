# TECHNICAL INVARIANTS — LOCKED (V1)

## Append-Only Ledger
- Ledger tablolarında UPDATE ve DELETE YASAK.
- Düzeltmeler reverse/adjustment entry ile yapılır.

## Tenant Isolation
- Tüm domain verileri company_id ile izole edilir.
- Cross-company erişim kesinlikle yasaktır.

## Idempotency
- Tüm write event’leri idempotency_key ile korunur.
- Aynı key ikinci kez işlenmez.

## UI Read Rule
- UI ledger’dan OKUYAMAZ.
- UI sadece read-model üzerinden okur.

STATUS: LOCKED
