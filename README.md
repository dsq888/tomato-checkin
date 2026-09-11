# 🍅 番茄学习打卡系统

> 基于 Flask + MySQL 的小组学习打卡系统，支持签到签退、学习内容正计时、多维度排行榜和数据可视化报告。

> 🌐 **在线体验**：[http://47.112.27.236](http://47.112.27.236)（支持注册登录，欢迎试用！）
>
> 🔑 **体验邀请码**：`60391ca3`（注册后用此邀请码加入体验小组）

## ✨ 功能特性

### 用户系统
- 注册 / 登录 / 修改昵称和密码
- 基于 Session 的身份认证
- CSRF 安全保护

### 小组管理
- **所有注册用户**均可创建小组并生成邀请码
- 普通用户通过邀请码加入小组，一人可加入多个小组
- 管理员可删除小组（级联删除成员关系和打卡记录）

### 打卡功能
- 随时随地签到 / 签退，无需 GPS 定位
- 签到后可添加自定义学习内容（如"高数"、"英语"）
- 每个学习内容独立正计时，支持**暂停 / 继续 / 结束**
- 计时器为全局悬浮窗，切换页面不中断，退出登录自动结束

### 数据报告
- 个人学习报告：**日报 / 周报 / 月报 / 年报**
- 使用 Chart.js 饼图展示各学习内容时长占比
- 每人数据独立隔离，互不可见

### 排行榜
- 小组间多维度竞争排名：
  - 📊 总学习时长
  - 📅 累计打卡天数
  - 🔥 连续打卡天数
- 自动过滤未打卡成员，零打卡不参与排名

### 其他
- 首页励志鸡汤 + 个人倒计时目标
- 番茄主题 UI，适配桌面端和移动端

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python + Flask |
| 数据库 | MySQL + PyMySQL + DBUtils 连接池 |
| 前端 | HTML / CSS / JavaScript / Chart.js |
| 安全 | Flask-WTF CSRF 保护、Werkzeug 密码哈希 |
| 部署 | Gunicorn + Nginx 反向代理 |

## 📁 项目结构

```
.
├── app.py                 # Flask 主应用（路由、视图函数）
├── models.py              # 数据库操作层（所有 SQL 封装）
├── config.py              # 配置文件（数据库、密钥，从环境变量读取）
├── init_db.py             # 数据库初始化脚本
├── init_db.sql            # 建表 SQL
├── requirements.txt       # Python 依赖
├── start.sh               # 部署启动脚本
├── static/
│   └── chart.min.js       # Chart.js 图表库
└── templates/
    ├── base.html          # 基础模板（导航栏、悬浮计时器、全局样式）
    ├── dashboard.html     # 首页（励志鸡汤、倒计时目标）
    ├── login.html          # 登录
    ├── register.html       # 注册
    ├── group_list.html     # 小组列表
    ├── group_create.html   # 创建小组
    ├── group_detail.html   # 小组详情（签到签退、打卡）
    ├── join_group.html     # 加入小组
    ├── ranking.html        # 排行榜
    ├── report.html         # 学习报告（饼图）
    ├── settings.html       # 个人设置
    ├── countdown_settings.html  # 倒计时设置
    └── error.html          # 错误页
```

## 🚀 快速开始

### 1. 环境准备

- Python 3.10+
- MySQL 8.0+

### 2. 克隆仓库

```bash
git clone https://github.com/dsq888/DSQ.git
cd DSQ
```

### 3. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=你的数据库密码
export DB_NAME=study_checkin
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

### 5. 初始化数据库

```bash
python init_db.py
```

> 默认管理员账号：`admin` / `admin123`（首次登录后请修改密码）

### 6. 启动服务

**开发环境：**

```bash
python app.py
```

**生产环境（Gunicorn + Nginx）：**

```bash
bash start.sh
```

访问 `http://localhost:5000` 即可使用。

## 📸 功能预览

| 页面 | 说明 |
|------|------|
| 首页 | 励志鸡汤 + 倒计时目标 |
| 小组详情 | 签到签退 + 悬浮计时器 |
| 排行榜 | 总时长 / 打卡天数 / 连续天数 |
| 学习报告 | 饼图展示各内容占比 |
| 个人设置 | 修改昵称、密码 |

## 🔒 安全说明

- 数据库密码和 SECRET_KEY 通过环境变量注入，不硬编码在代码中
- 用户密码使用 Werkzeug PBKDF2 哈希存储
- 全站 CSRF 保护
- Session 设置 HttpOnly + SameSite
- 生产环境通过 Nginx 反向代理 + HTTPS

## 📝 License

MIT License
