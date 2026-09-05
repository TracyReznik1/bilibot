# Bilibili AI 机器人增强方案设计（Gemini 驱动 + 楼中楼修复 + @监听）

## 1. 概述
基于开源项目 `chenluQwQ/bilibili-ai-bot`，在保留其完整的 Web 管理面板、记忆系统、好感度系统及扫码登录特性的基础上，进行针对性功能增强与模型对接：
1. 修复楼中楼子评论嵌套回复（准确区分 `root` 和 `parent`）。
2. 新增 `@我的`（`x/msgfeed/at`）消息中心监听，实现 @ 自动回复。
3. 对接 Google Gemini API（通过 Gemini 官方 OpenAI 兼容接口或直调）。

## 2. 详细改造点

### 2.1 楼中楼回复逻辑修复
在 `ai.py` 中：
- 修改 `send_reply` 接口参数，明确拆分 `root_id` 与 `parent_id`：
  ```python
  def send_reply(oid, root_id, parent_id, content_type, reply_text):
      url = "https://api.bilibili.com/x/v2/reply/add"
      data = {
          "oid": oid,
          "type": content_type,
          "root": root_id,
          "parent": parent_id,
          "message": reply_text,
          "csrf": BILI_JCT
      }
  ```
- 在 `get_new_replies` 及消息循环中：
  - 一级评论：`root_id = source_id`, `parent_id = source_id`
  - 楼中楼子评论：`root_id = r.get("root_id") or source_id`, `parent_id = source_id`

### 2.2 新增 `@我的` 消息监听
- 新增 `get_new_ats()` 函数，访问 `https://api.bilibili.com/x/msgfeed/at`。
- 解析返回的通知项：
  - `source_id`: 触发 @ 的评论 ID（作为 `parent_id`）
  - `root_id`: 根评论 ID（如果通知内无 root_id 则等于 source_id）
  - `subject_id`: 目标资源 ID（`oid`，如视频 avid 或动态 id）
  - `business_id`: 业务类型（1=视频评论，11/17=动态评论等）
  - `source_content`: @ 处的文字内容
  - `user`: 触发者的 nickname 和 mid
- 统一送入消息处理管线，过滤自身 uid，记录已处理 `rpid` 防重。

### 2.3 Gemini 模型配置接入
- 利用 Gemini 提供的 OpenAI 兼容接口：
  - Base URL: `https://generativelanguage.googleapis.com/v1beta/openai/`
  - Model: `gemini-2.5-flash` / `gemini-1.5-flash` / `gemini-1.5-pro`
  - API Key: 用户申请的 Gemini API Key
- 在 `config.example.json` 和 `config.py` 中提供清晰的 Gemini 预设模板。

## 3. 部署与使用流程
1. 克隆代码到当前项目根目录。
2. 应用增强补丁（修改 `ai.py`）。
3. 安装依赖（`pip install -r Requirements.txt`）。
4. 启动面板（`python local-chat.py`）扫码登录 B 站，配置 Gemini API Key。
5. 启动后台主程序（`python ai.py`）。
