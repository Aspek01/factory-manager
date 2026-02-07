\# Data Contracts (LOCKED)



Bu doküman, domain seviyesinde \*\*veri sözleşmelerini\*\* tanımlar.  

Kod bu kurallara \*\*uymak zorundadır\*\*. İhlal = \*\*fail-fast\*\*.



---



\## 1) Part Type + Procurement Strategy Constraints (LOCKED)



\### Part Types

\- `finished\_good`

\- `semi\_finished`

\- `raw\_material`

\- `consumable`

\- `fixed\_asset`



\### Procurement Strategy

\- `make`

\- `buy`



\### Zorunlu Kurallar

\- `finished\_good` → \*\*MUST\*\* `make`

\- `raw\_material` → \*\*MUST\*\* `buy`

\- `consumable` → \*\*MUST\*\* `buy`

\- `fixed\_asset` → \*\*MUST\*\* `buy`

\- `semi\_finished` → `make` \*\*OR\*\* `buy`



\### is\_saleable

\- `raw\_material` → opsiyonel

\- `semi\_finished` → opsiyonel

\- `consumable` → opsiyonel

\- `finished\_good` → genelde `true`



İhlal:

\- `ValidationError`

\- Persist YASAK



---



\## 2) BOM Safety Rules (LOCKED)



\- Multi-level BOM desteklenir.

\- Maksimum BOM derinliği: \*\*10\*\*

\- Circular reference \*\*KESİNLİKLE YASAK\*\*.

\- İhlal:

&nbsp; - Fail-fast

&nbsp; - Persist YASAK



---



\## 3) Costing Method (LOCKED)



\### Costing

\- \*\*WAC (Weighted Average Cost) ONLY\*\*



\### WAC Güncelleyen Hareketler (IN)

\- `purchase`

\- `production`

\- `subcontracting\_receive` (purchase-like)



\### WAC Kullanılan Hareketler (OUT)

\- `sales`

\- `production consumption`



Kurallar:

\- WAC yalnız \*\*IN\*\* hareketlerinde yeniden hesaplanır.

\- \*\*OUT\*\* hareketleri:

&nbsp; - `unit\_cost` = \*\*WAC snapshot\*\*

\- FIFO ❌

\- LIFO ❌

\- Specific cost ❌



---



\## 4) Stock Ledger Contract (Append-only — LOCKED)



\### Movement Types

\- `in`

\- `out`

\- `adjustment`



\### Source Types

\- `purchase`

\- `production`

\- `sales`

\- `adjustment`

\- `subcontracting\_send`

\- `subcontracting\_receive`



\### Zorunlu Alanlar

\- `company\_id`

\- `part\_id`

\- `qty`

\- `unit\_cost`

&nbsp; - IN için \*\*zorunlu\*\*

&nbsp; - OUT için \*\*WAC snapshot\*\*

\- `transaction\_value`

&nbsp; - `qty \* unit\_cost`

\- `source\_ref`

&nbsp; - order\_id / wo\_id / po\_id / gr\_id vb. ilişkilendirme

&nbsp; - Boş bırakılmaz



\### Append-only Kuralları

\- UPDATE ❌

\- DELETE ❌

\- Soft delete ❌

\- Düzeltme:

&nbsp; - Sadece `adjustment` veya reverse entry



---



\## 5) Ledger Logical Key (Idempotency Contract — LOCKED)



Ledger yazımları \*\*idempotent\*\* olmak zorundadır.



\### Logical Key (MVP)

Aşağıdaki alanların \*\*tamamı birlikte\*\* logical key oluşturur:



\- `company\_id`

\- `part\_id`

\- `movement\_type`

\- `source\_type`

\- `qty`

\- `unit\_cost`

\- `reference\_price` (nullable)

\- `source\_ref` (json)



\### Kurallar

\- Aynı logical key ile ikinci yazım:

&nbsp; - \*\*NO-OP\*\*

&nbsp; - Yeni ledger satırı YOK

&nbsp; - Hook / event YOK

\- Karşılaştırma:

&nbsp; - Sayılar `Decimal` olarak normalize edilir

&nbsp; - `source\_ref` yapısal eşitlik (json semantics)

\- Logical key:

&nbsp; - Genişletilemez

&nbsp; - Backward compatibility YOK



---



\## 6) QC Trigger Matrix (Minimum — LOCKED)



\### Incoming QC

\- Trigger: GR created

\- Execute: `quality\_inspector`

\- Outcome:

&nbsp; - PASS → stock-in (ledger `in`)

&nbsp; - FAIL → stock-in \*\*BLOKE\*\*



\### In-process QC

\- Trigger: operation complete \*\*AND\*\* `requires\_inspection = true`

\- Outcome:

&nbsp; - PASS → next operation

&nbsp; - FAIL → manual (rework / scrap)



\### Final QC

\- Trigger: last operation complete

\- Zorunlu:

&nbsp; - `finished\_good`

\- Outcome:

&nbsp; - PASS → `production\_in`

&nbsp; - FAIL → manual



---



\## 7) Lot Tracking (MVP — LOCKED)



\- WorkOrder release sonrası:

&nbsp; - `lot\_code` \*\*IMMUTABLE\*\*

\- Serial tracking YOK

\- Full trace YOK

\- Bağlantılar:

&nbsp; - WorkOrder → Ledger → Shipment



---



\## 8) Hard Out-of-Scope (ENFORCED)



\- Serial number tracking

\- Multi-costing

\- Auto recost

\- Ledger mutation

\- Silent fallback / try-except yutma



Bu dosya \*\*LOCKED\*\*’tır.  

Değişiklik yalnızca \*\*yeni MAJOR sürüm\*\* ile mümkündür.



