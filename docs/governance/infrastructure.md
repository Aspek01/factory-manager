\# Infrastructure (LOCKED)



Bu doküman, \*\*runtime, deploy ve istisnai operasyon\*\* varsayımlarını tanımlar.  

Governance kapsamındadır. İhlal = \*\*operasyonel hata\*\*.



---



\## 1) Runtime (LOCKED)



\- Backend: \*\*Django 5.x\*\*

\- Database: \*\*PostgreSQL 16\*\*

\- Cache / Queue: \*\*Redis\*\* (opsiyonel, MVP zorunlu değil)

\- Object Storage: \*\*MinIO\*\* (internal, S3-compatible)



---



\## 2) Environment Configuration (Minimum — LOCKED)



Zorunlu environment değişkenleri:



\### Core

\- `DATABASE\_URL`

\- `SECRET\_KEY`

\- `ALLOWED\_HOSTS`



\### Email

\- `EMAIL\_HOST`

\- `EMAIL\_PORT`

\- `EMAIL\_HOST\_USER`

\- `EMAIL\_HOST\_PASSWORD`

\- `DEFAULT\_FROM\_EMAIL`



\### Storage (MinIO)

\- `STORAGE\_ENDPOINT`

\- `STORAGE\_ACCESS\_KEY`

\- `STORAGE\_SECRET\_KEY`

\- `STORAGE\_BUCKET\_NAME`



Eksik env → \*\*startup FAIL\*\* (fail-fast).



---



\## 3) Deployment Assumptions (LOCKED)



\- Sistem \*\*containerized\*\* deploy edilir (Coolify uyumlu).

\- Deploy pipeline sırası:

&nbsp; 1. Image build

&nbsp; 2. Container start

&nbsp; 3. \*\*Django migrations çalıştırılır\*\*

&nbsp; 4. Health-check OK ise trafik açılır

\- Backward compatibility varsayımı \*\*YOK\*\*.

\- “Zaten vardı” gerekçesi \*\*GEÇERSİZ\*\*.



---



\## 4) Migrations Policy (LOCKED)



\- Tüm schema değişiklikleri \*\*migration ile\*\* yapılır.

\- Elle DB müdahalesi YASAK (istisna: aşağıdaki \*Data Repair\*).

\- Migration’lar:

&nbsp; - Deterministik olmalı

&nbsp; - Tekrar çalıştırıldığında yan etki üretmemeli

\- `atomic = False`:

&nbsp; - Sadece \*\*zorunlu\*\* durumlarda (ör. `CREATE INDEX CONCURRENTLY`).



---



\## 5) Ledger Unique Index \& Prod-Safe Strategy (LOCKED)



\### Amaç

Ledger logical key için DB-level uniqueness sağlamak \*\*kesin zorunludur\*\*.



\### Prod Varsayımı

\- Unique index \*\*CONCURRENTLY\*\* oluşturulur.

\- Index oluşturulmadan önce:

&nbsp; - Mevcut ledger’da logical-key duplikasyonu \*\*OLMAMALI\*\*.



\### Eğer duplikasyon VARSA

Bu durum \*\*bug\*\* değil, \*\*data drift\*\* olarak ele alınır.



---



\## 6) Data Repair Procedure (İstisnai — LOCKED)



> \*\*ÖNEMLİ:\*\*  

> Data repair, \*\*append-only kuralını ihlal eden bir normal operasyon DEĞİLDİR\*\*.  

> Bu işlem \*\*sadece istisnai, kontrollü ve kayıt altına alınmış\*\* bir prosedürdür.



\### Ne Zaman?

\- Unique index eklenemiyorsa

\- Ledger logical key çakışmaları tespit edildiyse



\### Nasıl?

1\. Sistem \*\*maintenance mode\*\* alınır (write kapalı).

2\. Ledger logical key’e göre \*\*deterministik dedupe\*\* yapılır:

&nbsp;  - Aynı logical key grubunda:

&nbsp;    - \*\*en eski kayıt korunur\*\*

&nbsp;    - diğerleri silinir

3\. İşlem \*\*migration veya tek seferlik SQL script\*\* ile yapılır.

4\. Unique index oluşturulur.

5\. Sistem tekrar write’a açılır.



\### Deterministik Kural

\- Sıralama:

&nbsp; - `created\_at ASC`

&nbsp; - `id ASC`

\- Bu kural \*\*değiştirilemez\*\*.



\### Kayıt

\- Yapılan repair:

&nbsp; - Audit log’a

&nbsp; - Deploy notlarına

&nbsp; - Versiyon notlarına

&nbsp; yazılır.



---



\## 7) Logging \& Monitoring (Minimum — LOCKED)



\- Django error logs açık olmalıdır.

\- DB hataları (IntegrityError dahil) görünür olmalıdır.

\- Aşağıdaki durumlar \*\*mutlaka loglanır\*\*:

&nbsp; - Ledger guard ihlalleri

&nbsp; - Idempotency çakışmaları (NO-OP)

&nbsp; - Data repair çalıştırılması

\- Fail-fast davranış \*\*log + stop\*\* şeklindedir.



---



\## 8) Hard Out-of-Scope (ENFORCED)



\- Silent data repair

\- Otomatik dedupe

\- Runtime’da ledger mutation

\- Try/except ile guard yutma

\- UI üzerinden data repair tetikleme



Bu dosya \*\*LOCKED\*\*’tır.  

Değişiklik yalnızca \*\*yeni MAJOR sürüm\*\* ile mümkündür.



