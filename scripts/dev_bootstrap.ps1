$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][scriptblock]$Cmd
    )
    & $Cmd
    if ($LASTEXITCODE -ne 0) {
        throw "BLOCKER: $Label failed (exit=$LASTEXITCODE)"
    }
}

# Repo root: bu script'in bulunduğu klasörün bir üstü
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot
Write-Host "Repo root:" $repoRoot

# Django settings module (bu terminalde kalsın)
$env:DJANGO_SETTINGS_MODULE = "factory_manager.settings"

# Docker compose ayakta olsun
if (Test-Path ".\docker-compose.yml") {
    Invoke-Checked "docker compose up" { docker compose up -d }
} elseif (Test-Path ".\compose.yml") {
    Invoke-Checked "docker compose up (compose.yml)" { docker compose -f .\compose.yml up -d }
} else {
    throw "BLOCKER: docker-compose.yml / compose.yml yok."
}

# Postgres container adını deterministik bul (image üzerinden)
$pgName = docker ps --format "{{.Image}} {{.Names}}" `
| Select-String -Pattern "^postgres:" `
| ForEach-Object { ($_ -split " ")[1] } `
| Select-Object -First 1

if (-not $pgName) { throw "BLOCKER: postgres container yok. docker ps çıktısını kontrol et." }
Write-Host "Postgres container:" $pgName

Invoke-Checked "pg_isready" { docker exec $pgName pg_isready }

Invoke-Checked "django check" { python manage.py check }
Invoke-Checked "django migrate" { python manage.py migrate }

# Canary normalize (AVAILABLE-based; negative'e düşmez)
Invoke-Checked "seed_stock_canary normalize" { python manage.py seed_stock_canary --normalize-to-target }

Invoke-Checked "rebuild_stock_summary" { python manage.py rebuild_stock_summary }

Write-Host "OK: dev bootstrap completed"
