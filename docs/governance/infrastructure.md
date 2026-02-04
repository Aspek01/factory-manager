# Infrastructure (LOCKED)

## 1) Runtime
- Django 5.x
- PostgreSQL 16
- Redis (opsiyonel)
- Object Storage: MinIO (internal)

## 2) Env Config (minimum)
- DATABASE_URL
- SECRET_KEY
- ALLOWED_HOSTS
- EMAIL_HOST / EMAIL_PORT / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD / DEFAULT_FROM_EMAIL
- STORAGE_* (MinIO)

## 3) Deployment Assumptions
- Containerized deploy (Coolify uyumlu)
- Migrations deploy pipeline’da çalıştırılır.

## 4) Logging & Monitoring (minimum)
- Django error logs
- DB errors visible
- Audit ve ledger guard ihlalleri loglanır (fail-fast)
