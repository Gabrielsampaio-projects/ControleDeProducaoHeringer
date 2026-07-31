@echo off
chcp 65001 >nul
title Motor de Comparacao - Controle de Producao

echo Verificando dependencias (pandas, openpyxl, requests)...
python -m pip install --quiet pandas openpyxl requests

echo.
echo Iniciando o motor de comparacao...
echo.
python "%~dp0motor_producao.py"

echo.
pause
