"""数据库操作层：封装所有 SQL 操作，避免在路由中直接写 SQL"""

import pymysql
from config import DB_CONFIG
from contextlib import contextmanager
from typing import Optional, Tuple, List, Dict
from werkzeug.security import generate_password_hash, check_password_hash
from dbutils.pooled_db import PooledDB
import secrets

# 数据库连接池
_pool = PooledDB(
    creator=pymysql,
    maxconnections=10,
    mincached=2,
    maxcached=5,
    blocking=True,
    **DB_CONFIG,
)


@contextmanager
def get_db():
    """获取数据库连接（上下文管理器，自动归还连接池）"""
    conn = _pool.connection()
    try:
        yield conn
    finally:
        conn.close()


# ==================== 密码工具 ====================

def hash_password(password: str) -> str:
    """哈希密码（使用 pbkdf2:sha256，兼容 Python 3.6）"""
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password_hash: str, password: str) -> bool:
    """验证密码"""
    return check_password_hash(password_hash, password)


def generate_invite_code() -> str:
    """生成 8 位随机邀请码"""
    return secrets.token_hex(4)


# ==================== 用户相关 ====================

def create_user(username: str, password: str, nickname: str = "") -> bool:
    """创建用户，成功返回 True，用户名重复返回 False"""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, password_hash, nickname) VALUES (%s, %s, %s)",
                (username, hash_password(password), nickname or username),
            )
            conn.commit()
            return True
        except pymysql.err.IntegrityError:
            return False


def verify_user(username: str, password: str) -> Optional[dict]:
    """验证登录，成功返回用户字典，失败返回 None"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, nickname, role, password_hash FROM users WHERE username=%s",
            (username,),
        )
        user = cur.fetchone()
        if user and verify_password(user["password_hash"], password):
            del user["password_hash"]
            return user
        return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, nickname, role FROM users WHERE id=%s", (user_id,))
        return cur.fetchone()


def update_nickname(user_id: int, nickname: str) -> bool:
    """更新昵称"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET nickname=%s WHERE id=%s", (nickname, user_id))
        conn.commit()
        return cur.rowcount > 0


def update_password(user_id: int, old_password: str, new_password: str) -> bool:
    """修改密码，返回是否成功（旧密码验证通过才更新）"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        if not user or not verify_password(user["password_hash"], old_password):
            return False
        cur.execute(
            "UPDATE users SET password_hash=%s WHERE id=%s",
            (hash_password(new_password), user_id),
        )
        conn.commit()
        return True


# ==================== 小组相关 ====================

def create_group(name: str, description: str, creator_id: int) -> dict:
    """创建小组，返回包含 invite_code 的字典"""
    with get_db() as conn:
        cur = conn.cursor()
        code = generate_invite_code()
        # 确保邀请码不重复（最多重试 10 次）
        for _ in range(10):
            cur.execute("SELECT id FROM `groups` WHERE invite_code=%s", (code,))
            if not cur.fetchone():
                break
            code = generate_invite_code()

        cur.execute(
            "INSERT INTO `groups` (name, description, creator_id, invite_code) VALUES (%s, %s, %s, %s)",
            (name, description, creator_id, code),
        )
        group_id = cur.lastrowid
        # 创建者自动加入
        cur.execute("INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)", (group_id, creator_id))
        conn.commit()
        return {"id": group_id, "invite_code": code}


def get_group_by_invite_code(code: str) -> Optional[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM `groups` WHERE invite_code=%s", (code,))
        return cur.fetchone()


def get_group_by_id(group_id: int) -> Optional[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT g.*, u.nickname AS creator_name FROM `groups` g "
            "JOIN users u ON g.creator_id = u.id WHERE g.id=%s",
            (group_id,),
        )
        return cur.fetchone()


def get_user_groups(user_id: int) -> List[dict]:
    """获取用户加入的所有小组"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT g.id, g.name, g.description, g.invite_code, g.creator_id, u.nickname AS creator_name, "
            "gm.joined_at "
            "FROM `groups` g "
            "JOIN group_members gm ON g.id = gm.group_id "
            "JOIN users u ON g.creator_id = u.id "
            "WHERE gm.user_id = %s "
            "ORDER BY gm.joined_at DESC",
            (user_id,),
        )
        return cur.fetchall()


def join_group(user_id: int, group_id: int) -> bool:
    """加入小组，已加入返回 False，成功返回 True"""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)", (group_id, user_id))
            conn.commit()
            return True
        except pymysql.err.IntegrityError:
            return False


def get_group_members(group_id: int) -> List[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT u.id, u.nickname, gm.joined_at FROM group_members gm "
            "JOIN users u ON gm.user_id = u.id WHERE gm.group_id=%s ORDER BY gm.joined_at",
            (group_id,),
        )
        return cur.fetchall()


def is_group_member(user_id: int, group_id: int) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, user_id))
        return cur.fetchone() is not None


def delete_group(group_id: int):
    """删除小组及所有相关数据（打卡记录、计时记录、留言、成员）"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM study_sessions WHERE group_id=%s", (group_id,))
        cur.execute("DELETE FROM check_records WHERE group_id=%s", (group_id,))
        cur.execute("DELETE FROM group_members WHERE group_id=%s", (group_id,))
        cur.execute("DELETE FROM `groups` WHERE id=%s", (group_id,))
        conn.commit()


# ==================== 打卡相关 ====================

def check_in(user_id: int, group_id: int) -> Optional[int]:
    """签到，返回记录 ID；如果已有未签退记录则返回 None。使用 SELECT FOR UPDATE 防止并发双击"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM check_records WHERE user_id=%s AND group_id=%s AND check_out_time IS NULL FOR UPDATE",
                    (user_id, group_id))
        if cur.fetchone():
            return None
        cur.execute("INSERT INTO check_records (user_id, group_id, check_in_time) VALUES (%s, %s, NOW())",
                    (user_id, group_id))
        conn.commit()
        return cur.lastrowid


def check_out(record_id: int, user_id: int) -> Optional[int]:
    """签退，返回学习时长(秒)；如果记录不属于该用户或已签退返回 None"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, check_in_time, check_out_time FROM check_records WHERE id=%s AND user_id=%s",
            (record_id, user_id),
        )
        record = cur.fetchone()
        if not record or record["check_out_time"] is not None:
            return None
        cur.execute(
            "UPDATE check_records SET check_out_time=NOW(), "
            "duration=TIMESTAMPDIFF(SECOND, check_in_time, NOW()) "
            "WHERE id=%s",
            (record_id,),
        )
        conn.commit()
        # 重新查询获取计算后的时长
        cur.execute("SELECT duration FROM check_records WHERE id=%s", (record_id,))
        return cur.fetchone()["duration"]


def get_active_checkin(user_id: int, group_id: int) -> Optional[dict]:
    """获取用户在某小组当前进行中的打卡记录"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT cr.id, cr.check_in_time FROM check_records cr "
            "WHERE cr.user_id=%s AND cr.group_id=%s AND cr.check_out_time IS NULL",
            (user_id, group_id),
        )
        return cur.fetchone()


def is_check_record_valid(check_record_id: int, user_id: int, group_id: int) -> bool:
    """校验 check_record_id 是否属于该 user 和 group，防止跨组伪造"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM check_records WHERE id=%s AND user_id=%s AND group_id=%s",
            (check_record_id, user_id, group_id),
        )
        return cur.fetchone() is not None


def get_user_group_records(user_id: int, group_id: int, limit: int = 20) -> List[dict]:
    """获取用户在某小组的打卡记录"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT cr.* FROM check_records cr "
            "WHERE cr.user_id=%s AND cr.group_id=%s "
            "ORDER BY cr.check_in_time DESC LIMIT %s",
            (user_id, group_id, limit),
        )
        return cur.fetchall()


# ==================== 排行榜相关 ====================

def get_ranking_by_duration(group_id: int, limit: int = 50) -> List[dict]:
    """按总学习时长排行"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT u.id, u.nickname, "
            "COALESCE(SUM(cr.duration), 0) AS total_duration, "
            "COUNT(DISTINCT DATE(cr.check_in_time)) AS total_days "
            "FROM group_members gm "
            "JOIN users u ON gm.user_id = u.id "
            "LEFT JOIN check_records cr ON cr.user_id = u.id AND cr.group_id = gm.group_id "
            "WHERE gm.group_id = %s "
            "GROUP BY u.id, u.nickname "
            "HAVING total_days > 0 "
            "ORDER BY total_duration DESC "
            "LIMIT %s",
            (group_id, limit),
        )
        return cur.fetchall()


def get_ranking_by_days(group_id: int, limit: int = 50) -> List[dict]:
    """按打卡天数排行"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT u.id, u.nickname, "
            "COALESCE(SUM(cr.duration), 0) AS total_duration, "
            "COUNT(DISTINCT DATE(cr.check_in_time)) AS total_days "
            "FROM group_members gm "
            "JOIN users u ON gm.user_id = u.id "
            "LEFT JOIN check_records cr ON cr.user_id = u.id AND cr.group_id = gm.group_id "
            "WHERE gm.group_id = %s "
            "GROUP BY u.id, u.nickname "
            "HAVING total_days > 0 "
            "ORDER BY total_days DESC "
            "LIMIT %s",
            (group_id, limit),
        )
        return cur.fetchall()


def get_ranking_by_consecutive_days(group_id: int, limit: int = 50) -> List[dict]:
    """按连续打卡天数排行（在 Python 端计算，SQL 先取打卡日期）"""
    with get_db() as conn:
        cur = conn.cursor()
        # 设置 GROUP_CONCAT 最大长度，避免日期列表被截断
        cur.execute("SET SESSION group_concat_max_len = 100000")
        # 先获取所有人的打卡日期
        cur.execute(
            "SELECT u.id, u.nickname, "
            "COALESCE(SUM(cr.duration), 0) AS total_duration, "
            "GROUP_CONCAT(DISTINCT DATE(cr.check_in_time) ORDER BY DATE(cr.check_in_time) DESC SEPARATOR ',') AS dates "
            "FROM group_members gm "
            "JOIN users u ON gm.user_id = u.id "
            "LEFT JOIN check_records cr ON cr.user_id = u.id AND cr.group_id = gm.group_id "
            "WHERE gm.group_id = %s "
            "GROUP BY u.id, u.nickname",
            (group_id,),
        )
        rows = cur.fetchall()

    # Python 端计算连续打卡天数
    from datetime import date, timedelta, datetime

    result = []
    for row in rows:
        row["consecutive_days"] = 0
        if row["dates"]:
            date_list = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in row["dates"].split(",")], reverse=True)
            today = date.today()
            # 从今天开始往前数连续天数
            consecutive = 0
            expected = today
            for d in date_list:
                if d == expected:
                    consecutive += 1
                    expected = d - timedelta(days=1)
                elif d < expected:
                    break
            row["consecutive_days"] = consecutive
        result.append(row)

    # 过滤未打卡的成员
    result = [r for r in result if r["consecutive_days"] > 0]
    result.sort(key=lambda x: x["consecutive_days"], reverse=True)
    return result[:limit]


# ==================== 个人倒计时 ====================

def get_countdown(user_id: int) -> Optional[dict]:
    """获取用户的倒计时目标"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title, target_date FROM countdowns WHERE user_id=%s", (user_id,))
        return cur.fetchone()


def save_countdown(user_id: int, title: str, target_date: str) -> bool:
    """创建或更新倒计时（upsert），返回 True"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO countdowns (user_id, title, target_date) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE title=%s, target_date=%s",
            (user_id, title, target_date, title, target_date),
        )
        conn.commit()
        return True


def delete_countdown(user_id: int):
    """删除倒计时"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM countdowns WHERE user_id=%s", (user_id,))
        conn.commit()


# ==================== 学习内容计时 ====================

def start_session(user_id: int, group_id: int, check_record_id: int, title: str) -> Optional[Tuple[int, str]]:
    """创建学习内容，返回 (session_id, device_token)，每次打卡只能同时有一个进行中的任务"""
    with get_db() as conn:
        cur = conn.cursor()
        # 检查是否已有进行中的任务
        cur.execute(
            "SELECT id FROM study_sessions "
            "WHERE check_record_id=%s AND user_id=%s AND status IN ('running','paused')",
            (check_record_id, user_id),
        )
        if cur.fetchone():
            return None  # 已有进行中的任务
        token = secrets.token_hex(16)
        cur.execute(
            "INSERT INTO study_sessions (user_id, group_id, check_record_id, title, start_time, device_token) "
            "VALUES (%s, %s, %s, %s, NOW(), %s)",
            (user_id, group_id, check_record_id, title, token),
        )
        conn.commit()
        return (cur.lastrowid, token)


def pause_session(session_id: int, user_id: int, device_token: str = None):
    """暂停计时，服务端计算已过秒数。token 不匹配返回 None"""
    with get_db() as conn:
        cur = conn.cursor()
        if device_token:
            cur.execute("SELECT device_token FROM study_sessions WHERE id=%s", (session_id,))
            row = cur.fetchone()
            if row and row["device_token"] and row["device_token"] != device_token:
                return None  # token 不匹配，其他设备在操作
        cur.execute(
            "UPDATE study_sessions SET status='paused', "
            "duration = COALESCE(duration, 0) + TIMESTAMPDIFF(SECOND, start_time, NOW()), "
            "start_time = NULL "
            "WHERE id=%s AND user_id=%s AND status='running'",
            (session_id, user_id),
        )
        conn.commit()
        cur.execute("SELECT duration FROM study_sessions WHERE id=%s", (session_id,))
        row = cur.fetchone()
        return row["duration"] if row else 0


def resume_session(session_id: int, user_id: int, device_token: str = None):
    """恢复计时。token 不匹配返回 False"""
    with get_db() as conn:
        cur = conn.cursor()
        if device_token:
            cur.execute("SELECT device_token FROM study_sessions WHERE id=%s", (session_id,))
            row = cur.fetchone()
            if row and row["device_token"] and row["device_token"] != device_token:
                return False
        cur.execute(
            "UPDATE study_sessions SET status='running', start_time=NOW() "
            "WHERE id=%s AND user_id=%s AND status='paused'",
            (session_id, user_id),
        )
        conn.commit()
        return True


def complete_session(session_id: int, user_id: int, device_token: str = None):
    """结束计时，服务端计算总时长。token 不匹配返回 None。支持 running 和 paused 状态"""
    with get_db() as conn:
        cur = conn.cursor()
        if device_token:
            cur.execute("SELECT device_token FROM study_sessions WHERE id=%s", (session_id,))
            row = cur.fetchone()
            if row and row["device_token"] and row["device_token"] != device_token:
                return None
        # 先尝试 running 状态（需计算增量时长）
        cur.execute(
            "UPDATE study_sessions SET status='completed', end_time=NOW(), "
            "duration = COALESCE(duration, 0) + TIMESTAMPDIFF(SECOND, start_time, NOW()) "
            "WHERE id=%s AND user_id=%s AND status='running'",
            (session_id, user_id),
        )
        if cur.rowcount == 0:
            # 不是 running，尝试 paused 状态（duration 已在暂停时存好）
            cur.execute(
                "UPDATE study_sessions SET status='completed', end_time=NOW() "
                "WHERE id=%s AND user_id=%s AND status='paused'",
                (session_id, user_id),
            )
        conn.commit()
        cur.execute("SELECT duration FROM study_sessions WHERE id=%s", (session_id,))
        row = cur.fetchone()
        return row["duration"] if row else 0


def complete_all_sessions(check_record_id: int, user_id: int):
    """签退时结束所有进行中的计时"""
    with get_db() as conn:
        cur = conn.cursor()
        # 结束 running 状态的（计算时长）
        cur.execute(
            "UPDATE study_sessions SET status='completed', end_time=NOW(), "
            "duration = COALESCE(duration, 0) + TIMESTAMPDIFF(SECOND, start_time, NOW()) "
            "WHERE check_record_id=%s AND user_id=%s AND status='running'",
            (check_record_id, user_id),
        )
        # 结束 paused 状态的（保持已有 duration）
        cur.execute(
            "UPDATE study_sessions SET status='completed', end_time=NOW() "
            "WHERE check_record_id=%s AND user_id=%s AND status='paused'",
            (check_record_id, user_id),
        )
        conn.commit()


def get_active_sessions(check_record_id: int, user_id: int) -> List[dict]:
    """获取某次签到下进行中的学习内容"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, duration, status, UNIX_TIMESTAMP(start_time) AS start_ts FROM study_sessions "
            "WHERE check_record_id=%s AND user_id=%s AND status IN ('running','paused')",
            (check_record_id, user_id),
        )
        return cur.fetchall()


def get_sync_sessions(check_record_id: int, user_id: int) -> List[dict]:
    """获取同步所需的所有 session：活跃的 + 最近 5 秒内完成的"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, duration, status, UNIX_TIMESTAMP(start_time) AS start_ts FROM study_sessions "
            "WHERE check_record_id=%s AND user_id=%s "
            "AND (status IN ('running','paused') "
            "OR (status='completed' AND end_time > DATE_SUB(NOW(), INTERVAL 5 SECOND)))",
            (check_record_id, user_id),
        )
        return cur.fetchall()


def get_report_data(user_id: int, period: str) -> List[dict]:
    """获取报告数据：按时间周期汇总各学习内容时长
    period: 'day' | 'week' | 'month' | 'year' """
    period_sql = {
        "day": "DATE(end_time) = CURDATE()",
        "week": "YEARWEEK(end_time, 1) = YEARWEEK(CURDATE(), 1)",
        "month": "DATE_FORMAT(end_time, '%%Y-%%m') = DATE_FORMAT(CURDATE(), '%%Y-%%m')",
        "year": "YEAR(end_time) = YEAR(CURDATE())",
    }
    if period not in period_sql:
        period = "day"
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT title, SUM(duration) AS total_seconds FROM study_sessions "
            "WHERE user_id=%s AND status='completed' AND " + period_sql[period] +
            " GROUP BY title ORDER BY total_seconds DESC",
            (user_id,),
        )
        return cur.fetchall()


# ==================== 每日学习目标 ====================

def get_daily_goal(user_id: int) -> int:
    """获取每日学习目标(秒)，默认7200(2小时)"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT daily_goal FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        return row["daily_goal"] if row else 7200


def set_daily_goal(user_id: int, seconds: int):
    """设置每日学习目标(秒)"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET daily_goal=%s WHERE id=%s", (seconds, user_id))
        conn.commit()


def get_today_total_seconds(user_id: int) -> int:
    """获取今日已完成的学习总时长(秒)"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(duration), 0) AS total FROM study_sessions "
            "WHERE user_id=%s AND status='completed' AND DATE(end_time) = CURDATE()",
            (user_id,),
        )
        row = cur.fetchone()
        return row["total"] if row else 0


# ==================== 打卡日历 ====================

def get_group_monthly_checkins(group_id: int, year: int, month: int) -> dict:
    """获取小组某月每天的打卡成员列表，返回 {day: [{user_id, nickname}, ...]}"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT DATE(cr.check_in_time) AS day, u.id AS user_id, u.nickname "
            "FROM check_records cr "
            "JOIN users u ON cr.user_id = u.id "
            "WHERE cr.group_id=%s "
            "AND YEAR(cr.check_in_time)=%s AND MONTH(cr.check_in_time)=%s "
            "ORDER BY day, u.nickname",
            (group_id, year, month),
        )
        rows = cur.fetchall()
        result = {}
        for row in rows:
            day = row["day"].day
            if day not in result:
                result[day] = []
            result[day].append({"user_id": row["user_id"], "nickname": row["nickname"]})
        return result


# ==================== 学习风格标签 ====================

def _determine_tag(total: int, consecutive: int, avg_hour: int, avg_dur: int, weekend_ratio: float, night_ratio: float, total_cnt: int) -> str:
    """标签判定逻辑（纯函数，可复用）"""
    if total < 3600:
        return "初出茅庐"
    if consecutive >= 30:
        return "全勤标兵"
    if consecutive >= 14:
        if avg_hour < 8:
            return "清晨追光者"
        if avg_hour >= 22:
            return "深夜孤勇者"
        return "稳定打卡人"
    if avg_hour < 7:
        return "清晨追光者"
    if avg_hour >= 23:
        return "修仙者"
    if night_ratio > 0.5:
        return "深夜孤勇者"
    if avg_dur > 7200:
        if weekend_ratio > 0.5:
            return "周末突击兵"
        return "沉浸式学霸"
    if weekend_ratio > 0.6:
        return "周末突击兵"
    if avg_dur < 1800 and total_cnt >= 10:
        return "碎片化战神"
    if total > 36000:
        if consecutive >= 7:
            return "卷王"
        return "时间管理大师"
    if avg_dur < 1800:
        return "闪电侠"
    if consecutive >= 7:
        return "稳定打卡人"
    return "佛系学者"


def get_user_style_tags_batch(user_ids: List[int]) -> Dict[int, str]:
    """批量计算风格标签，避免 N+1 查询。返回 {user_id: tag}"""
    from datetime import date, timedelta

    if not user_ids:
        return {}

    result = {}
    today = date.today()
    placeholders = ','.join(['%s'] * len(user_ids))

    with get_db() as conn:
        cur = conn.cursor()

        # 1. 批量总时长
        cur.execute(
            f"SELECT user_id, COALESCE(SUM(duration), 0) AS total FROM study_sessions "
            f"WHERE user_id IN ({placeholders}) AND status='completed' GROUP BY user_id",
            tuple(user_ids),
        )
        total_map = {row["user_id"]: row["total"] for row in cur.fetchall()}

        # 2. 批量连续打卡天数
        cur.execute(
            f"SELECT user_id, DATE(check_in_time) AS d FROM check_records "
            f"WHERE user_id IN ({placeholders}) GROUP BY user_id, d ORDER BY user_id, d DESC",
            tuple(user_ids),
        )
        user_dates = {}
        for row in cur.fetchall():
            user_dates.setdefault(row["user_id"], []).append(row["d"])
        consecutive_map = {}
        for uid, dates in user_dates.items():
            consecutive = 0
            for d in dates:
                if d == today - timedelta(days=consecutive):
                    consecutive += 1
                else:
                    break
            consecutive_map[uid] = consecutive

        # 3. 批量平均开始时间
        cur.execute(
            f"SELECT user_id, AVG(HOUR(check_in_time)) AS avg_hour FROM check_records "
            f"WHERE user_id IN ({placeholders}) GROUP BY user_id",
            tuple(user_ids),
        )
        avg_hour_map = {row["user_id"]: int(row["avg_hour"]) if row["avg_hour"] is not None else 12
                        for row in cur.fetchall()}

        # 4. 批量平均时长
        cur.execute(
            f"SELECT user_id, AVG(duration) AS avg_dur FROM study_sessions "
            f"WHERE user_id IN ({placeholders}) AND status='completed' GROUP BY user_id",
            tuple(user_ids),
        )
        avg_dur_map = {row["user_id"]: int(row["avg_dur"]) if row["avg_dur"] is not None else 0
                       for row in cur.fetchall()}

        # 5. 批量周末占比
        cur.execute(
            f"SELECT user_id, COUNT(*) AS cnt FROM study_sessions "
            f"WHERE user_id IN ({placeholders}) AND status='completed' AND DAYOFWEEK(end_time) IN (1,7) "
            f"GROUP BY user_id",
            tuple(user_ids),
        )
        weekend_map = {row["user_id"]: row["cnt"] for row in cur.fetchall()}

        # 6. 批量深夜占比 + 总次数
        cur.execute(
            f"SELECT user_id, COUNT(*) AS cnt FROM study_sessions "
            f"WHERE user_id IN ({placeholders}) AND status='completed' AND HOUR(end_time) >= 22 "
            f"GROUP BY user_id",
            tuple(user_ids),
        )
        night_map = {row["user_id"]: row["cnt"] for row in cur.fetchall()}

        cur.execute(
            f"SELECT user_id, COUNT(*) AS cnt FROM study_sessions "
            f"WHERE user_id IN ({placeholders}) AND status='completed' GROUP BY user_id",
            tuple(user_ids),
        )
        total_cnt_map = {row["user_id"]: row["cnt"] for row in cur.fetchall()}

    for uid in user_ids:
        total = total_map.get(uid, 0)
        consecutive = consecutive_map.get(uid, 0)
        avg_hour = avg_hour_map.get(uid, 12)
        avg_dur = avg_dur_map.get(uid, 0)
        total_cnt = total_cnt_map.get(uid, 0)
        weekend_cnt = weekend_map.get(uid, 0)
        night_cnt = night_map.get(uid, 0)
        weekend_ratio = weekend_cnt / total_cnt if total_cnt > 0 else 0
        night_ratio = night_cnt / total_cnt if total_cnt > 0 else 0

        result[uid] = _determine_tag(total, consecutive, avg_hour, avg_dur, weekend_ratio, night_ratio, total_cnt)

    return result


def get_user_style_tag(user_id: int) -> str:
    """根据学习数据自动生成趣味风格标签（单个用户，委托批量函数）"""
    tags = get_user_style_tags_batch([user_id])
    return tags.get(user_id, "佛系学者")