# B 子系统后端

按《共同字段与接口约定》v0.5 实现，覆盖 B 的职责：**基础字典、信息发布与图片、浏览检索、
详情、状态管理**。A（用户管理）保留演示实现用于自查，C（认领）用桩代替。

- 技术栈：Python 3.13 · Django 5.2 · DRF · SQLite（自测）/ MySQL 8（验收）
- 不实现：认领流程与站内消息（C）、审核与举报

---

## 1. 目录

```
backend/
├── config/            # settings（数据库、DRF、日志）、urls（/api/v1）
├── common/            # 响应信封、异常、认证、分页、冻结的契约结构（contracts.py）
├── posts/             # B 的主体
│   ├── models.py      # Post / PostImage / Campus / Category / Location
│   ├── constants.py   # 契约常量：状态、字段白名单、分页、错误码
│   ├── dictionary.py  # 字典门面：list_options / get_option / resolve_location / valid_option_ids
│   ├── query.py       # 检索：筛选、排序、分页（唯一实现）
│   ├── images.py      # 上传校验、可见性、内容响应、清理
│   ├── browse.py      # PostSummary / PostDetail 组装
│   ├── services.py    # 给 C 的同进程函数（要求调用方已开事务）
│   ├── serializers.py # 单字段校验
│   └── views.py       # HTTP 薄壳
├── workflow/          # 状态机：transit(post, action, actor, reason) + 审计表
├── catalog/           # /meta/* 三个字典接口
├── identity/          # A 的演示身份（demo token）
├── users/             # A 的用户与登录会话模型
└── integration/       # auth（取当前用户）、claims（C 的桩）
```

## 2. 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AUTH_SECRET` | 开发默认值 | 大于等于 16 字符；生产必须显式设置 |
| `DATABASE_URL` | `sqlite:///var/db.sqlite3` | 验收用 `mysql://user:pass@127.0.0.1:3306/claim_dev` |
| `DEMO_MODE` | `false` | 开启后可用 `/api/v1/demo/token` 快速换令牌 |
| `DJANGO_DEBUG` | `true` | |

## 3. 运行

```powershell
cd backend
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

## 4. 字段与规则要点

- **主键**：`Post.id` 是 UUID 字符串（契约 3.5）。
- **状态**：`open` / `in_handover` / `completed` / `withdrawn`；默认列表只展示前两个，
  `completed` 需要显式筛选（`status=completed`），`withdrawn` 不参与筛选。
- **关键词**：标题与描述的字面包含，**大小写敏感**，`%` 与 `_` 不作通配符。
- **描述**：必填 10～2000 字，模型层有 CHECK 约束兜底。
- **交接说明**：招领（`found`）必填，失物（`lost`）不能填写。
- **图片**：单张不超过 5 MiB，只接受 jpeg/png/webp，`alt_text` 5～100 字且不能只写
  `image` / `photo`；`is_public=false` 的图需要登录，任何登录用户都能读。
- **重复状态操作**：返回 `409 STATE_CONFLICT`，不覆盖首次操作的时间。
- **发布者缺失**：查不到的用户降级为 `{"nickname": "已注销用户", "is_campus_verified": false}`，
  列表与详情不中断。

## 5. 给 C 的接口（契约 7.1）

| 函数 | 说明 |
| --- | --- |
| `services.get_post_for_claim(post_id, lock=False)` | 读取单条信息；`lock=True` 时锁行 |
| `services.get_posts_for_claims(post_ids, lock=False)` | 批量读取 |
| `services.set_handover_state(post_id, transition)` | `reserve` / `complete` / `reopen` |
| `services.list_match_candidates(source)` | 同校区同分类的反类型进行中信息 |

前三个都要求调用方已经开启事务，否则抛 `RuntimeError`，避免认领记录与信息状态不一致。

## 6. 测试

```powershell
.\.venv\Scripts\python.exe manage.py test posts users
```
