
Write-Host "Generating Param Review Report..." -ForegroundColor Cyan

python app/pc/param_review.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Success." -ForegroundColor Green
}
else {
    Write-Host "Failed." -ForegroundColor Red
}
