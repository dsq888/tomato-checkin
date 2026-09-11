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

# SECRET_KEY：必须从环境变量读取，切勿使用硬编码默认值
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("请设置环境变量 SECRET_KEY，例如: export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')")