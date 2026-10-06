#!/usr/bin/env bash
# Render build script: install dependencies, collect static files, run migrations.
set -o errexit

pip install -r requirements.txt

cd musicelo
python manage.py collectstatic --no-input
python manage.py migrate
