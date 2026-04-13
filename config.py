from __future__ import annotations
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'exam-prep-secret-key-2026')

_db_url = os.environ.get('DATABASE_URL', '')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
SQLALCHEMY_DATABASE_URI = _db_url or ('sqlite:///' + os.path.join(BASE_DIR, 'instance', 'exam_prep.db'))
SQLALCHEMY_TRACK_MODIFICATIONS = False
PORT = int(os.environ.get('PORT', 5011))
