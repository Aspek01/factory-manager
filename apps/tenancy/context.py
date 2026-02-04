import contextvars

active_company_id = contextvars.ContextVar("active_company_id", default=None)
active_facility_id = contextvars.ContextVar("active_facility_id", default=None)
active_section_id = contextvars.ContextVar("active_section_id", default=None)
active_workstation_id = contextvars.ContextVar("active_workstation_id", default=None)


def set_active_scope(company_id, facility_id=None, section_id=None, workstation_id=None):
    active_company_id.set(company_id)
    active_facility_id.set(facility_id)
    active_section_id.set(section_id)
    active_workstation_id.set(workstation_id)


def get_active_company_id():
    return active_company_id.get()


def require_active_company_id() -> str:
    company_id = active_company_id.get()
    if not company_id:
        raise RuntimeError("active_company_id is required for tenant-bound queries")
    return company_id

def clear_active_scope():
    set_active_scope(None)
