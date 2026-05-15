#!/bin/bash
cd "$(dirname "$0")"
echo "TYMM PDF Analizörü başlatılıyor..."
python3 --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Python3 bulunamadı. Lütfen Python 3 kurun."
  exit 1
fi
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m streamlit run app/app.py
