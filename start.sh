#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/aplikasi"

python3 buat_database.py
python3 isi_contoh.py
exec python3 app.py
