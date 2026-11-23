"""Production entry point (used by gunicorn in Docker):  gunicorn wsgi:app"""

import os

import db
from app import create_app, load_env_file

load_env_file()
db.DB_ENGINE = os.getenv("DB_ENGINE", "mysql")
app = create_app()
