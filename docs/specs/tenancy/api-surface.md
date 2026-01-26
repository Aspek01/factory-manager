# TENANCY API SURFACE — LOCKED (D-0.6)

## 1. Purpose
Bu doküman, Factory Manager için **tenancy domain API yüzeyini**
ve bu endpoint'lerin **erişim kurallarını** tanımlar.

## 2. General Rules
- Tüm endpoint'ler authentication gerektirir (SYSTEM hariç metadata)
- DELETE endpoint'leri YASAK
- Mutasyonlar audit event üretmek zorundadır
- Tüm write işlemleri idempotency_key ister

## 3. Company Endpoints
- POST   /api/companies                (system_admin)
- GET    /api/companies/{id}            (system_admin, company_manager*)
- PATCH  /api/companies/{id}            (system_admin)
- POST   /api/companies/{id}/disable    (system_admin)

* company_manager yalnızca own company

## 4. Facility Endpoints
- POST   /api/facilities                (company_manager)
- GET    /api/facilities/{id}            (company_manager, facility-level roles)
- PATCH  /api/facilities/{id}            (company_manager)
- POST   /api/facilities/{id}/disable    (company_manager)

## 5. Section Endpoints
- POST   /api/sections                  (company_manager)
- GET    /api/sections/{id}              (section_supervisor+)
- PATCH  /api/sections/{id}              (company_manager)

## 6. Workstation Endpoints
- POST   /api/workstations               (company_manager)
- GET    /api/workstations/{id}           (operator+)
- PATCH  /api/workstations/{id}           (company_manager)

## 7. Forbidden Operations
- DELETE /api/*        (ALL)
- PATCH FK relations   (ALL)
- Cross-company access (ALL)

## 8. Invariants
- API scope, request context ile uyumlu olmalı
- Endpoint logic context olmadan çalışamaz
- Response yalnızca izinli scope verisini içerir

STATUS: LOCKED
