# TECHNICAL INVARIANTS — LOCKED (V1)

## 1. Append-Only Ledger
- Ledger tablolarında UPDATE ve DELETE YASAK.
- Her düzeltme, yeni bir reverse/adjustment entry ile yapılır.
- Uygulama seviyesi + DB seviyesi koruma zorunludur.

## 2. Reverse Entry Standardı
- Yanlış hareket geri alınmaz.
- Zıt işaretli (qty ve value) yeni bir hareket oluşturulur.
- Orijinal hareket referansı zorunludur.

## 3. Tenant Isolation
- Tüm domain verileri company_id ile izole edilir.
- Cross-company erişim kesinlikle yasaktır.
- Read-model'ler dahil bu kuraldan muaf değildir.

## 4. Idempotency (API)
- Tüm write event'leri idempotency_key ile korunur.
- Aynı key ile gelen ikinci istek NO-OP olmalıdır.
- Idempotency key audit log'da saklanır.

## 5. UI Read Kuralı
- UI doğrudan ledger tablolarından okuyamaz.
- UI sadece read-model/view üzerinden veri alır.

STATUS: LOCKED
