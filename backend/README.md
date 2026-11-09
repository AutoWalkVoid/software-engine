# B 子系统 v0 原型：信息发布与浏览（校园失物招领）

按《共同字段与接口约定-03》实现的后端可运行原型，只覆盖 B 的职责：
**基础字典、信息发布与图片、浏览检索、详情、状态管理**。

- 技术栈：Python 3.13.13 + Django 5.2.19 + DRF 3.18.3 + SQLite
- 位置：`代码迭代/0-架构设计前/backend/`
- 不实现（属于 A / C）：注册登录页面与逻辑、认领流程与站内消息、审核/举报、`GET /users/me/posts`
- 边界写法：A、C 未就绪的部分全部通过 `integration/` 适配，缺什么在本文第 7、8 节写明

---

## 1. 目录与文件说明

```
backend/
├── manage.py
├── requirements.txt
├── .gitignore
├── config/
│   ├── settings.py          # SQLite、私有图片目录、DRF 统一认证/异常处理、A/C 集成地址
│   ├── urls.py              # /api/v1/ 挂 catalog + posts 两组路由
│   ├── wsgi.py / asgi.py
├── common/
│   ├── responses.py         # 统一成功响应 {code,message,data}
│   ├── exceptions.py        # ApiError + 统一错误信封（字段级 errors、状态码→code 映射）
│   ├── views.py             # /api/v1 未匹配路径的 JSON 404 兜底
│   └── pagination.py        # page/page_size 解析（1～100）与切页
├── catalog/                 # E1 数据底座：三个字典
│   ├── models.py            # Campus / Category / Location
│   ├── views.py             # GET /meta/campuses|categories|locations
│   ├── urls.py
│   └── migrations/
│       ├── 0001_initial.py
│       └── 0002_seed.py     # 种子：1 校区 / 6 分类 / 5 地点（update_or_create 幂等）
├── posts/                   # E2/E3：信息、图片、检索、详情
│   ├── models.py            # Post / PostImage + 私有图片存储
│   ├── serializers.py       # 创建/编辑字段校验（长度、字典 ID、发生时间）
│   ├── presenters.py        # PostSummary / PostDetail / PostImageView 组装
│   ├── views.py             # 8 个 posts 路由 + 2 个图片路由的全部逻辑
│   ├── imagetype.py         # 真实解码校验 jpeg/png/webp（Pillow，失败退魔数）
│   ├── urls.py
│   ├── management/commands/cleanup_images.py  # 清理解绑超过 24h 的图片
│   └── migrations/0001_initial.py
├── workflow/                # E4：状态机
│   ├── models.py            # PostStatusHistory(from/to/actor/reason/at)
│   ├── transitions.py       # transit(post, to, actor, reason)：迁移矩阵 + 留痕
│   └── migrations/0001_initial.py
├── integration/             # 与 A / C 的边界（不是 HTTP 公开接口）
│   ├── auth.py              # Bearer 令牌 → 调 A_IDENTITY_URL → Actor(user_id, campus_verified)
│   ├── users.py             # UserSummary 出口（v0 读发布快照，A 提供批量接口后替换）
│   ├── claims.py            # 调 C：close_pending_claims / has_completed_claim
│   └── for_c.py             # 提供给 C 的三个函数 + 匹配候选计算
├── tests/
│   ├── support.py           # 测试基类：mock A 的令牌校验、临时媒体目录
│   ├── test_meta.py         # 5 条
│   ├── test_publish.py      # 12 条
│   ├── test_images.py       # 12 条（上传校验 + 可见性）
│   ├── test_list.py         # 12 条（关键词/筛选/排序/分页）
│   ├── test_edit.py         # 10 条（白名单、权限、图片替换）
│   ├── test_lifecycle.py    # 19 条（撤回/恢复/办结/回退/状态机/事务回滚）
│   └── test_integration.py  # 16 条（身份 401、UserSummary、给 C 的三个函数）
└── tools/bootstrap_deps.py  # 本机无 pip 时的 wheel 解压安装脚本（见第 2 节）
```

---

## 2. 运行方式与实测结果

### 2.1 环境准备

```powershell
D:\Python\Python313\python.exe -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

> **本机实际遇到的环境问题（如实记录）**：在这台机器上执行 `python -m venv .venv` 时
> `ensurepip` 失败（沙箱不允许 pip 写临时目录），`.venv` 内没有 pip；
> `python -m pip install --target ...` 也在解包 wheel 时报 `PermissionError`。
> 因此改用 `tools/bootstrap_deps.py`：直接从 PyPI 下载 wheel 并解压进
> `.venv\Lib\site-packages`。依赖版本与 `requirements.txt` 一致，`import django` 正常。
> 网络可用，所以依赖确实装上了，不是空壳。

### 2.2 实际命令与输出（2026-11-09 在本机执行）

```text
> .\.venv\Scripts\python.exe manage.py check
System check identified no issues (0 silenced).

> .\.venv\Scripts\python.exe manage.py makemigrations
No changes detected

> .\.venv\Scripts\python.exe manage.py migrate
Operations to perform:
  Apply all migrations: auth, catalog, contenttypes, posts, workflow
Running migrations:
  Applying contenttypes.0001_initial... OK
  ...
  Applying catalog.0001_initial... OK
  Applying catalog.0002_seed... OK
  Applying posts.0001_initial... OK
  Applying workflow.0001_initial... OK

> .\.venv\Scripts\python.exe manage.py test
Found 89 test(s).
System check identified no issues (0 silenced).
Ran 89 tests in 0.226s

OK
```

`auth` / `contenttypes` 是 Django 自带迁移，只为让 DRF 的匿名用户对象可用；B 不建用户表。

### 2.3 启动与联调

```powershell
# 只跑 B（此时登录接口一律 401，这是预期：B 不含用户体系）
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010

# 接上 A 的身份校验接口
$env:A_IDENTITY_URL = "http://127.0.0.1:8001/api/v1/users/me"
# 接上 C 的认领服务（不配置时撤回跳过远程关单，仅限本地开发，见第 9 节）
$env:C_BASE_URL = "http://127.0.0.1:8002"
```

本机做过一次真实 HTTP 冒烟（`runserver 127.0.0.1:8010`）：

```text
GET  /api/v1/meta/categories -> 200，返回 6 条（证件/电子产品/钥匙/书籍/衣物/其他）
GET  /api/v1/posts          -> 200，{"items":[],"page":1,"page_size":20,"total":0,"total_pages":0}
POST /api/v1/posts（无令牌） -> 401 {"code":"UNAUTHENTICATED","message":"请先登录","data":null,"errors":{}}
```

---

## 3. 接口表（全部带 `/api/v1` 前缀，路径不带结尾 `/`）

| # | 方法 | 路径 | 权限 | 关键规则 |
|---|---|---|---|---|
| 1 | GET | `/meta/campuses` | 匿名 | 不分页，按 ID 升序；`{id,name}` |
| 2 | GET | `/meta/categories` | 匿名 | 不分页，`sort_order ASC, id ASC`；`{id,name,sort_order}` |
| 3 | GET | `/meta/locations` | 匿名 | 可选 `campus_id`；不存在的校区 400（不是空结果）；`{id,campus_id,name,sort_order}` |
| 4 | POST | `/post-images` | 登录 | multipart：`file`、`alt_text`(5～100)、`is_public`(默认 true)；单张 ≤5 MiB→413；非 jpeg/png/webp→415；返回 `PostImageView`，201 |
| 5 | GET | `/post-images/{id}/content` | 见规则 | 未绑定：仅上传者；信息已撤回：仅发布者（其余 404）；已绑定且 `is_public=true`：匿名可读；`is_public=false`：需登录（匿名 401）。`FileResponse` + `Cache-Control: no-store`，不套 JSON 信封 |
| 6 | POST | `/posts` | 登录；`found` 需校园认证 | 字段见 5.2；`publisher_id` 服务端写入，客户端提交→400；`campus_id` 由地点推导；`handover_note` found 必填 1～200、lost 必须为空；`request_id` 同发布者幂等（第二次 200 返回原记录）；201 |
| 7 | GET | `/posts` | 匿名 | `keyword`≤50 字面包含标题/描述、不折叠大小写、`%`/`_` 普通字符；`category_id/campus_id/location_id` 精确且校验存在；`status` 只允许 open/in_handover/completed（withdrawn→400），默认 open+in_handover；`occurred_from/to` 均为闭区间；`sort=latest|occurred_latest`；`page`/`page_size`（默认 20，范围 1～100，越界 400）；返回 `{items,page,page_size,total,total_pages}` |
| 8 | GET | `/posts/{id}` | 匿名；撤回仅本人 | 撤回信息对他人 404（不暴露存在性）；返回 `PostDetail` |
| 9 | PATCH | `/posts/{id}` | 本人，且 open/withdrawn | 白名单 `title/category_id/description/location_id/location_detail/occurred_at/image_ids`；`post_type/status/publisher_id/campus_id/completed_at/request_id` → 400；空提交 400；交接中/已完成 → 409；`image_ids` 缺省不改、`[]` 清空、数组整体替换并按顺序重排 |
| 10 | POST | `/posts/{id}/withdraw` | 本人，open | open→withdrawn；同一事务调用 C 的 `close_pending_claims`，失败回滚（503）；重复撤回 409 |
| 11 | POST | `/posts/{id}/restore` | 本人，withdrawn | withdrawn→open；不恢复历史认领；重复恢复 409 |
| 12 | POST | `/posts/{id}/resolve` | 本人，lost/open | `resolve_note` 5～200 必填；→completed，写 `completed_at` 与操作人/时间；found 调用→409 |
| 13 | POST | `/posts/{id}/reopen` | 本人，completed | completed→open；C 报告存在 `completed` 认领记录时 409；清空 `completed_at` |

**关于“13 个接口”**：任务书列举的是 3（字典）+2（图片）+1（创建）+1（列表）+1（详情）+1（编辑）+3（撤回/恢复/办结）= 12 个；
契约 5.4 还要求 `reopen`（FR-12 的“错标可回退”，且有已完成认领时 409）。本实现把它作为第 13 个接口。
`GET /users/me/posts` 按契约由 A 直查 `Post` 表实现，B 不提供。

### 3.1 统一响应

成功：`{"code":"OK","message":"操作成功","data":{...}}`。
失败：`{"code":"...","message":"...","data":null,"errors":{"字段":["原因"]}}`，无字段错误时 `errors={}`。

| HTTP | code |
|---|---|
| 400 | `VALIDATION_ERROR` |
| 401 | `UNAUTHENTICATED` |
| 403 | `FORBIDDEN` / `IDENTITY_REQUIRED` |
| 404 | `NOT_FOUND` |
| 409 | `STATE_CONFLICT` / `DUPLICATE_RESOURCE` |
| 413 | `FILE_TOO_LARGE` |
| 415 | `UNSUPPORTED_MEDIA_TYPE` |
| 429 | `RATE_LIMITED`（异常处理器已映射，B 未主动配置限流） |
| 500 | `INTERNAL_ERROR` |
| 503 | `UPSTREAM_UNAVAILABLE`（契约外新增，仅用于 C 服务调用失败） |

`/api/v1/` 下未匹配的路径（含结尾斜杠、非数字 ID）由兜底视图返回同样的 JSON 404，
不会出现 Django 的 HTML 调试页。

---

## 4. 数据模型要点

| 表 | 关键字段 | 说明 |
|---|---|---|
| `catalog_campus` | `id`(PK,字符串), `name` | 种子 `campus_main/主校区` |
| `catalog_category` | `id`, `name`, `sort_order` | 6 条种子，`cat_document/cat_electronics/cat_keys/cat_books/cat_clothing/cat_other` |
| `catalog_location` | `id`, `campus_id`(FK,PROTECT), `name`, `sort_order` | 5 条种子：图书馆/教学楼/食堂/操场/宿舍楼，均属主校区 |
| `posts_post` | `publisher_id`, `post_type`, `title`, `description`, `category_id`, `location_id`, `campus_id`, `location_detail`, `occurred_at`, `handover_note`, `status`, `request_id`, `completed_at`, `created_at`, `updated_at` + 发布者快照 `publisher_nickname/publisher_is_campus_verified/publisher_verification_mode` | 约束：`(publisher_id, request_id)` 条件唯一（空 `request_id` 不参与）；索引 `(status,-created_at)`、`(category,location)` |
| `posts_postimage` | `owner_id`, `post_id`(可空,SET_NULL), `file`, `mime_type`, `size_bytes`, `sort_order`, `alt_text`, `is_public`, `created_at` | 文件落在 `var/media/post-images/<uuid>.<ext>`，不经静态 URL 暴露 |
| `workflow_poststatushistory` | `post_id`, `from_status`, `to_status`, `actor_id`, `reason`, `at` | 每次迁移一条，`resolve` 的说明存在 `reason` |

要点：

- 字典外键使用 `PROTECT`：已被使用的分类/地点不能删除（契约 3.4）。
- ID 对外统一字符串：`Post`/`PostImage` 用自增主键，序列化时 `str()`；字典用字符串主键。
- 时间统一 UTC 存储，响应 ISO 8601（`2026-10-07T02:00:00Z`）。
- 图片校验读实际字节并用 Pillow 解码（`Image.verify()`），扩展名不参与判断；
  Pillow 缺失时退回 PNG/JPEG/WebP 魔数校验并记日志。
- 解绑图片保留文件，`python manage.py cleanup_images [--hours 24] [--dry-run]` 才删除。

---

## 5. 状态机（`workflow.transit`）

```
open        -> withdrawn     撤回（B，本人）
withdrawn   -> open          恢复（B，本人）
open        -> in_handover   同意认领（C）
in_handover -> open          交接前取消（C）
in_handover -> completed     双方确认（C）
open        -> completed     自行找回（B，仅 lost）
completed   -> open          撤销完成（B，C 无已完成认领时）
```

- `transit(post, to_status, actor, reason)`：先校验矩阵，再改 `status`、维护 `completed_at`、
  写一条 `PostStatusHistory(from,to,actor,reason,at)`；**不 commit**，事务由调用方负责。
- 目标状态等于当前状态（重复操作）、跨状态跳跃、`found/open→completed` 一律 409 `STATE_CONFLICT`。
- `withdraw` 在事务内调用 C：`close_pending_claims(post_id, "post_withdrawn")`；C 报错则整体回滚。
- `reopen` 先问 C `has_completed_claim(post_id)`；为真则 409，不允许 B 单方改回 open。
- C 通过 `integration.for_c.set_handover_state(post_id, transition)` 驱动
  `reserve / complete / reopen`，只接受上表对应前态，非法前态 409。

---

## 6. 需要 A 提供什么

1. **身份校验接口**（B 的唯一登录来源）  
   环境变量 `A_IDENTITY_URL`，建议指向 A 的 `GET /api/v1/users/me`，携带同一个 Bearer 令牌。
   返回 `UserSelf`（直接返回或 `{code,message,data}` 包装均可），B 读取：
   `id`、`nickname`、`is_campus_verified`、`verification_mode`。
   401/403 → B 返回 401；网络错误/5xx → B 也返回 401 并写 `b.auth` 日志（不回退假用户）。
2. **批量用户摘要**（可选，提升一致性）  
   契约 7.3 的 `get_user_summaries(user_ids)` 目前 B 用“发布时快照”实现；
   A 若提供 `POST /internal/users/summaries`，替换 `integration/users.py` 的实现即可，
   `PostSummary.publisher` 字段结构不变。
3. **`GET /users/me/posts` 由 A 直接查 B 的 `posts_post` 表**（按 `publisher_id` 过滤，
   默认包含本人全部状态）。B 不实现该接口，也不额外提供“我的发布”。
4. 登录页、令牌签发/撤销、校园身份绑定界面与 `403 IDENTITY_REQUIRED` 的前端引导文案
   （“非校园用户不能发布招领，请将物品送至失物招领处”）。

## 7. 需要 C 提供什么

B 的撤回要关闭该信息下所有 `pending` 申请，`reopen` 要判断是否存在已完成认领。
两种落地方式任选：

- **同进程/同库（契约 7.3 推荐）**：把 `integration/claims.py` 改成直接调用 C 的 Python 函数；
- **独立服务（本原型默认）**：C 提供下面两个内部 HTTP 接口（路径是本原型约定，需 C 确认）：
  - `POST {C_BASE_URL}/api/v1/internal/claims/close-pending`  
    body：`{"post_id":"1","reason":"post_withdrawn","except_claim_id":null}`；返回 `{"closed":n}`
  - `GET {C_BASE_URL}/api/v1/internal/claims/has-completed?post_id=1`；返回 `{"has_completed_claim":true|false}`

失败时 B 返回 503 `UPSTREAM_UNAVAILABLE` 并回滚撤回（`posts_post.status` 保持 `open`，无历史记录）。

**B 提供给 C 的三个函数**（`integration/for_c.py`，Python 调用，不是 HTTP）：

| 函数 | 行为 |
|---|---|
| `get_post_for_claim(post_id, lock=False)` | 返回 `{post, post_id, publisher_id, publisher}`；`lock=True` 时 `select_for_update()` |
| `set_handover_state(post_id, transition, actor=None)` | 只接受 `reserve(open→in_handover)`、`complete(in_handover→completed)`、`reopen(in_handover→open)`；非法 transition 400、前态不符 409；内部用 `workflow.transit` 留痕 |
| `list_match_candidates(source_post, limit=None)` | 反类型、同校区、同类别、`open`、非本人、`found.occurred_at ∈ [lost.occurred_at, +30 天]`；打分 40/30/20/10，返回 `[{post, post_summary, score, reasons, computed_at}]`，按 `score DESC, created_at DESC, id DESC` |

---

## 8. 测试覆盖（89 条，全部通过）

| 文件 | 条数 | 覆盖点 |
|---|---|---|
| `test_meta.py` | 8 | 三份字典匿名可取、数量与种子一致、地点按校区过滤、非法校区 400；未匹配路径 / 非数字 ID / 结尾斜杠均返回 JSON 404 |
| `test_publish.py` | 12 | 401/201、publisher_id 服务端写入且客户端提交 400、found 认证 403、handover_note 规则、字段边界（标题/描述/时间/字典/地点说明）、未知字段 400、request_id 幂等、重复图片 ID、绑定他人图片 403 |
| `test_images.py` | 12 | 上传字段与 `PostImageView`、非登录 401、alt_text 5～100、is_public 布尔、413、415、公开图匿名 200 + `no-store`、私有图匿名 401/登录 200、未绑定仅上传者、撤回后仅发布者、不存在 404 |
| `test_list.py` | 12 | 默认 open+in_handover、withdrawn 永不出现、status 过滤（withdrawn→400）、关键词大小写敏感与 `%`/`_` 字面化、>50 字 400、空关键词等同不筛选、分类/校区/地点筛选、未知字典 400、地点与校区不匹配 400、时间闭区间与非法范围、两种排序、分页默认/上限 100/越界页、`PostSummary` 字段集合 |
| `test_edit.py` | 10 | 白名单可改、post_type/status/publisher_id/completed_at/campus_id 400、空提交 400、他人 403、交接中 409、撤回后本人可改、改地点重推校区、未来时间 400、found 不能清空交接说明、image_ids 替换/重排/清空 |
| `test_lifecycle.py` | 19 | 撤回后列表与详情不可见、重复撤回/恢复 409、非本人 403、恢复后重新可见、历史留痕、C 失败回滚（503 且状态不变）、C 调用参数、resolve 成功与 note 长度、found 不能办结、重复办结 409、reopen 成功/有认领 409/状态不符 409、状态机非法迁移与重复迁移 409、reopen 清空 completed_at |
| `test_integration.py` | 16 | 无令牌/未知令牌/畸形头 401、A 不可达 401 且日志、匿名列表可用、UserSummary 快照、`get_post_for_claim`、`set_handover_state` 三个 transition 与 400/409、匹配打分与硬条件（反类型/同校区/同类别/open/非本人/30 天）、limit、排除 completed/withdrawn、found 源反向匹配 |

---

## 9. 与契约 -03 的差异（及原因）

1. **重复状态操作返回 409，契约 5.4 第一条写的是“返回当前对象和 200”**  
   任务书与 EFST（US-15/US-16、FR-11 验收点“二次撤回返回 409”）明确要求 409，
   本实现按任务书执行；建议契约下一版统一为 409。
2. **多出 `POST /posts/{id}/reopen`**：契约 5.1 的表里没有，但 5.4 与 FR-12 要求“错标可回退”，
   且任务书要求“仅有完成认领记录时不可回退”，因此补为第 13 个接口。
3. **`resolve_note` 不落 Post 字段**：契约 3.5 的 Post 没有该字段，说明写入
   `workflow_poststatushistory.reason`，操作人/时间同样在该表；接口响应结构不变。
4. **C 未配置时的开发开关**：`C_BASE_URL` 为空时撤回不调用 C，只记 `b.claims` 警告
   （契约 5.1 “B 注记”允许 C 未就绪时先只改状态）；配置后失败即回滚并返回 503。
5. **新增错误码 503 `UPSTREAM_UNAVAILABLE`**：契约错误码表没有跨子系统调用失败的位置，
   502/503 二选一，这里用 503 并保证“失败必回滚”。
6. **`PostSummary.publisher` 用发布时快照**：B 没有用户表，发布时把 A 返回的
   `nickname/is_campus_verified/verification_mode` 存进 Post；A 提供批量摘要接口后可替换
   `integration/users.py`，对外结构不变（已知限制：从未发布过的用户 B 无法给出摘要）。
7. **关键词用 SQLite `REGEXP` + `re.escape` 实现**：SQLite 的 `LIKE` 对 ASCII 不区分大小写，
   无法满足“不折叠大小写”；`re.escape` 保证用户输入不被当正则、`%`/`_` 只是普通字符。
8. **`reopen` 会清空 `completed_at`**：契约只说“由业务流程设置”，回退到 open 时保留旧完成时间
   会误导，故置空并留痕。
9. **`GET /posts` 的 `status=withdrawn` 返回 400**：契约 5.3 写明“不允许传 `withdrawn`”。
10. **429 只做映射不做限流**：B 的接口在契约里没有限流要求，登录/绑定限流属于 A；
    异常处理器已把 DRF `Throttled` 映射为 429 并带 `Retry-After`（若将来给 B 配置节流）。
11. **图片 URL 为相对路径** `/api/v1/post-images/{id}/content`：与契约示例一致，由前端同源使用。
12. **未实现图片 24 小时自动清理的定时任务**：提供 `manage.py cleanup_images` 命令，
    调度由运维（cron/计划任务）决定，符合“运维/部署人员”的职责边界。

---

## 10. 已知限制 / 不做的事

- 不提供用户注册登录、令牌签发；没有 A 就只能是匿名接口可用（这是有意的边界）。
- 不实现认领申请、站内消息、匹配结果接口（`GET /posts/{id}/matches` 属 C）。
- 不实现审核、举报、下架、争议处理（系统管理子系统）。
- 不提供 `GET /users/me/posts`；A 直接查 `posts_post`。
- SQLite 单机、无并发压测；性能需求（1 万条 <200ms）只做了索引与查询设计，未做基准测试。
- 撤回时 C 关闭申请与 B 的本地回滚在同一事务内；若 C 是独立服务，“C 已关单但 B 提交失败”
  的极端情况只能靠 C 侧幂等/补偿，第一版按单库同进程联调验收。
