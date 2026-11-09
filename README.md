# 校园失物招领系统 · B 子系统 v0 原型

软件工程课程大作业。「0-架构设计前」阶段的可运行前后端原型：只覆盖 B 子系统（信息发布与浏览）
的职责 —— 基础字典、信息发布与图片、浏览检索、详情、状态管理。

A / C 子系统（注册登录、认领流程与站内消息、审核/举报）不在本仓库范围内，所有未就绪部分
通过 `backend/integration/` 适配层隔离，缺什么在 `backend/README.md` 第 7、8 节写明。

## 目录

| 目录 | 说明 | 技术栈 |
| --- | --- | --- |
| `backend/` | 基础字典、信息发布与图片、浏览检索、详情、状态管理 | Python 3.13 · Django 5.2 · DRF · SQLite |
| `frontend/` | 列表 / 详情 / 编辑界面 | Vue 3 · Vite · vue-router |

## 本地运行

```powershell
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver

# 前端（另开一个终端）
cd frontend
npm install
npm run dev
```

`backend/var/`（SQLite 数据库、私有图片）与 `.venv/`、`node_modules/` 均已在 `.gitignore` 中排除，
首次运行会自动创建。

## 更多文档

- 后端设计、接口清单与环境说明：[`backend/README.md`](backend/README.md)
- 前端结构、跨域与代理配置：[`frontend/README.md`](frontend/README.md)
