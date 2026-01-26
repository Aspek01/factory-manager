# TENANCY AUDIT EVENTS — LOCKED (D-0.4)

## 1. Purpose
Bu doküman, Factory Manager'da **tenancy ve context ile ilgili**
hangi olayların **zorunlu olarak audit log'a yazılacağını** tanımlar.

## 2. Audit Event Principles
- Audit log append-only'dir
- UPDATE / DELETE yasaktır
- Her event idempotency_key içerir
- Event'ler company-scope bazlıdır (SYSTEM hariç)

## 3. Mandatory Audit Events

### 3.1 Authentication
- user_login_success
- user_login_failure
- user_logout

Payload:
- user_id
- timestamp
- ip_address

### 3.2 Active Scope Resolution
- active_company_selected
- active_facility_selected
- active_section_selected
- active_workstation_selected

Payload:
- user_id
- role
- scope_type
- scope_id

### 3.3 Context Switch
- context_switch_attempt
- context_switch_success
- context_switch_denied

Payload:
- user_id
- from_scope
- to_scope
- reason (if denied)

### 3.4 Cross-Company Violation
- cross_company_access_attempt

Payload:
- user_id
- requested_company_id
- allowed_company_id
- endpoint

## 4. System-Level Events
(SYSTEM scope — company_id NULL)

- system_admin_login
- company_created
- company_disabled

## 5. Audit Invariants
- Audit event context immutable'dır
- Event payload sonradan değiştirilemez
- Context doğrulanmadan audit yazılamaz

STATUS: LOCKED
