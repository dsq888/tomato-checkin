"""学习打卡系统 - Flask 主应用"""

import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect
import models
from config import SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

# CSRF 保护
csrf = CSRFProtect(app)

# Session 安全配置
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=86400 * 365,  # 365 天，关闭浏览器不丢失
)

# 反向代理修复：让 Flask 知道原始请求是 HTTPS（Nginx 必备）
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config["PREFERRED_URL_SCHEME"] = "https"

# 日志配置
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    handler = RotatingFileHandler("app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

# ==================== 装饰器 ====================

def login_required(f):
    """登录校验装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """管理员权限校验装饰器"""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            return "权限不足", 403
        return f(*args, **kwargs)
    return decorated


# ==================== 工具函数 ====================

def format_duration(seconds: int) -> str:
    """格式化秒数为 时:分:秒"""
    if not seconds:
        return "0分"
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    if h > 0:
        return f"{h}小时{m}分"
    return f"{m}分{s}秒"


# 注册模板过滤器
app.jinja_env.filters["format_duration"] = format_duration


@app.template_filter("format_time")
def format_time_filter(seconds: int) -> str:
    """格式化秒数为 HH:MM:SS"""
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ==================== 认证路由 ====================

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        nickname = request.form.get("nickname", "").strip()
        if not username or not password:
            return render_template("register.html", error="用户名和密码不能为空")
        if len(password) < 6:
            return render_template("register.html", error="密码至少6位")
        if models.create_user(username, password, nickname):
            return redirect(url_for("login", msg="注册成功，请登录"))
        return render_template("register.html", error="用户名已存在")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = models.verify_user(username, password)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["nickname"] = user["nickname"]
            session["role"] = user["role"]
            # 记住我：session 持久化，关闭浏览器也不丢失
            session.permanent = True
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="用户名或密码错误")
    return render_template("login.html", msg=request.args.get("msg", ""))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==================== 仪表盘 ====================

@app.route("/dashboard")
@login_required
def dashboard():
    my_groups = models.get_user_groups(session["user_id"])
    countdown = models.get_countdown(session["user_id"])
    days_left = 0
    if countdown:
        from datetime import date
        delta = countdown["target_date"] - date.today()
        days_left = delta.days
    return render_template("dashboard.html", groups=my_groups, countdown=countdown, days_left=days_left)


# ==================== 个人设置 ====================

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.route("/settings/nickname", methods=["POST"])
@login_required
def update_nickname():
    nickname = request.form.get("nickname", "").strip()
    if nickname:
        models.update_nickname(session["user_id"], nickname)
        session["nickname"] = nickname
    return redirect(url_for("settings"))


@app.route("/settings/password", methods=["POST"])
@login_required
def update_password():
    old_pw = request.form.get("old_password", "")
    new_pw = request.form.get("new_password", "")
    if len(new_pw) < 6:
        return render_template("settings.html", pw_error="新密码至少6位")
    if models.update_password(session["user_id"], old_pw, new_pw):
        return redirect(url_for("settings"))
    return render_template("settings.html", pw_error="旧密码不正确")


# ==================== 倒计时目标设置 ====================

@app.route("/countdown/settings")
@login_required
def countdown_settings():
    countdown = models.get_countdown(session["user_id"])
    return render_template("countdown_settings.html", countdown=countdown)


@app.route("/countdown/save", methods=["POST"])
@login_required
def save_countdown():
    title = request.form.get("title", "").strip()
    target_date = request.form.get("target_date", "").strip()
    if title and target_date:
        models.save_countdown(session["user_id"], title, target_date)
    return redirect(url_for("dashboard"))


@app.route("/countdown/delete", methods=["POST"])
@login_required
def delete_countdown():
    models.delete_countdown(session["user_id"])
    return redirect(url_for("dashboard"))


# ==================== 小组路由 ====================

@app.route("/groups")
@login_required
def group_list():
    my_groups = models.get_user_groups(session["user_id"])
    return render_template("group_list.html", groups=my_groups)


@app.route("/groups/create", methods=["GET", "POST"])
@admin_required
def create_group():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        if not name:
            return render_template("group_create.html", error="小组名称不能为空")
        group = models.create_group(name, desc, session["user_id"])
        return redirect(url_for("group_detail", group_id=group["id"]))
    return render_template("group_create.html")


@app.route("/groups/join", methods=["GET", "POST"])
@login_required
def join_group():
    if request.method == "POST":
        code = request.form.get("invite_code", "").strip()
        group = models.get_group_by_invite_code(code)
        if not group:
            return render_template("join_group.html", error="邀请码无效")
        if models.join_group(session["user_id"], group["id"]):
            return redirect(url_for("group_detail", group_id=group["id"]))
        return render_template("join_group.html", error="你已在该小组中")
    return render_template("join_group.html")


@app.route("/groups/<int:group_id>/delete", methods=["POST"])
@admin_required
def delete_group(group_id):
    models.delete_group(group_id)
    return redirect(url_for("group_list"))


@app.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    if not models.is_group_member(session["user_id"], group_id):
        return "你不在该小组中", 403
    group = models.get_group_by_id(group_id)
    members = models.get_group_members(group_id)
    active_checkin = models.get_active_checkin(session["user_id"], group_id)
    records = models.get_user_group_records(session["user_id"], group_id)
    active_sessions = []
    if active_checkin:
        active_sessions = models.get_active_sessions(active_checkin["id"], session["user_id"])
    daily_goal = models.get_daily_goal(session["user_id"])
    # 批量计算成员风格标签（避免 N+1 查询）
    member_tags = models.get_user_style_tags_batch([m["id"] for m in members])
    return render_template(
        "group_detail.html",
        group=group,
        members=members,
        active_checkin=active_checkin,
        active_sessions=active_sessions,
        records=records,
        daily_goal=daily_goal,
        member_tags=member_tags,
        is_admin=(session.get("role") == "admin"),
    )


# ==================== 打卡路由 ====================

@app.route("/checkin/<int:group_id>", methods=["POST"])
@login_required
def checkin(group_id):
    """签到：直接打卡，无需定位"""
    if not models.is_group_member(session["user_id"], group_id):
        return jsonify({"ok": False, "msg": "你不在该小组中"})

    active = models.get_active_checkin(session["user_id"], group_id)
    if active:
        return jsonify({"ok": False, "msg": "你还有未签退的打卡记录"})

    record_id = models.check_in(session["user_id"], group_id)
    if record_id:
        return jsonify({"ok": True, "msg": "打卡成功！", "record_id": record_id})
    return jsonify({"ok": False, "msg": "打卡失败，请重试"})


@app.route("/checkout/<int:record_id>", methods=["POST"])
@login_required
def checkout(record_id):
    """签退"""
    models.complete_all_sessions(record_id, session["user_id"])  # 结束所有计时
    duration = models.check_out(record_id, session["user_id"])
    if duration is not None:
        return jsonify({"ok": True, "msg": f"签退成功！本次学习 {format_duration(duration)}"})
    return jsonify({"ok": False, "msg": "签退失败，记录不存在或已签退"})


# ==================== 学习内容计时 API ====================

@app.route("/session/start", methods=["POST"])
@login_required
def start_session():
    group_id = request.form.get("group_id", type=int)
    check_record_id = request.form.get("check_record_id", type=int)
    title = request.form.get("title", "").strip()
    if not title:
        return jsonify({"ok": False, "msg": "请输入学习内容"})
    # 校验 check_record_id 属于该 group_id 和当前用户
    if not models.is_check_record_valid(check_record_id, session["user_id"], group_id):
        return jsonify({"ok": False, "msg": "打卡记录校验失败"})
    result = models.start_session(session["user_id"], group_id, check_record_id, title)
    if result is None:
        return jsonify({"ok": False, "msg": "已有进行中的学习任务，请先结束当前任务"})
    sid, token = result
    return jsonify({"ok": True, "session_id": sid, "device_token": token, "title": title})


@app.route("/session/<int:session_id>/pause", methods=["POST"])
@login_required
def pause_session(session_id):
    token = request.form.get("device_token", "")
    duration = models.pause_session(session_id, session["user_id"], token)
    if duration is None:
        return jsonify({"ok": False, "msg": "该计时任务已在其他设备操作中"})
    return jsonify({"ok": True, "duration": duration})


@app.route("/session/<int:session_id>/resume", methods=["POST"])
@login_required
def resume_session_route(session_id):
    token = request.form.get("device_token", "")
    ok = models.resume_session(session_id, session["user_id"], token)
    if ok is False:
        return jsonify({"ok": False, "msg": "该计时任务已在其他设备操作中"})
    return jsonify({"ok": True})


@app.route("/session/<int:session_id>/complete", methods=["POST"])
@login_required
def complete_session_route(session_id):
    token = request.form.get("device_token", "")
    duration = models.complete_session(session_id, session["user_id"], token)
    if duration is None:
        return jsonify({"ok": False, "msg": "该计时任务已在其他设备操作中"})
    return jsonify({"ok": True, "duration": duration})


@app.route("/session/sync/<int:check_record_id>", methods=["GET"])
@login_required
def sync_sessions(check_record_id):
    sessions = models.get_sync_sessions(check_record_id, session["user_id"])
    return jsonify({"ok": True, "sessions": sessions})


# ==================== 学习报告 ====================

@app.route("/report")
@login_required
def report():
    period = request.args.get("period", "day")
    data = models.get_report_data(session["user_id"], period)
    return render_template("report.html", data=data, period=period)


# ==================== 每日学习目标 API ====================

@app.route("/api/daily_goal", methods=["GET", "POST"])
@login_required
def daily_goal():
    if request.method == "POST":
        seconds = request.form.get("seconds", type=int, default=7200)
        if seconds < 300:
            return jsonify({"ok": False, "msg": "目标至少5分钟"})
        models.set_daily_goal(session["user_id"], seconds)
        return jsonify({"ok": True, "goal": seconds})
    goal = models.get_daily_goal(session["user_id"])
    today = models.get_today_total_seconds(session["user_id"])
    return jsonify({"ok": True, "goal": goal, "today": today})


@app.route("/api/today_progress")
@login_required
@csrf.exempt
def today_progress():
    """获取今日学习进度（含进行中的计时估算）"""
    today = models.get_today_total_seconds(session["user_id"])
    goal = models.get_daily_goal(session["user_id"])
    # 加上当前进行中的计时估算
    from datetime import datetime
    with models.get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(duration), 0) AS dur FROM study_sessions "
            "WHERE user_id=%s AND status='paused' AND DATE(COALESCE(end_time, created_at)) = CURDATE()",
            (session["user_id"],),
        )
        paused_dur = cur.fetchone()["dur"]
        cur.execute(
            "SELECT COALESCE(SUM(TIMESTAMPDIFF(SECOND, start_time, NOW())), 0) AS dur FROM study_sessions "
            "WHERE user_id=%s AND status='running'",
            (session["user_id"],),
        )
        running_dur = cur.fetchone()["dur"]
    active = today + paused_dur + running_dur
    return jsonify({"ok": True, "goal": goal, "today": today, "active": active})


# ==================== 打卡日历 API ====================

@app.route("/api/group/<int:group_id>/calendar")
@login_required
def group_calendar(group_id):
    if not models.is_group_member(session["user_id"], group_id):
        return jsonify({"ok": False, "msg": "你不在该小组中"})
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    from datetime import datetime
    now = datetime.now()
    if not year:
        year = now.year
    if not month:
        month = now.month
    data = models.get_group_monthly_checkins(group_id, year, month)
    return jsonify({"ok": True, "year": year, "month": month, "data": data})


# ==================== 风格标签 API ====================

@app.route("/api/user/<int:user_id>/style_tag")
@login_required
def user_style_tag(user_id):
    tag = models.get_user_style_tag(user_id)
    return jsonify({"ok": True, "tag": tag})


# ==================== 排行榜路由 ====================

@app.route("/ranking/<int:group_id>")
@login_required
def ranking(group_id):
    if not models.is_group_member(session["user_id"], group_id):
        return "你不在该小组中", 403
    metric = request.args.get("metric", "duration")  # duration | days | consecutive
    group = models.get_group_by_id(group_id)

    if metric == "days":
        data = models.get_ranking_by_days(group_id)
    elif metric == "consecutive":
        data = models.get_ranking_by_consecutive_days(group_id)
    else:
        data = models.get_ranking_by_duration(group_id)

    # 批量计算风格标签（避免 N+1 查询）
    tags = models.get_user_style_tags_batch([row["id"] for row in data])
    for row in data:
        row["style_tag"] = tags.get(row["id"], "")

    return render_template("ranking.html", group=group, data=data, metric=metric)


# ==================== 错误处理 ====================

@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, msg="请求参数有误"), 400


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, msg="权限不足"), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, msg="页面不存在"), 404


@app.errorhandler(500)
def server_error(e):
    import traceback
    app.logger.error(f"500 错误: {traceback.format_exc()}")
    return f"500 Internal Server Error: {str(e.original_exception) if hasattr(e, 'original_exception') else str(e)}", 500


# ==================== 启动 ====================

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    if debug:
        print("⚠️ 调试模式已开启")
    print("请确保：")
    print("1. MySQL 已启动")
    print("2. 已创建数据库: CREATE DATABASE study_checkin CHARACTER SET utf8mb4;")
    print("3. 已导入表结构: python init_db.py")
    print("4. 已设置环境变量 DB_PASSWORD（数据库密码）")
    app.run(debug=debug, host="0.0.0.0", port=5000)