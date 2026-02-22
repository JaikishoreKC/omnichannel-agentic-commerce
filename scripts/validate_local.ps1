param(
  [switch]$SkipE2E,
  [switch]$SkipPerf
)

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Backend tests + coverage gate (80%)..."
Push-Location "backend"
python -m pytest tests -q --cov=app --cov-report=term --cov-fail-under=80
Pop-Location

Write-Host "[2/4] Frontend build..."
npm --prefix frontend run build

if (-not $SkipE2E) {
  Write-Host "[3/4] Frontend E2E..."
  npm --prefix frontend run test:e2e
}
else {
  Write-Host "[3/4] Frontend E2E skipped."
}

if (-not $SkipPerf) {
  Write-Host "[4/4] Backend performance smoke..."
  Push-Location "backend"
  python -m app.scripts.perf_smoke --iterations 30 --ws-iterations 15
  Pop-Location
}
else {
  Write-Host "[4/4] Backend performance smoke skipped."
}

Write-Host "Local validation complete."
