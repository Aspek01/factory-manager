# Factory Manager — Dev Bootstrap (Windows PowerShell)
# Deterministic local bring-up: repo root -> venv -> deps -> docker db -> django checks -> migrate -> canary -> rebuild

$ErrorActionPreference = "Stop"

# 0) Repo root'a git
$repoRoot = (Get-ChildItem -Path $PWD -Recurse -Filter manage.py -File | Select-Object -First 1).DirectoryName
if (-not $repoRoot) { throw "BLOCKER: manage.py bulunamadı" }
Set-Location $repoRoot
Write-Host "Repo root: $repoRoot"

# 1) venv
if (-not (Test-Path ".\.venv")) {
  Write-Host ".venv yok -> oluşturuluyor"
  py -m venv .venv
}
.\.venv\Scripts\Activate.ps1 | Out-Null

# 2) pip + deps
python -m pip install -U pip | Out-Null
python -m pip install -r requirements.txt | Out-Null

# 3) Docker Desktop + compose
$dockerInfo = docker info 2>$null
if (-not $dockerInfo) {
  Write-Host "Docker çalışmıyor -> Docker Desktop başlatılıyor"
  Start-Process "Docker Desktop"
  Write-Host "Docker açılınca ENTER"
  pause
}

if (Test-Path ".\docker-compose.yml") {
  docker compose up -d
} elseif (Test-Path ".\compose.yml") {
  docker compose -f .\compose.yml up -d
} else {
  throw "BLOCKER: docker-compose.yml / compose.yml yok."
}

# 4) Postgres container adı (image=postgres:)
$pgName = docker ps --format "{{.Image}} {{.Names}}" `
  | Select-String -Pattern "^postgres:" `
  | ForEach-Object { ($_ -split " ")[1] } `
  | Select-Object -First 1

if (-not $pgName) { throw "BLOCKER: postgres container bulunamadı (docker ps kontrol et)." }

Write-Host "Postgres container: $pgName"
docker exec $pgName pg_isready | Out-Host

# 5) Django env
$env:DJANGO_SETTINGS_MODULE = "factory_manager.settings"

# 6) Django checks + migrate
python manage.py check
python manage.py migrate

# 7) Canary + rebuild
python manage.py seed_stock_canary
python manage.py rebuild_stock_summary

Write-Host "OK: dev bootstrap completed"
