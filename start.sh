#!/bin/bash
# 请通过环境变量或 .env 文件设置以下敏感信息，切勿硬编码
# export DB_HOST=localhost
# export DB_PORT=3306
# export DB_USER=clock_user
# export DB_PASSWORD=你的数据库密码
# export DB_NAME=clock_db
# export SECRET_KEY=你的随机密钥
cd "/www/wwwroot/dsq love learn"
exec gunicorn app:app -w 2 -b 127.0.0.1:5000