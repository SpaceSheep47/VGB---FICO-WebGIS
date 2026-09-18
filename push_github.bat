@echo off
setlocal
cd /d "%~dp0"

echo =======================================================
echo          WebGIS Goias - Envio para o GitHub
echo =======================================================
echo.

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] O Git nao foi encontrado no sistema.
    echo Certifique-se de que o Git esta instalado e configurado no PATH.
    echo.
    pause
    exit /b 1
)

echo [1/3] Adicionando arquivos (git add .)...
git add .
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao adicionar arquivos.
    echo.
    pause
    exit /b 1
)
echo Arquivos preparados com sucesso.
echo.

set "MSG="
set /p "MSG=Digite a mensagem do commit (pressione Enter para mensagem padrao): "
if "%MSG%"=="" (
    set "MSG=feat: atualizacao do WebGIS com banco de dados GeoPackage (FICO)"
)

echo.
echo [2/3] Criando commit...
git commit -m "%MSG%"
if %errorlevel% neq 0 (
    echo.
    echo [AVISO] Nenhuma alteracao pendente para commit ou alteracoes ja commitadas.
)
echo.

echo [3/3] Enviando para o GitHub (git push origin main)...
git push origin main
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao enviar para o GitHub.
    echo Verifique sua conexao e credenciais de acesso ao repositorio.
    echo.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo       Envio concluido com sucesso para o GitHub!
echo =======================================================
echo Repositorio: https://github.com/SpaceSheep47/VGB---FICO-WebGIS
echo.
pause
endlocal
