# TENANCY DATA MODEL — LOCKED (D-0.5)

## 1. Purpose
Bu doküman, Factory Manager için **tenancy domain tablolarını**
ve aralarındaki **zorunlu ilişkileri** tanımlar.

## 2. Company
Table: company

Fields:
- id (PK)
- name
- legal_name
- status (active | disabled)
- created_at

Invariants:
- Company silinemez
- status=disabled → login ve context selection engellenir

## 3. Facility
Table: facility

Fields:
- id (PK)
- company_id (FK → company.id)
- name
- timezone
- created_at

Invariants:
- Facility her zaman tek bir company'ye bağlıdır
- Company disabled ise facility aktif olamaz

## 4. Section
Table: section

Fields:
- id (PK)
- facility_id (FK → facility.id)
- name
- created_at

Invariants:
- Section her zaman tek bir facility'ye bağlıdır

## 5. Workstation
Table: workstation

Fields:
- id (PK)
- section_id (FK → section.id)
- code (unique per section)
- is_active
- created_at

Invariants:
- Workstation her zaman tek bir section'a bağlıdır
- is_active=false ise operator assignment yapılamaz

## 6. Deletion & Mutation Rules
- Hiçbir tenancy entity DELETE edilemez
- Deaktivasyon status flag ile yapılır
- FK ilişkileri runtime'da değiştirilemez

STATUS: LOCKED
