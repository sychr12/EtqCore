@echo off
setlocal
title Inicializador do Sistema
color 0A

cd /d "%~dp0"

echo ==========================================
echo          INICIANDO O SISTEMA
echo ==========================================
echo.

:: Verifica se o Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado.
    echo.
    echo Instale o Python e marque a opcao:
    echo "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado.

:: Verifica se requirements.txt existe
if not exist "requirements.txt" (
    echo.
    echo [ERRO] requirements.txt nao foi encontrado.
    echo Local esperado:
    echo %CD%\requirements.txt
    echo.
    pause
    exit /b 1
)

echo [OK] requirements.txt encontrado.
echo.

:: Instala as dependencias
echo ==========================================
echo       VERIFICANDO DEPENDENCIAS
echo ==========================================
echo.

python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ==========================================
    echo                 ERRO
    echo ==========================================
    echo.
    echo Nao foi possivel instalar as dependencias.
    echo Verifique sua conexao com a internet.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Dependencias instaladas.
echo.

:: Verifica se app.py existe
if not exist "app.py" (
    echo [ERRO] O arquivo app.py nao foi encontrado.
    echo.
    echo Local esperado:
    echo %CD%\app.py
    echo.
    pause
    exit /b 1
)

echo [OK] app.py encontrado.
echo.
echo ==========================================
echo          INICIANDO APLICACAO
echo ==========================================
echo.

python app.py

if errorlevel 1 (
    echo.
    echo ==========================================
    echo                 ERRO
    echo ==========================================
    echo.
    echo Nao foi possivel iniciar o sistema.
    echo Verifique os erros apresentados acima.
    echo.
    pause
    exit /b 1
)

echo.
echo Aplicacao encerrada.
pause

endlocal