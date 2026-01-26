# TENANCY SCOPE MODEL — LOCKED (D-0.1)

## 1. Purpose
Bu doküman, Factory Manager SaaS için **multi-tenant scope hiyerarşisini**
ve bu hiyerarşiye bağlı **erişim ve izolasyon kurallarını** tanımlar.

## 2. Scope Hierarchy
SYSTEM
 └── COMPANY
      └── FACILITY
           └── SECTION
                └── WORKSTATION

## 3. Scope Definitions
### SYSTEM
- Tüm sistemin üst scope’u
- Yalnızca system_admin erişebilir

### COMPANY
- Hukuki ve finansal sınır
- Tüm domain verileri company_id ile izole edilir

### FACILITY
- Fiziksel üretim tesisi
- Scheduling, production ve inventory bağlamı

### SECTION
- Facility içindeki üretim alanı
- Shopfloor ve scheduling section bazlıdır

### WORKSTATION
- Tekil makine / iş istasyonu
- Operator yalnızca kendi workstation’ını görür

## 4. Access Rules
- Üst scope alt scope’u okuyabilir (read)
- Alt scope üst scope’u ASLA göremez
- Cross-company erişim kesinlikle yasaktır

## 5. Data Isolation
- Tüm tablolar company_id içerir
- Read-model’ler dahil istisna yoktur

## 6. Invariants
- Scope hiyerarşisi runtime’da değiştirilemez
- Workstation her zaman tek bir section’a bağlıdır
- Section her zaman tek bir facility’ye bağlıdır

STATUS: LOCKED
