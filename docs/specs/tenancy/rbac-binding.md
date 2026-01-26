# TENANCY RBAC BINDING — LOCKED (D-0.2)

## 1. Purpose
Bu doküman, Factory Manager’da **rollerin hangi scope’a bağlanabileceğini**
ve scope hiyerarşisi içindeki **erişim sınırlarını** tanımlar.

## 2. Role → Scope Binding (Allowed)
- system_admin → SYSTEM
- company_manager → COMPANY
- sales_engineer → COMPANY
- production_engineer → FACILITY
- planner → FACILITY
- purchasing → FACILITY
- goods_receipt_clerk → FACILITY
- quality_inspector → FACILITY
- section_supervisor → SECTION
- operator → WORKSTATION

## 3. Binding Rules
- Her kullanıcı **yalnızca tek bir aktif scope binding** ile çalışır
- Kullanıcı aynı anda birden fazla company’ye bağlı olamaz
- Scope binding runtime’da keyfi değiştirilemez (explicit switch gerekir)

## 4. Visibility Rules
- SYSTEM: tüm company metadata (operational data hariç)
- COMPANY: kendi company altındaki tüm facility’ler
- FACILITY: yalnızca kendi facility’si
- SECTION: yalnızca kendi section’ı
- WORKSTATION: yalnızca kendi workstation’ı

## 5. Negative Rules (Critical)
- operator:
  - Diğer workstation’ları GÖREMEZ
  - Facility-wide listeleri GÖREMEZ
  - Sadece assigned operations + own queue görür

## 6. Invariants
- Role, izin vermediği scope’a bağlanamaz
- Scope hiyerarşisi RBAC ile bypass edilemez
- Cross-company role binding kesinlikle yasaktır

STATUS: LOCKED
