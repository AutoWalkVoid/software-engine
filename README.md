# 校园失物招领系统 · B 子系统（信息发布与浏览）

软件工程课程项目。本仓库是 **B 子系统**的独立可运行副本：负责基础字典、失物/招领信息发布与图片、
浏览检索、详情展示与状态生命周期，按《共同字段与接口约定》**v0.5** 实现，并按架构设计的阶段 3
完成了模块拆分（检索规格单点、字典门面、图片可见性单点、状态机 action 驱动）。

A（用户管理）与 C（失物认领）由队友负责。本仓库保留 A 的演示身份实现（`backend/identity`、
`backend/users`）用于自查，C 的认领接口用 `backend/integration/claims.py` 的桩代替，因此
**B 的所有流程都能独立跑通**。

## 目录

| 目录 | 说明 | 技术栈 |
| --- | --- | --- |
| `backend/` | 字典、发布、图片、检索、详情、状态机 | Python 3.13 · Django 5.2 · DRF |
| `frontend/` | 列表 / 详情 / 编辑界面（v0 原型） | Vue 3 · Vite · vue-router |

后端模块划分：

| 模块 | 职责 |
| --- | --- |
| `posts/models.py` | `Post` / `PostImage` / 三个字典模型 |
| `posts/constants.py` | 契约常量：状态、字段白名单、分页、错误码 |
| `posts/dictionary.py` | 校区 / 分类 / 地点的唯一读取门面 |
| `posts/query.py` | 列表检索：筛选、排序、分页（关键词字面包含、大小写敏感） |
| `posts/images.py` | 图片上传校验、可见性判定、内容响应、清理 |
| `posts/browse.py` | `PostSummary` / `PostDetail` 组装，发布者缺失时降级为"已注销用户" |
| `posts/views.py` | HTTP 薄壳：参数解析、权限、事务边界、响应 |
| `posts/services.py` | 给 C 的同进程服务（`get_post_for_claim` 等，要求调用方已开事务） |
| `workflow/transitions.py` | 状态机：`transit(post, action, actor, reason)` 单一入口 |

## 本地运行

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

默认使用 `backend/var/db.sqlite3`，不需要额外配置；要连 MySQL 8 时设
`DATABASE_URL=mysql://user:pass@127.0.0.1:3306/claim_dev`。

演示身份：`DEMO_MODE=1` 时可用 `POST /api/v1/demo/token`（`{"actor": "alice"}`）直接换取令牌，
内置 `alice` / `bob` / `finder` / `outsider` 四个演示账号（前三个已校园认证）。

前端（另开一个终端）：

```powershell
cd frontend
npm install
npm run dev
```

`.venv/`、`var/`、`node_modules/` 已在 `.gitignore` 中排除。

## 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/meta/campuses` | 校区列表（匿名） |
| GET | `/api/v1/meta/categories` | 分类列表（匿名，按 sort_order） |
| GET | `/api/v1/meta/locations?campus_id=` | 地点列表（匿名，可按校区过滤） |
| POST | `/api/v1/post-images` | 上传图片（登录，`file` + `alt_text` + `is_public`） |
| GET | `/api/v1/post-images/{id}/content` | 读取图片（按公开性与绑定状态控制） |
| GET | `/api/v1/posts` | 公开列表（筛选 / 搜索 / 排序 / 分页） |
| POST | `/api/v1/posts` | 发布信息（登录；招领需校园认证） |
| GET | `/api/v1/posts/{id}` | 详情（撤回信息仅本人可见） |
| PATCH | `/api/v1/posts/{id}` | 编辑（本人且状态为 open / withdrawn） |
| POST | `/api/v1/posts/{id}/withdraw` | 撤回 |
| POST | `/api/v1/posts/{id}/restore` | 恢复 |
| POST | `/api/v1/posts/{id}/resolve` | 失物自行办结（`resolve_note` 5～200 字） |
| POST | `/api/v1/posts/{id}/reopen` | 撤销完成 |
| GET | `/api/v1/health` | 健康检查 |

重复执行已达目标状态的操作返回 `409 STATE_CONFLICT`，不覆盖首次操作记录的时间。

## 与其他仓库的关系

- 本仓库是个人负责部分的独立副本，接口与团队整合仓库
  [hello318869/claim-subsystem](https://github.com/hello318869/claim-subsystem) 中的 `posts` 模块保持一致。
- `frontend/` 仍是架构设计前的 v0 原型，接的是同一套 `/api/v1` 接口；新版结构以后端为准。

## 更多文档

- 后端设计、字段规则与环境变量：[`backend/README.md`](backend/README.md)
- 前端结构、跨域与代理配置：[`frontend/README.md`](frontend/README.md)
