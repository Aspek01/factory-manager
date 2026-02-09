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

### 2.1) Reverse Entry Standardı (LOCKED)
Amaç: Hatalı bir ledger satırının etkisini, **yeni bir append-only satır** ile sıfırlamak veya düzeltmek.

**Kurallar**
- Reverse, asla mevcut satırı değiştirmez; sadece yeni satır yazar.
- Reverse satırı mutlaka “hangi satırı terslediğini” referanslamalıdır.
- Reverse işleminde company boundary değişmez: `company_id` aynı olmalıdır.
- Reverse satırı, orijinal satırın **qty etkisini** tersine çevirmelidir:
  - Orijinal `movement_type=in` ise reverse satırı `movement_type=out` olur ve `qty` aynı büyüklükte olur.
  - Orijinal `movement_type=out` ise reverse satırı `movement_type=in` olur ve `qty` aynı büyüklükte olur.
  - Orijinal `movement_type=adjustment` ise reverse satırı `movement_type=adjustment` kalır ve `qty = -original.qty` olur.
- Reverse satırı bir kez yazılır; aynı original satır için ikinci reverse **yasaktır** (idempotency/uniqueness ile engellenir).
- Reverse satırı da ledger idempotency standardına tabidir.
- Reverse satırı yazıldığında:
  - Read-model’ler update edilir (normal ledger insert gibi).
  - Audit event emit edilir.

**Negatif stok ile etkileşim**
- Negatif stok guard fail-closed kalır.
- Reverse satırı, negatif stok guard’ı bypass etmez; projected balance yine 0’ın altına düşemez.
  - Bu, sistemin hiçbir koşulda “imkânsız stok”a düşmemesini garanti eder.

## 3) Fail-fast
- Guard ihlallerinde try/except ile yutma yoktur.
- Guard ihlali = PermissionDenied/ValidationError ile işlem kesilir.

## 4) Deterministik idempotency (API Event Standardı)
- Event üreten endpoint'ler idempotency-key kabul eder.
- Aynı key + aynı scope + aynı payload → aynı sonuç; mükerrer kayıt yok.
- Idempotency kayıtları append-only audit ile izlenebilir.

## 5) Ledger Idempotency (Domain Logical Key Standardı)
- Ledger türü yazımlarda (append-only) **mükerrer insert** yasaktır.
- Mükerrerlik, “aynı işin tekrar yazılması” anlamına gelir ve **logical key** ile tespit edilir.
- Logical key karşılaştırması **deterministik** olmalıdır:
  - Sayılar `Decimal` olarak normalize edilir (float kullanılmaz).
  - JSON (`source_ref`) yapısal eşitlik ile kıyaslanır (jsonb); uygulama tarafında key’ler deterministik üretilir.
- `StockLedgerEntry` için MVP logical key aşağıdaki alanlardan oluşur:
  - `company_id`
  - `part_id`
  - `movement_type`
  - `source_type`
  - `qty`
  - `unit_cost`
  - `reference_price` (nullable)
  - `source_ref` (json)
- Bu logical key ile aynı kayıt zaten varsa:
  - Yeni satır eklenmez (NO-OP).
  - Hook/event tetiklenmez (insert yoksa yok).

## 6) UI Read-model Kuralı
- UI, ledger tablosundan doğrudan okumaz.
- UI için read-model zorunludur (materialized/denormalized view tabloları).
