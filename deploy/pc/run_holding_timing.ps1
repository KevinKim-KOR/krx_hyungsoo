
Write-Host "Starting PC Holding Timing Analysis..." -ForegroundColor Cyan

python app/pc/holding_timing.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Analysis Completed." -ForegroundColor Green
}
else {
    Write-Host "Analysis Failed." -ForegroundColor Red
}
