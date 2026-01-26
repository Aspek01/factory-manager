# INFRASTRUCTURE GOVERNANCE — LOCKED (V1)

## 1. Environment
- Backend: Django (prod-ready)
- DB: PostgreSQL
- Storage: S3-compatible (MinIO)
- Cache/Queue: Redis (future-safe)

## 2. Secrets & Config
- Secrets .env üzerinden yönetilir.
- Repo içinde secret tutulmaz.
- Prod varsayımı her zaman geçerlidir.

## 3. Deployment Assumptions
- Containerized deployment
- Stateless app nodes
- DB single source of truth

## 4. Logging & Monitoring (Minimum)
- Error logging zorunlu
- Audit log uygulama içi tutulur
- Infra logları dış sistemlere gönderilebilir (future)

STATUS: LOCKED
