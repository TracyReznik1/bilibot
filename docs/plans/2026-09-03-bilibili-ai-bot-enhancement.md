# Bilibili AI Bot 增强部署实施计划

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** 基于 `chenluQwQ/bilibili-ai-bot` 部署支持 Gemini 大模型、修复深层楼中楼回复逻辑，并新增 `@我的` 消息自动回复的 B站 AI 机器人。

**Architecture:** 克隆开源项目后，在 `ai.py` 中重构评论回复参数以精准支持楼中楼嵌套，接入 `x/msgfeed/at` 轮询接口解析 @ 消息并统一喂入 AI 回复与好感度记忆管线，配置 Gemini OpenAI-compatible 协议端点。

**Tech Stack:** Python 3.10+, Requests, Flask, OpenAI SDK (Gemini Endpoint), Bilibili Web API.

---

### Task 1: 克隆项目源码至工作区

**Files:**
- Create: 工作区所有项目源码文件（来自 `https://github.com/chenluQwQ/bilibili-ai-bot.git`）

**Step 1: 执行 git clone 到临时目录并转移至工作区根目录**
```powershell
git clone https://github.com/chenluQwQ/bilibili-ai-bot.git temp_bot
Move-Item -Path temp_bot/* -Destination . -Force
Move-Item -Path temp_bot/.git* -Destination . -Force
Remove-Item -Recurse -Force temp_bot
```

**Step 2: 验证项目结构**
检查 `ai.py`, `config.example.json`, `local-chat.py`, `Requirements.txt` 是否完整存在。

---

### Task 2: 修复楼中楼回复定位（`root` 与 `parent`）

**Files:**
- Modify: `ai.py`

**Step 1: 修改 `send_reply` 函数签名与请求体**
将：
```python
def send_reply(oid, rpid, content_type, reply_text):
    url = "https://api.bilibili.com/x/v2/reply/add"
    data = {
        "oid": oid, "type": content_type,
        "root": rpid, "parent": rpid,
        "message": reply_text, "csrf": BILI_JCT
    }
```
修改为：
```python
def send_reply(oid, root_id, parent_id, content_type, reply_text):
    url = "https://api.bilibili.com/x/v2/reply/add"
    data = {
        "oid": oid, "type": content_type,
        "root": root_id, "parent": parent_id,
        "message": reply_text, "csrf": BILI_JCT
    }
```

**Step 2: 修改评论解析中的 `root_id` 与调用**
在 `get_new_replies` 和主循环中，确保如果评论来自楼中楼，准确记录 `root_id`，并将 `source_id` 作为 `parent_id` 传递给 `send_reply`。

---

### Task 3: 增加 `@我的` 消息中心监听与回复

**Files:**
- Modify: `ai.py`

**Step 1: 编写 `get_new_ats()` 接口获取函数**
请求 `https://api.bilibili.com/x/msgfeed/at?ps=10&pn=1`，解析 `@` 的 `source_id`、`subject_id` (oid)、`root_id`、`business_id` (type)、`source_content`、用户 mid 等。

**Step 2: 接入主轮询循环与去重**
在 `run()` 循环中，轮询 `get_new_ats()`：
- 过滤机器人自身的 mid（防死循环）。
- 去重检查 `rpid in replied_rpids`。
- 送入现有 AI 回复生成流程，通过 `send_reply` 发送到对应评论楼层。

---

### Task 4: 配置 Gemini 大模型支持与配置文件模板

**Files:**
- Modify: `config.example.json`
- Create: `config.json`（若不存在，提供 Gemini 快速预设）

**Step 1: 在配置中预置 Gemini 接口参数**
- `OPENAI_BASE_URL`: `https://generativelanguage.googleapis.com/v1beta/openai/`
- `OR_CHAT_MODEL`: `gemini-2.5-flash` 或 `gemini-1.5-flash`
- 预留 `OR_API_KEY` 供用户填入其 Gemini API Key

---

### Task 5: 验证与运行指引

**Step 1: 验证 Python 语法与模块解析**
运行 `python -m py_compile ai.py local-chat.py` 确保无语法错误。

**Step 2: 整理运行与使用文档（README 指引）**
提供清晰的扫码登录、启动 Web 调试面板和启动后台守护进程的操作步骤。
