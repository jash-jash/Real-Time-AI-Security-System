# Real Time Security — Live public URL with branded name when possible
# Keep the app running first:  python main.py
# Then run:  powershell -ExecutionPolicy Bypass -File .\start_live.ps1

param(
    [int]$Port = 5000,
    [string]$Name = "realtimesecurity"
)

Write-Host ""
Write-Host "Creating branded live URL for Real Time Security..." -ForegroundColor Cyan
Write-Host "Keep python main.py running while this window stays open." -ForegroundColor Yellow
Write-Host ""

# Prefer a readable name via localtunnel (e.g. https://realtimesecurity.loca.lt)
Write-Host "Trying named link: https://$Name.loca.lt" -ForegroundColor Green
npx --yes localtunnel --port $Port --subdomain $Name
