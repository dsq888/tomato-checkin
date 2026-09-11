#!/bin/bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=clock_user
export DB_PASSWORD=Kbgahe96
export DB_NAME=clock_db
export SECRET_KEY=dsq-love-learn-2024-secret-key-abc123
cd "/www/wwwroot/dsq love learn"
exec gunicorn app:app -w 2 -b 127.0.0.1:5000