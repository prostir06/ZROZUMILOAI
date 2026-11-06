# Windows-friendly backup (Task Scheduler or manual). Prefer backup-cron.sh on Linux VPS.
# Usage (repo root):
#   .\scripts\backup-cron.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$compose = @("docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
Write-Host "[$(Get-Date -Format o)] backup start"
$filename = & $compose exec -T backend python manage.py create_backup
Write-Host "[$(Get-Date -Format o)] created: $filename"
Write-Host "[$(Get-Date -Format o)] backup done — copy ./backup off-box"
