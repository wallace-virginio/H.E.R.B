# Gera HERB_v0.1.0.zip sem venv/caches/modelos
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$version = "0.1.0"
$out = Join-Path $root "HERB_v$version.zip"
if (Test-Path $out) { Remove-Item $out -Force }

$excludeDirs = @(
  "\.venv\\",
  "\\__pycache__\\",
  "\\\.pytest_cache\\",
  "\\data\\cache\\",
  "\\data\\memory\\.*\.db",
  "\\logs\\.*\.log"
)

$temp = Join-Path $env:TEMP "herb_release_$version"
if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
New-Item -ItemType Directory -Path $temp | Out-Null
$dest = Join-Path $temp "HERB"
New-Item -ItemType Directory -Path $dest | Out-Null

Get-ChildItem -Path $root -Force | Where-Object {
  $_.Name -notin @(".venv", "HERB_v0.1.0.zip", ".git")
} | ForEach-Object {
  Copy-Item $_.FullName -Destination (Join-Path $dest $_.Name) -Recurse -Force
}

# Limpa caches e artefatos
Get-ChildItem -Path $dest -Recurse -Force -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $dest -Recurse -Force -Directory -Filter ".pytest_cache" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $dest -Recurse -Force -Include "*.pyc","*.log","*.db" | Remove-Item -Force -ErrorAction SilentlyContinue
if (Test-Path (Join-Path $dest "data\config.json")) { Remove-Item (Join-Path $dest "data\config.json") -Force }
if (Test-Path (Join-Path $dest "data\cache")) {
  Get-ChildItem (Join-Path $dest "data\cache") -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Compress-Archive -Path $dest -DestinationPath $out -Force
Remove-Item $temp -Recurse -Force
Write-Host "ZIP criado: $out"
Get-Item $out | Format-List FullName, Length
