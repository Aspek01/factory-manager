# TENANCY REQUEST CONTEXT — LOCKED (D-0.3)

## 1. Purpose
Bu doküman, her HTTP/API request için **aktif tenant ve scope bağlamının**
nasıl belirlendiğini ve zorunlu doğrulama adımlarını tanımlar.

## 2. Active Context Fields
Her request aşağıdaki context alanlarını taşır:
- active_company_id (zorunlu)
- active_facility_id (role bağlı)
- active_section_id (role bağlı)
- active_workstation_id (operator için zorunlu)

## 3. Context Resolution Order
1. Authenticated user
2. User role
3. Role → scope binding (D-0.2)
4. Explicit scope selection (UI veya header)
5. Final validation

## 4. Resolution Rules
- system_admin:
  - active_company opsiyonel (metadata-only erişim)
- company-level roller:
  - active_company zorunlu
  - facility/section/workstation opsiyonel (read-only)
- facility-level roller:
  - active_company + active_facility zorunlu
- section_supervisor:
  - active_company + active_facility + active_section zorunlu
- operator:
  - tüm active_* alanları zorunlu

## 5. Validation Rules
- active_company, kullanıcının bağlı olduğu company olmalı
- Scope zinciri hiyerarşiyi bozamaz
- Eksik veya uyumsuz scope → 403 Forbidden

## 6. Cross-Company Guard
- Request’te farklı company_id tespit edilirse:
  - Context oluşturulmaz
  - Audit log yazılır
  - Request reddedilir

## 7. Invariants
- Context request süresi boyunca immutable
- Context olmadan domain logic çalışmaz
- UI ve API aynı context kurallarını kullanır

STATUS: LOCKED
