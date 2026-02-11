
Write-Host "Starting PC Param Search V1..." -ForegroundColor Cyan

# Dependencies check?
# We assume pandas/requests installed. If not, user needs to pip install.
# pip install pandas requests

python app/pc/param_search.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Search Completed Successfully." -ForegroundColor Green
}
else {
    Write-Host "Search Failed." -ForegroundColor Red
}
