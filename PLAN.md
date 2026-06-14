# LLM Chat Web 應用 — 開發計畫 (PLAN.md)

> 面試作業：多人 LLM Chat Web 應用。本文件整理需求、定案技術選型、架構分層，並排出 7 天可落地的分階段開發計畫。

---

## 0. 結論先行 (TL;DR)

- **選型定案**：apiflask (後端) + Vue 3 (前端) + **PostgreSQL** + **Groq** (OpenAI 相容、free tier、原生 streaming) + Docker Compose 一鍵起。
- **最關鍵的工程判斷點不是「功能」，而是四件事**：
  1. `super_admin` 的 **idempotent seed** + 「至少 1 個 active super_admin」不變式。
  2. **streaming** 端到端打通 (SSE，含 DB 持久化的時機與斷流處理)。
  3. **RBAC** 用一個集中的權限矩陣驅動，避免散落在各 view。
  4. **JWT secret / API key** 全走環境變數，零 hardcode，`.env.example` 完整。
- **建構順序**：先打地基 (Docker + DB + migration + 設定管理) → 再 auth/JWT → 再 RBAC → 再 chat 持久化 → **最後才接 streaming 與 LLM** (風險最高、最依賴前面)。LLM 串接放最後是刻意的：它依賴 session/message model 與 auth 都先穩。
- **範圍策略**：Core 全綠且品質穩定為達標線。Bonus 只挑 4 項高 CP 值且能展現工程深度的：structured logging + request ID、health check (DB+LLM)、前端 admin 頁、對話標題自動生成。
- **每個 commit 都要能對應到 transcript**：因為評分會交叉比對 git history 與 AI 對話紀錄，務必小步提交、訊息清楚。

---

## 1. 需求整理

### 1.1 強制技術棧

| 角色 | 指定技術 | 本計畫定案 |
|------|---------|-----------|
| 後端 | apiflask | apiflask (Flask + marshmallow/apispec，內建 `/docs`) |
| 前端 | Vue 3 | Vue 3 + Vite + TypeScript + Pinia |
| 容器化 | Docker + docker-compose | 多階段 Dockerfile + compose (api / db / frontend) |
| 資料庫 | SQLite / PostgreSQL / MariaDB / MongoDB 擇一 | **PostgreSQL 16** |
| LLM 介接 | 任一線上服務 (free tier 佳) | **Groq** (OpenAI 相容 SDK、原生 SSE streaming) |

### 1.2 Core 功能需求 (必做，全綠才達標)

**1. 認證與帳號**
- 帳號密碼登入 / 登出
- JWT 做 session 管理
- 使用者可改自己的密碼
- 密碼用合適方式儲存 → **Argon2id** (或 bcrypt)，絕不明文
- JWT secret / 敏感設定走環境變數 → 不 hardcode

**2. RBAC 三層權限** (`user` / `admin` / `super_admin`)，完整矩陣：

| 動作 | user | admin | super_admin |
|------|:---:|:---:|:---:|
| 登入登出、改自己密碼 | ✓ | ✓ | ✓ |
| LLM 對話、多 session | ✓ | ✓ | ✓ |
| 查看/刪除自己的對話 | ✓ | ✓ | ✓ |
| 新增使用者 (role=user) | ✗ | ✓ | ✓ |
| 新增使用者 (role=admin) | ✗ | ✗ | ✓ |
| 列出所有使用者 | ✗ | ✓ | ✓ |
| 啟用/停用 user 帳號 | ✗ | ✓ | ✓ |
| 啟用/停用 admin 帳號 | ✗ | ✗ | ✓ |
| 將 user 升為 admin | ✗ | ✗ | ✓ |
| 匯出所有人對話 (JSON) | ✗ | ✗ | ✓ |

**系統不變式 (必須保證)**
- **(I-1) super_admin 首次啟動自動建立**：從環境變數讀帳密，首啟動建立；重複啟動 idempotent (已存在不重建、不報錯)；環境變數缺失時明確報錯而非靜默啟動成無管理員。**禁止 hardcode 帳密**。
- **(I-2) 任何時刻至少 1 個 active super_admin**：需在 README 說明如何保證 (見 §3.4 設計)。

**3. LLM 對話功能**
- 每使用者多個對話 session (ChatGPT 式左側列表)
- 對話內容持久化
- **LLM 回應逐字串流顯示 (streaming)**
- session 切換時正確載入歷史
- 使用者可刪除自己的對話

**4. 管理功能**
- 後端 Admin / Super Admin API **必須完整實作**
- 前端 admin 頁非必須 (可用 `/docs`、curl 演示)；做了算 Bonus

**5. Super Admin 匯出**：匯出所有使用者對話，格式 JSON

**6. API 文件**：維護 apiflask 內建 `/docs`，schema / tag / description 完整準確

**7. 測試**：對 auth、RBAC、對話、匯出 等核心邏輯撰寫測試 (類型/覆蓋自行判斷)

**8. 部署**：Dockerfile + docker-compose；`docker compose up` 一鍵起 (含 DB)；`.env.example`；README 註明預設管理員 / seed；說明 production worker 選擇理由

### 1.3 Bonus (選做，本計畫挑做)

挑選原則：高工程訊號、低相對成本、與 Core 共用基礎設施。

| 取捨 | Bonus 項目 | 為什麼挑 / 不挑 |
|------|-----------|----------------|
| ✅ 做 | Structured logging + Request ID tracking | 幾乎零成本，直接展現 observability 思維 |
| ✅ 做 | 完整 health check (DB + LLM 上游) | compose healthcheck 會用到，順手做 |
| ✅ 做 | 前端 Admin / Super Admin 頁 | 明列 Bonus，且能讓 demo 錄影更完整 |
| ✅ 做 | 對話標題自動生成 | UX 亮點，串接 LLM 時順帶實作，成本低 |
| 🟡 有餘力 | Rate limiting、graceful shutdown、Markdown/code highlight、dark mode | Core 全綠後才碰 |
| ❌ 不做 | E2E (Playwright)、CI pipeline、refresh token rotation、metrics endpoint | 時間風險高，邊際效益遞減；在 README「未完成項目」誠實說明取捨理由 |

### 1.4 交付物清單 (繳交前 checklist)

1. Git repo (含 `.git`，commit history 要乾淨、能對應 transcript)
2. `README.md`：啟動步驟、預設帳密/seed、**Tech Choices & Rationale**、已完成 Bonus、已知限制/未完成項目
3. 完整 LLM 對話 **原始 JSONL** transcript (不接受事後整理的 Markdown)
4. 3–5 分鐘螢幕錄影 (登入 / 對話 / admin 操作 / 匯出；可用 `/docs`)
5. `TOOLING.md` (用作業提供的範本，逐節填寫，無此項填「無」)
6. `REDACTION.md` (說明遮蔽了哪些類型敏感資訊)

> ⚠️ 易漏點：**transcript 與 REDACTION 是評分項**。從 Day 1 就保留 `~/.claude/projects/<...>/` 對話紀錄，繳交前統一 redact API key / secret / 私人路徑，撤換任何不慎外洩的憑證。

---

## 2. 技術選型與 Trade-offs (README 的 Tech Choices 段落雛形)

**資料庫 — PostgreSQL**
- 選它：production-grade、SQLAlchemy + Alembic 生態成熟、原生支援 JSONB (存 message metadata 方便)、可展現連線池 / 索引 / 交易範圍等工程考量。
- Trade-off：相較 SQLite 多一個 service，但 compose 已涵蓋；一鍵起仍成立。

**LLM Provider — Groq**
- 選它：free tier、OpenAI 相容 API (可直接用 `openai` SDK)、原生 SSE streaming、延遲低。
- Trade-off：模型清單受限於 Groq 供應，但作業明說 provider/價格不計分。用 OpenAI 相容介面包一層 adapter，未來換 provider 只改設定。

**JWT 演算法 — HS256**
- 單體服務、單一簽發者，HS256 + 環境變數 secret 足夠且最簡。
- Trade-off：若要多服務驗證會選 RS256；本作業不需要，避免 over-engineering。README 註明此判斷。

**密碼雜湊 — Argon2id**
- 現代首選 (記憶體硬、抗 GPU)。bcrypt 為可接受備案。

**Production worker — Gunicorn + Uvicorn worker / 或 gevent**
- apiflask 是 WSGI。streaming (SSE) 需要能長連線、不被 worker 提前回收。
- 決策：`gunicorn` 搭 `gevent` worker (對 SSE 長連線與 I/O 密集的 LLM 轉發友善)；worker 數 `2*CPU+1` 起步。README 說明：選 gevent 是因為 SSE 是長時 I/O 等待，thread/sync worker 容易吃滿；理由寫清楚。

**Container 策略**
- 後端多階段 build (builder 裝依賴 → slim runtime)，non-root user，`.dockerignore` 控制 context。
- 前端 build 出靜態檔，由 nginx 或 Vite preview 服務；compose 內 `depends_on` + healthcheck 控制啟動順序。

---

## 3. 架構設計 (Clean Architecture / DDD 視角)

### 3.1 分層

```
app/
  domain/            # 純業務：entity、value object、領域規則、Port (interface)
    user.py          #   User aggregate、Role、RBAC policy
    chat.py          #   ChatSession、Message aggregate
    ports.py         #   UserRepository / ChatRepository / LLMProvider (抽象)
  application/        # use case / service layer：編排，不含框架
    auth_service.py
    user_admin_service.py
    chat_service.py
    export_service.py
  infrastructure/     # 框架/IO 實作
    db/              #   SQLAlchemy models、repository 實作、Alembic
    llm/             #   Groq adapter (實作 LLMProvider port)
    security/        #   JWT、Argon2 雜湊
    config.py        #   Pydantic Settings (讀環境變數)
    seed.py          #   super_admin idempotent seed
  interface/          # apiflask blueprint、schema、權限 decorator
    api/auth.py
    api/chat.py
    api/admin.py
    api/health.py
    schemas.py       #   marshmallow / apispec request/response
    deps.py          #   DI 組裝 (request scope)
```

- **依賴方向**：interface → application → domain；infrastructure 實作 domain 定義的 port。domain 不 import 任何框架。
- **DI**：在 `interface/deps.py` 用工廠把 repository、LLMProvider、service 組起來注入 view，方便測試替身 (fake repo / fake LLM)。
- **避免**：business logic 落在 schema/view、fat model、signals 魔法行為。

### 3.2 資料模型 (PostgreSQL)

```
users
  id (uuid pk)
  username (unique, citext/lower)
  password_hash (argon2)
  role (enum: user|admin|super_admin)
  is_active (bool)
  created_at, updated_at

chat_sessions
  id (uuid pk)
  user_id (fk users, on delete cascade)
  title (text, nullable → 自動生成)
  created_at, updated_at
  index (user_id, updated_at desc)   # 左側列表排序

messages
  id (uuid pk)
  session_id (fk chat_sessions, cascade)
  role (enum: user|assistant|system)
  content (text)
  created_at
  index (session_id, created_at)     # 載入歷史、避免 N+1
```

- 列出 session 列表 + 訊息時注意 **N+1**：用 `selectinload` 或分查詢；列表頁不要 eager load 全部 messages。
- 匯出時用 streaming query / 分批，避免一次撈爆記憶體 (資料量大時)。

### 3.3 RBAC 設計

- 用**單一權限矩陣** (枚舉 `Permission` → 允許的 role 集合) 集中定義，view 上掛 `@require_permission(Permission.X)` decorator。
- 權限檢查走 application service / decorator，**不散落在 view body**。
- 跨角色約束 (例：admin 不能停用 admin、不能建 admin) 在 service 層用領域規則擋，並回 403 而非 500。

### 3.4 系統不變式的工程保證

**(I-1) super_admin idempotent seed**
- 啟動時 `seed.py` 讀 `SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD`：
  - 缺任一 → **明確 raise，啟動失敗** (fail fast，不靜默成無管理員)。
  - 已存在同名 super_admin → 跳過 (idempotent)，不重建、不報錯。
  - 不存在 → 建立。
- 用 `INSERT ... ON CONFLICT DO NOTHING` 或先查再建 + 唯一約束，避免並發重複建立。
- 在 entrypoint：先跑 Alembic migration，再跑 seed，再啟 worker。

**(I-2) 至少 1 個 active super_admin**
- 設計決策 (擇一，寫進 README)：**不提供 super_admin 自我退場 / 自我降級 / 自我停用**。
  - 任何「停用 / 降級 super_admin」操作前，在 service 層檢查「目前 active super_admin 數量 > 1」，否則拒絕 (409/422)。
  - 加上 seed 保證系統永遠有初始 super_admin → 結合矩陣限制，理論上不可能進入「無超管」狀態。
- README 用一段話說明此保證 (作業明確要求)。

### 3.5 LLM Streaming 設計 (最高風險，重點)

- **傳輸**：SSE (`text/event-stream`)。比 WebSocket 簡單、單向夠用、apiflask/WSGI + gevent 可長連線。
- **流程**：
  1. 前端送出 user message → 後端先持久化 user message。
  2. 後端呼叫 Groq (`stream=True`)，逐 token `yield` SSE event 給前端。
  3. 串流結束後，把完整 assistant 回應**一次性持久化** (避免每 token 寫 DB)。
  4. 斷流 / 上游錯誤：持久化「已收到的部分內容 + 錯誤標記」，前端顯示重試。
- **gotcha**：
  - apiflask response schema 對 streaming 端點不適用，需用裸 `Response(stream_with_context(...))`，並在 OpenAPI 手動註明此端點行為。
  - gunicorn 要用 gevent worker，且關閉 response buffering；nginx 前置時要關 `proxy_buffering`。
  - JWT 驗證要在開始串流前完成 (header 帶 token)。

---

## 4. 建構順序與依賴 (為什麼這樣排)

```
[地基] Docker+DB+migration+設定   ← 一切的前提
   │
[Auth] 註冊由 admin 建/登入登出/改密碼/JWT
   │
[RBAC] 權限矩陣 + decorator + admin API
   │
[Chat 持久化] session/message CRUD + 歷史載入
   │
[LLM Streaming] 接 Groq + SSE      ← 風險最高，依賴上面全部
   │
[匯出 + /docs + 測試 + Bonus]
```

刻意把 **LLM streaming 放最後**：它依賴 auth (誰在用)、chat model (存哪)、worker 設定 (gevent)。前面不穩就接 streaming 會反覆返工。先用 mock LLM provider 打通 chat CRUD 與前端，最後才換真 Groq。

---

## 5. 7 天分階段計畫

> 每天結束都應有「可 demo 的增量」。每完成一塊就 commit，訊息清楚 (利於 transcript 對照)。

### Day 1 — 地基與骨架 (環境穩，後面才快)
- 初始化 git repo、monorepo 結構 (`backend/`、`frontend/`、`docker/`)。
- 後端 apiflask skeleton + Pydantic Settings 讀環境變數 + `/docs` 可開。
- PostgreSQL 接上、SQLAlchemy + Alembic 初始 migration (users / chat_sessions / messages)。
- Dockerfile (多階段) + docker-compose (api + db) + `.env.example`。
- **驗收**：`docker compose up` 起得來，`/docs` 打得開，migration 自動跑。
- **產出**：可一鍵起的空殼。

### Day 2 — Auth 與 super_admin seed (不變式 I-1)
- Argon2 密碼雜湊、JWT 簽發/驗證 (HS256, secret 走 env)。
- 登入 / 登出 / 改自己密碼 endpoint + schema。
- **super_admin idempotent seed** + 環境變數缺失 fail-fast。
- 對 auth + seed 寫測試 (含「缺 env 報錯」「重複啟動不重建」案例)。
- **驗收**：compose 起來後能直接用 env 設定的 super_admin 登入；重啟不爆。

### Day 3 — RBAC 與 Admin / Super Admin API (不變式 I-2)
- 權限矩陣 + `@require_permission` decorator。
- 完整 admin API：建 user/admin、列出使用者、啟用/停用、升級 user→admin、跨角色約束。
- 「至少 1 個 active super_admin」service 層守門。
- RBAC 測試：每個矩陣格子至少一個 allow/deny 案例。
- **驗收**：用 `/docs` 或 curl 走完整管理流程，越權回 403。

### Day 4 — Chat 持久化 (先用 mock LLM)
- chat session CRUD (多 session、列表、切換載入歷史、刪除)。
- message 持久化、N+1 檢查、索引。
- 先接 **mock LLM provider** (回固定 / echo)，把前後端 chat 流程打通。
- **驗收**：能開多個對話、切換載入正確、刪除生效；資料持久化。

### Day 5 — 真・LLM Streaming (最高風險日，留緩衝)
- Groq adapter 實作 `LLMProvider` port (OpenAI 相容、`stream=True`)。
- SSE 端點 + 前端逐字渲染 + 串流結束後持久化 assistant 回應。
- gunicorn + gevent worker 設定；斷流 / 上游錯誤處理。
- **Bonus**：對話標題自動生成 (首則訊息後用 LLM 產標題)。
- **驗收**：前端看到逐字串流；重整後歷史完整；上游錯誤不會壞掉 session。

### Day 6 — 匯出、前端整合、Bonus 基礎設施
- Super Admin 匯出所有對話 (JSON，分批查詢)。
- **Bonus**：前端 Admin / Super Admin 管理頁 (對應後端端點)。
- **Bonus**：structured logging + request ID middleware；health check (DB + Groq 上游)；compose healthcheck 串起來。
- 補測試覆蓋 (匯出、邊界案例)。
- **驗收**：匯出 JSON 結構正確；admin 頁可操作；`/health` 反映 DB+LLM 狀態。

### Day 7 — 收斂、文件、交付物
- README：啟動步驟、預設帳密/seed、**Tech Choices & Rationale**、已完成 Bonus、**已知限制/未完成項目** (誠實寫沒做的 Bonus 與理由)。
- `TOOLING.md` (照範本逐節)、`REDACTION.md`。
- 整理並 **redact transcript** (JSONL)，撤換任何外洩憑證。
- 錄 3–5 分鐘 demo (登入 / 對話 streaming / admin 操作 / 匯出)。
- 全量跑測試、`docker compose up` 從乾淨環境驗一次一鍵起。
- 打包 zip (含 `.git`)。
- **驗收**：別人拿到 zip，照 README 能一鍵跑起來。

> **緩衝原則**：若進度落後，Day 5 的 streaming 與 Day 7 的交付物優先；Day 6 的 Bonus 全部可砍，砍掉就在 README 未完成項目誠實說明。

---

## 6. 測試策略

- **單元 (pytest)**：domain 規則 (RBAC 矩陣、不變式守門)、密碼雜湊、JWT。用 fake repository，不碰 DB。
- **整合**：service + 真 DB (pytest fixture 起測試 schema / 交易回滾)、auth flow、admin flow、匯出。
- **LLM**：用 fake `LLMProvider` 注入，測 streaming 端點的事件序列與持久化，不打真 API (穩定、免費、可重現)。
- **factory_boy** 造測試資料。
- 最低標：作業點名的 auth / RBAC / 對話 / 匯出 四塊都有測試。

---

## 7. 風險清單與對策

| 風險 | 影響 | 對策 |
|------|------|------|
| SSE streaming + WSGI worker 設定踩坑 | 高 | Day 4 先用 mock 打通流程，Day 5 才換真 Groq；預留緩衝 |
| super_admin 不變式設計沒講清楚 | 中 (扣分點) | §3.4 決策 + README 明確說明保證機制 |
| transcript 沒留 / 沒 redact | 中 (繳交瑕疵) | Day 1 就確認紀錄路徑；繳交前統一 redact + REDACTION.md |
| Bonus 吃掉 Core 時間 | 中 | Core 全綠才碰 Bonus；Day 6 Bonus 可全砍 |
| N+1 / 匯出記憶體爆 | 低中 | 索引 + selectinload；匯出分批 |
| 密碼 / secret hardcode | 高 (硬傷) | 全走 Pydantic Settings + `.env`；`.dockerignore` 排除 `.env` |

---

## 8. 立即可動的第一步 (Day 1 開工順序)

1. `git init`，建 monorepo 目錄與 `.gitignore` / `.dockerignore` / `.env.example`。
2. 後端 apiflask 最小 app + Pydantic Settings + `/health` + `/docs`。
3. compose 起 PostgreSQL，SQLAlchemy 連上，Alembic 初始 migration。
4. 寫 Dockerfile (多階段) + compose，確認 `docker compose up` 一鍵起。
5. 第一個有意義的 commit：「chore: project skeleton, docker compose one-command up」。

> 地基穩了，Day 2 之後每天都是疊加可 demo 的功能，而不是和環境奮鬥。
