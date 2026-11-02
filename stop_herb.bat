@echo off
setlocal EnableExtensions
echo Encerrando processos H.E.R.B...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'Herb\\\\main.py|C:\\\\Herb\\\\main.py' -or ($_.Name -eq 'python.exe' -and $_.CommandLine -match 'main.py' -and $_.CommandLine -match 'Herb') } | ForEach-Object { Write-Host ('Stopping PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Concluido.
endlocal
