@echo off
cd /d "%~dp0"
python app.py
if errorlevel 1 (
  echo.
  echo Nao foi possivel iniciar. Verifique se Python, Flask e ReportLab estao instalados.
  pause
)
