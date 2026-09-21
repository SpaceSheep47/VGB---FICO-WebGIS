@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   VGB-FICO - Sincronizacao de panoramas no R2
echo ================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERRO: Python nao encontrado no PATH.
  pause
  exit /b 1
)

if not exist "data\panoramas" (
  mkdir "data\panoramas"
)

if "%R2_ENDPOINT_URL%"=="" (
  echo ERRO: defina as variaveis R2_ENDPOINT_URL, R2_ACCESS_KEY_ID,
  echo       R2_SECRET_ACCESS_KEY, R2_BUCKET e R2_PUBLIC_BASE_URL.
  echo.
  echo Exemplo: abra o PowerShell e execute as variaveis antes deste BAT.
  pause
  exit /b 1
)

echo Enviando fotografias de data\panoramas para o Cloudflare R2...
echo.
python "scripts\sync_panoramas_r2.py" --source "data\panoramas"
if errorlevel 1 (
  echo.
  echo ERRO durante a sincronizacao.
  pause
  exit /b 1
)

echo.
echo Sincronizacao concluida.
echo O WebGIS podera ler o novo index.json na proxima atualizacao/cache.
pause
