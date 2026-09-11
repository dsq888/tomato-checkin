"""初始化数据库：创建数据库和表，并创建默认管理员账号"""

import pymysql
import re
from config import DB_CONFIG
from werkzeug.security import generate_password_hash

db_name = DB_CONFIG["database"]

# 先连接 MySQL（不指定数据库），创建数据库
root_config = {k: v for k, v in DB_CONFIG.items() if k != "database"}
root_config.pop("cursorclass", None)

conn = pymysql.connect(**root_config)
cur = conn.cursor()
cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
conn.close()
print(f"数据库 {db_name} 已创建/已存在")

# 重新连接，指定数据库
conn = pymysql.connect(**DB_CONFIG)
cur = conn.cursor()

# 逐条执行建表 SQL
with open("init_db.sql", "r", encoding="utf-8") as f:
    sql_content = f.read()

sql_content = re.sub(r'--.*', '', sql_content)

statements = [s.strip() for s in sql_content.split(";") if s.strip()]

for stmt in statements:
    try:
        cur.execute(stmt)
    except pymysql.err.OperationalError as e:
        print(f"跳过（可能已存在）: {str(e)[:60]}")

conn.commit()
conn.close()
print("数据表已创建")

# 数据库迁移：移除旧版自习室遗留字段
conn = pymysql.connect(**DB_CONFIG)
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE check_records DROP FOREIGN KEY check_records_ibfk_2")
except pymysql.err.OperationalError:
    pass
try:
    cur.execute("ALTER TABLE check_records DROP COLUMN study_room_id")
    conn.commit()
    print("已移除旧版 study_room_id 列")
except pymysql.err.OperationalError:
    pass
# 迁移：添加每日学习目标字段
try:
    cur.execute("ALTER TABLE users ADD COLUMN daily_goal INT DEFAULT 7200 COMMENT '每日学习目标(秒)'")
    conn.commit()
    print("已添加 daily_goal 列")
except pymysql.err.OperationalError:
    pass
conn.close()

# 创建默认管理员
import models
admin_created = models.create_user("admin", "admin123", "管理员")
if admin_created:
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("UPDATE users SET role='admin' WHERE username='admin'")
    conn.commit()
    conn.close()
    print("默认管理员账号: admin / admin123")
else:
    print("管理员账号已存在")

print("初始化完成！")