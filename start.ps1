param(
    [string]$Python = "python"
)

Write-Host "Starting via run.py..." -ForegroundColor Cyan
& $Python -X utf8 run.py
exit $LASTEXITCODE

