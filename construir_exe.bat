@echo off
REM Gera dist\Conversor de Ficha Financeira.exe
cd /d "%~dp0"
echo Instalando dependencias...
python -m pip install -r requirements.txt pyinstaller pillow --quiet
echo.
echo Construindo o executavel (pode levar 1-2 minutos)...
python -m PyInstaller --noconfirm --clean ConversorWeb.spec
echo.
if exist "dist\Conversor de Ficha Financeira.exe" (
  echo PRONTO: dist\Conversor de Ficha Financeira.exe
) else (
  echo FALHOU. Veja as mensagens acima.
)
pause
