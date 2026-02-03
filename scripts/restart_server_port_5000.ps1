# إيقاف العمليات على المنفذ 5000 وإعادة تشغيل الخادم في وضع المطور
# Run from project root: .\scripts\restart_server_port_5000.ps1

$port = 5000
Write-Host "Checking for processes on port $port..." -ForegroundColor Cyan

$connections = netstat -ano | Select-String ":$port\s"
if ($connections) {
    $pids = @()
    foreach ($line in $connections) {
        $parts = $line -split '\s+'
        $pid = $parts[-1]
        if ($pid -match '^\d+$' -and $pid -ne '0') { $pids += $pid }
    }
    $pids = $pids | Select-Object -Unique
    foreach ($p in $pids) {
        Write-Host "Killing PID $p..." -ForegroundColor Yellow
        try { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } catch {}
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "No process found on port $port." -ForegroundColor Green
}

$env:FLASK_DEBUG = "1"
$env:FLASK_ENV = "development"
Write-Host "Starting server on http://127.0.0.1:$port (debug mode)..." -ForegroundColor Green
Set-Location $PSScriptRoot\..
python run.py
