"""配置文件：数据库连接、应用密钥等"""

import os
import pymysql.cursors

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),  # 生产环境请设置环境变量 DB_PASSWORD
    "database": os.environ.get("DB_NAME", "study_checkin"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# SECRET_KEY：优先从环境变量读取，否则使用默认值（小范围使用场景）
# 如需更高安全性，设置环境变量 SECRET_KEY
_DEFAULT_SECRET = "study-checkin-tomato-2024-secret-key-fixed-default"
SECRET_KEY = os.environ.get("SECRET_KEY") or _DEFAULT_SECRET