# 校园失物招领系统 · B 子系统前端 v0

> 目的：**只验证「信息发布与浏览」（B）能融入小组的前后端契约**，不是最终交付。
> 契约依据：工作区根目录 `共同字段与接口约定-03.md`（v0.4）§5.1 接口清单、§5.3 列表参数、§3.9 响应结构、§3.5 Post 字段、§3.6 PostImage。
> 需求依据：`课内实验/EFST树.md` 的 E2（信息发布与图片）、E3（浏览检索与展示）。

技术栈：Vue 3 + Vite + vue-router，样式手写 CSS（不引入任何需要联网安装的 UI 库）。

---

## 1. 页面清单（3 个页面，全部真实调用后端接口）

| 页面 | 路由 | 对应 Story | 说明 |
|---|---|---|---|
| 公开列表 | `/` | E3 F3.1 US-11、F3.2 US-12/US-13 | 类型切换（全部 / 失物 / 招领）、关键词、筛选（类别 / 校区 / 地点 / 状态 / 发生时间范围）、排序（最新 / 发生时间）、分页、空结果提示、结果计数 |
| 信息详情 | `/posts/:id` | E3 F3.3 US-14、E4 US-15/16/17 | 全部字段、发布者昵称与认证状态、四状态文案、图片与替代文字、撤回仅本人可见提示；发布者操作：撤回 / 恢复 / 办结（办结需 5～200 字说明） |
| 发布 / 编辑 | `/posts/new`、`/posts/:id/edit` | E2 F2.1 US-06/US-07、F2.2 US-08/US-09、F2.3 US-10 | 字段校验与字段级错误回填、图片先上传再提交 `image_ids`、每张图填 `alt_text` 并可勾选“允许未登录查看”、提交失败保留已填内容 |

明确**不做**（归属其他人 / 未来的系统管理子系统）：登录注册页、我的发布、认领与站内消息、审核举报、字典管理、图片下架。

身份只做“消费”：从 `localStorage.token` 读取 Bearer 令牌。

- 没有令牌：列表与详情照常匿名可用；发布页显示“需要登录”的提示卡片，**不跳转**（登录页归 A）。
- 令牌失效（401）：统一封装层清掉本地令牌并提示，公开页面自动以匿名身份重试一次（契约 §2.2）。

---

## 2. 对接了哪些接口

| 方法 | 路径（均加 `/api/v1`） | 用途 | 页面 |
|---|---|---|---|
| GET | `/posts` | 公开列表分页查询（§5.3 全部参数） | 列表 |
| GET | `/posts/{id}` | 详情（`PostDetail`） | 详情、编辑回填 |
| POST | `/posts` | 发布（`lost` 只需登录；`found` 需校园认证，否则 403 `IDENTITY_REQUIRED`） | 发布 |
| PATCH | `/posts/{id}` | 编辑（只提交允许修改字段；`image_ids` 缺省表示不改图片） | 编辑 |
| POST | `/posts/{id}/withdraw` | 撤回（`open` → `withdrawn`） | 详情 |
| POST | `/posts/{id}/restore` | 恢复（`withdrawn` → `open`） | 详情 |
| POST | `/posts/{id}/resolve` | 失物自行办结（`resolve_note` 5～200 字） | 详情 |
| POST | `/post-images` | 上传图片（multipart：`file`、`alt_text` 5～100 字、`is_public` 默认 true） | 发布、编辑 |
| GET | `/post-images/{id}/content` | 图片二进制；`is_public=false` 或未绑定图带令牌取 Blob 预览 | 列表、详情、编辑 |
| GET | `/meta/campuses` | 校区字典（筛选用） | 列表、编辑 |
| GET | `/meta/categories` | 类别字典 | 列表、编辑 |
| GET | `/meta/locations` | 地点字典（发布只用 `location_id`，`campus_id` 由服务端推导） | 列表、编辑 |
| GET | `/users/me` | **A 的接口**，仅用来判断“我是不是发布者”以显示操作按钮；不可用时静默降级 | 详情、编辑 |

约定实现要点：

- 所有 JSON 请求统一解析 `{ code, message, data, errors }`：HTTP 2xx 且 `code === 'OK'` 返回 `data`，其余抛 `ApiError`（带 `status` / `code` / `message` / `errors`），页面据此给出中文提示（错误码映射见 `src/api/http.js` 的 `CODE_TEXT`）。
- 图片内容接口不使用 JSON 包装，单独走 `fetchImageBlob`（`src/api/http.js`），**令牌不拼进 URL**。
- 列表查询只提交 §5.3 允许的参数，空字符串不提交；时间筛选按北京时间当天 00:00:00 / 23:59:59 转成 UTC ISO。
- 时间响应按 UTC 解析、按北京时间（UTC+8）显示，不依赖浏览器本地时区。

---

## 3. 需要 A 提供什么

1. **登录与令牌**：`POST /auth/login` 成功后由 A 的页面把 `data.access_token` 写入 `localStorage.token`（键名固定为 `token`）。本前端只读该键，不做登录页、不发登录请求。
2. **`GET /users/me`**：用于判断当前用户是否为信息发布者，从而显示编辑 / 撤回 / 恢复 / 办结按钮。返回 `UserSelf`，至少需要 `id`。
   - 该接口未就绪时本前端不阻塞：详情页仍显示操作按钮，但会提示“无法确认登录身份，权限以服务端校验为准”；点错会拿到 403 并给出提示。
3. **令牌有效期与撤销语义**：过期/撤销返回 `401 UNAUTHENTICATED`（契约 §2.2）。本前端收到 401 会清掉 `localStorage.token` 并提示重新登录，已填表单内容不清空。
4. **校园身份（`is_campus_verified` / `verification_mode`）**：发布招领时后端返回 `403 IDENTITY_REQUIRED` 即视为未绑定，前端按契约提示“非校园用户不能发布招领，请将物品送至失物招领处”并给出地址与联系方式（见下方“待确认内容”）。
5. **“我的发布”页面**：由 A 直查 B 的 `Post` 表实现，`GET /users/me/posts` 不归本前端；A 的页面跳转到本前端的 `/posts/:id/edit` 即可复用编辑页。

另需要 B 后端提供：

- `POST /posts` 与 `PATCH` 的 `errors` 字段名与表单字段一致（`title` / `category_id` / `description` / `location_id` / `occurred_at` / `handover_note` / `image_ids`），否则字段级错误只能显示在顶部汇总。
- 后端允许本前端来源的跨域请求（见第 5 节），或改走 vite dev proxy。

---

## 4. 运行方式

```bash
cd 代码迭代/0-架构设计前/frontend
npm install
npm run dev
# 默认 http://127.0.0.1:5173
```

其他脚本：

```bash
npm run build   # 产物在 dist/，只用于确认代码可编译，不是部署交付
npm run preview # 预览构建产物
```

没有后端时页面会显示“加载列表失败 / 无法连接后端接口 …”，这是预期的真实空态，页面里**没有假数据**。要看到数据，需要 B 的后端至少实现 `/posts`、`/meta/*`。

### 本次开发机上的实际安装结果（如实记录）

本仓库编写时所在机器有文件沙箱限制（不允许写全局 npm 缓存、不允许 spawn 子进程），实际执行的命令是：

```bash
# 在 frontend/ 目录下；缓存写到工作区的 .tmp，绕开“禁止写全局 npm 缓存”
npm install --no-audit --no-fund --ignore-scripts --cache ../../../.tmp/npm-cache
```

结果：**`node_modules` 安装成功（36 个包，vue / vue-router / vite / @vitejs/plugin-vue 齐全，`package-lock.json` 已生成）**。
但 `npm run dev` / `npm run build` 需要 esbuild 启动子进程，被沙箱以 `spawn EPERM` 拒绝，所以**这台机器上没能真正跑起 dev server，也没有在浏览器里点过页面**；换成普通开发机应可直接 `npm install && npm run dev`。

替代的静态验证（已通过，脚本为一次性自检、未随交付保留）：

- 用 `@vue/compiler-sfc` 编译全部 12 个 SFC（parse + script + template + style）：0 失败；
- 检查模板里引用的标识符是否都能在 setup 绑定中找到：0 处缺失；
- 对时间换算（UTC ↔ 北京时间、日期上下界）、表单校验、后端 `errors` 归一化跑了 21 条断言：全部通过。

若 `npm install` 因网络失败：本目录源码完整可读（`src/` 下全部为手写代码，无生成物），依赖仅 `vue`、`vue-router`、`vite`、`@vitejs/plugin-vue`，可直接阅读或在有网络的环境重装；`node_modules/` 与 `dist/` 未提交。

---

## 5. `VITE_API_BASE` 与跨域

默认值：`http://127.0.0.1:8000/api/v1`（**配置项，不是假数据**）。写在 `.env.example`，复制成 `.env.local` 可覆盖：

```ini
VITE_API_BASE=http://127.0.0.1:8000/api/v1
```

两种联调方式：

1. **直连（默认）**：后端需允许 `http://127.0.0.1:5173` 的 CORS，并允许 `Authorization` 请求头、`multipart/form-data`。
2. **dev proxy**：把 `VITE_API_BASE` 改成 `/api/v1`，在 `.env.local` 里设置 `VITE_PROXY_TARGET=http://127.0.0.1:8000`，请求经 vite 转发，无需后端开 CORS（`vite.config.js` 已配置 `/api/v1` 代理）。

注意 `VITE_API_BASE` 必须以 `/api/v1` 结尾（封装层不会再补前缀），末尾斜杠会被自动去掉。

---

## 6. 目录结构

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── .env.example
├── README.md
└── src/
    ├── main.js
    ├── App.vue
    ├── router.js                 # 3 个页面路由
    ├── config.js                 # 状态/类型中文映射、长度限制、图片约束、失物招领处文案
    ├── api/
    │   ├── http.js               # API_BASE、code/message/data 解析、ApiError、图片 Blob
    │   ├── posts.js              # 列表/详情/发布/编辑/三个状态操作/图片上传
    │   ├── meta.js               # 校区/类别/地点字典
    │   ├── users.js              # GET /users/me（A），失败静默
    │   └── session.js            # localStorage.token 读写 + 响应式令牌
    ├── components/
    │   ├── AppHeader.vue         # 导航 + 登录状态 + 令牌失效提示
    │   ├── PostCard.vue          # 列表卡片（类型/状态/地点/时间/发布者）
    │   ├── PostImage.vue         # 统一图片：可读显示、不可读显示 alt_text 占位
    │   ├── StatusBadge.vue       # 四状态徽章
    │   ├── FilterBar.vue         # 类型切换 + 关键词 + 筛选 + 排序
    │   ├── PaginationBar.vue     # 分页
    │   ├── NoticeBar.vue         # 统一提示条（错误/警告/成功）
    │   └── ImageUploader.vue     # 逐张上传、alt_text、is_public、排序、移除
    ├── views/
    │   ├── ListView.vue
    │   ├── DetailView.vue
    │   └── EditorView.vue
    ├── utils/
    │   ├── format.js             # UTC ↔ 北京时间、字符数、文件大小
    │   ├── validate.js           # 前端预校验 + 后端 errors 归一化
    │   └── image.js              # 图片可见性判定
    └── styles/main.css           # 手写全局样式
```

---

## 7. 关键行为与契约对照

| 要求（EFST / 契约） | 实现位置 |
|---|---|
| 列表默认只展示 `open` + `in_handover`，`completed` 需显式筛选，不出现 `withdrawn` | `FilterBar.vue` 状态下拉（空值 = 后端默认） |
| 类型切换“全部 / 失物 / 招领”含无障碍标签 | `FilterBar.vue` 的 `role="tablist"` / `aria-selected` |
| 关键词 ≤50 字，空关键词等于不筛选 | `FilterBar.vue` 计数 + `posts.js` 的 `normalizeListQuery` |
| 关键词 + 筛选 + 排序同时生效 | 全部放进同一个 `GET /posts` 查询 |
| 空结果提示、结果计数、筛选条件回显（URL query） | `ListView.vue` 的 `emptyMessage` / `total` / `syncUrl` |
| 未登录遇到不可读图片：显示 `alt_text`、不请求原图、布局不塌陷 | `utils/image.js` + `PostImage.vue` |
| 登录后同一列表中的受保护图片变为可读 | 令牌响应式（`session.js` 的 `tokenRef`），组件重新挂载时按新令牌判定 |
| 详情页展示全部字段、发布者昵称与认证状态 | `DetailView.vue` |
| 撤回信息仅本人可见的提示；他人 404 | `DetailView.vue` 的 warn 提示 + 404 错误态 |
| 状态文案：进行中 / 交接中 / 已完成 / 已撤回 | `config.js` 的 `STATUS_TEXT` |
| 办结需填 5～200 字说明 | `DetailView.vue` 的 resolve 表单 + `validate.js` |
| 409 提示当前状态 | `DetailView.vue` 的 `runAction` 捕获 409 后提示并重新拉取详情 |
| 400 字段级错误落到对应输入框，且失败保留已填内容 | `EditorView.vue` 的 `fieldErrors` + `focusFirstError`，提交路径不清空任何状态 |
| 图片先上传再提交 `image_ids`；响应改用 `images` | `ImageUploader.vue` + `EditorView.vue` 的 `buildPayload` |
| 每张图 `alt_text` 5～100 字、逐张 `is_public` | `ImageUploader.vue` |
| 编辑时 `image_ids` 缺省表示不改；变了才提交（含重排） | `EditorView.vue` 的 `sameIds` 比较 |
| `request_id` 幂等 | 创建时生成一次 UUID，失败重试复用；成功后换新值 |

---

## 8. 已知限制 / 待确认内容

1. **失物招领处的地址、电话、服务时间**：契约要求 403 `IDENTITY_REQUIRED` 时给出，但未定义获取接口，现为占位文案，写在 `src/config.js` 的 `LOST_AND_FOUND_OFFICE`，联调时替换。
2. **`/users/me` 不可用时**：详情页会显示操作按钮（提示“身份未确认”），点错由服务端 403 兜底；编辑页无法判断“非本人”，同样依赖服务端 403。
3. **校区与地点的联动**：地点字典一次性拉全量（`GET /meta/locations` 不带 `campus_id`），前端按校区过滤显示，并在选地点时自动对齐 `campus_id`，避免提交“校区与地点矛盾”导致 400。若地点数据量变大，可改为按 `campus_id` 懒加载。
4. **图片格式/大小**：前端只按 `file.type` 和 5 MiB 预检，最终以服务端 413 / 415 为准。
5. **未实现**：退出登录只清本地令牌并刷新页面，不调用 `POST /auth/logout`（归 A）；没有草稿、举报、审核、认领入口（按范围排除）。
6. **request_id 幂等**：若后端未实现该字段，多余字段可能被当作未知字段返回 400（契约 §2.1 要求未知字段报 400）。联调时若后端尚未实现，请先删除 `EditorView.vue` 里 `payload.request_id` 这一行；本前端按契约保留。
7. **筛选时间用日期粒度**：接口支持 `occurred_from` / `occurred_to` 精确到秒，页面用日期选择器（当天 00:00:00 ~ 23:59:59，北京时间）。
8. **状态筛选“全部”**：不传 `status`，由后端返回 `open` + `in_handover`；页面不会把 `withdrawn` 作为筛选项（契约禁止）。

---

## 9. 联调顺序建议（对应契约 §8.1）

1. 起后端，确认 `/meta/*` 返回字典种子数据；
2. 列表页能拉到空 `items` 或数据，无 CORS 报错；
3. 用 A 的登录页写入 `localStorage.token`，刷新后发布一条 `lost`；
4. 上传 0～6 张图片（每张填 alt_text，其中一张取消“允许未登录查看”）→ 发布 → 详情页；
5. 退出登录（清令牌）再看列表和详情，确认受保护图片显示替代文字；
6. 编辑、撤回、恢复、办结（`lost`）逐项验证 409 与字段级 400。
