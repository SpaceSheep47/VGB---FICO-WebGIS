@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo           WebGIS Goias - Inicializacao
echo ================================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set PYTHON=py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set PYTHON=python
    ) else (
        echo ERRO: Python nao foi encontrado.
        echo Instale Python 3.10 ou superior e marque "Add Python to PATH".
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo ERRO ao criar o ambiente virtual.
        pause
        exit /b 1
    )
)

echo Instalando dependencias...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo Iniciando WebGIS...
echo Acesse http://127.0.0.1:5000
echo.

start "" http://127.0.0.1:5000
.venv\Scripts\python.exe app.py

endlocal
