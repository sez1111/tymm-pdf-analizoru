@echo off
title TYMM PDF Analizoru
echo TYMM PDF Analizoru baslatiliyor...
echo.
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo Python bulunamadi. Lutfen python.org adresinden Python 3.11 veya 3.12 kurun.
    echo Kurulumda "Add Python to PATH" secenegini isaretleyin.
    pause
    exit /b
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app/app.py
pause
