#!/usr/bin/env bash
# Render build qadamlari — root directory = backend/ (manage.py shu yerda).
# Xatolik yuz bersa jarayonni darhol to'xtatadi, yarim holatdagi deploy
# serverga chiqmaydi.
set -o errexit

# Kutubxonalar (Django, DRF, psycopg, gunicorn, whitenoise, dj-database-url).
# `python -m pip` — pip aynan shu interpreterga tegishli bo'lishi uchun.
python -m pip install -r requirements.txt

# Statik fayllarni WhiteNoise uchun yig'ish (admin + DRF statiki)
python manage.py collectstatic --no-input

# Migratsiyalar. Render'da bitta web service bo'lgani uchun parallel
# migrate xavfi yo'q; eski instansiya deploy tugaguncha ishlayveradi.
python manage.py migrate --no-input

# UI uchun majburiy idempotent seed ma'lumotlari (boshlang'ich katalog,
# universitetlar, tariflar, nishonlar) — ularsiz sahifalar bo'sh chiqadi.
python manage.py seed_catalog
python manage.py seed_universities
python manage.py seed_premium
python manage.py seed_badges
