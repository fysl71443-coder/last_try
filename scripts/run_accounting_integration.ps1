# Run Accounting Integration (Node + Flask + tests)
# Usage: .\scripts\run_accounting_integration.ps1 [init-db|start-node|test|all]

param([string]$Action = "all")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }
Set-Location $root

# Load .env
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

function Ensure-Env {
    if (-not $env:ACCOUNTING_KEY) { $env:ACCOUNTING_KEY = "dev-key-accounting" }
    if (-not $env:ACCOUNTING_API) { $env:ACCOUNTING_API = "http://127.0.0.1:3000" }
}

function Init-Db {
    Set-Location "$root\accounting-service"
    npm run init-db
    Set-Location $root
}

function Start-Node {
    Ensure-Env
    $nodeDir = "$root\accounting-service"
    if (-not (Get-Process -Name node -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath "node" -ArgumentList "src/index.js" -WorkingDirectory $nodeDir -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }
    $env:PORT = "3000"
    Write-Host "Node accounting: ensure running on port 3000 (or start manually: cd accounting-service && npm start)"
}

function Run-Tests {
    Ensure-Env
    python -m pytest tests/test_accounting_integration.py -v
}

function Run-All {
    Ensure-Env
    Write-Host "1. Init Node DB (if needed)..."
    Init-Db
    Write-Host "2. Start Node (manual in other terminal: cd accounting-service && npm start)"
    Write-Host "3. Run integration tests..."
    Run-Tests
}

switch ($Action.ToLower()) {
    "init-db" { Init-Db }
    "start-node" { Start-Node }
    "test" { Run-Tests }
    "all" { Run-All }
    default { Run-All }
}
