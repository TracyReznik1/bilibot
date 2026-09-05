# 🤖 Bilibili AI Bot (Enhanced Edition)

<div align="center">

一个深度演化、支持安全私信、精准楼中楼回复与智能降级视频流的 **B站全能 AI 角色系统**。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Tests Passing](https://img.shields.io/badge/Tests-32%20Passed-success.svg)](#-自动化测试与质量保障)
[![GitHub Stars](https://img.shields.io/github/stars/TracyReznik1/bilibot?style=social)](https://github.com/TracyReznik1/bilibot)

</div>

---

> 💡 **致敬与开源血统 (Upstream Tribute)**：
> 
> 本项目基于 [@chenluQwQ](https://github.com/chenluQwQ) 开源的优秀原型项目 [chenluQwQ/bilibili-ai-bot](https://github.com/chenluQwQ/bilibili-ai-bot) 进行深度演化与重构。衷心感谢原作者为社区带来的出色架构与灵感！
> 
> 在原版基础上，本增强版重构了底层评论交互协议，自研了闭环私信安全体系、三级平滑降级的主动视频流、动态用户全生命周期管理系统，并实现了全域零硬编码与自动化测试工程化。

---

## 🌟 核心差异与特性升级 (Original vs Enhanced)

| 维度 / 功能 | 原始版本 (chenluQwQ) | 🚀 增强版 (本项目) |
| :--- | :--- | :--- |
| **子评论回复** | 混淆 root/parent，多层对话易变平铺评论 | **精准「楼中楼」嵌套回复**：严格解耦根楼层与父节点，长串讨论自然跟帖 |
| **@消息交互** | 暂未支持 | **新增独立「@我的」消息流监听**：支持动态与视频评论 @ 自动捕获与防自刷过滤 |
| **B站私信系统** | 暂未实现 | **全新全套私信模块**：共享记忆人格，自带钓鱼/色情外链隔离防护与自动拉黑 |
| **主动刷视频** | 仅按固定分区随机拉取，偶发候选数为 0 | **多标签搜刷 + 排除词 + 三级降级保底**：标签不足平滑回退，保证候选池永不落空 |
| **视频推荐@** | 仅能固定 @ 主人 | **自由 @ 目标选择器**：可指定主人、认识的人，支持多选随机抽取或一键取消 @ |
| **用户画像管理** | 仅只读展示，保存后不可修改 | **全功能编辑/删除模态框**：支持修改 UID（自动迁移记忆与@）、好感度实时徽章预览 |
| **主人身份绑定** | 配置易被数据覆盖，偶有硬编码 | **纯动态数据自愈引擎 (`sync_owner_state`)**：配置热更即生效，全代码零硬编码 |
| **模型生态与容错** | 强依赖外部 Embedding 向量服务 | **弹性解耦**：深度适配 Gemini 3.5/3.1 Flash，Embedding 失效优雅降级 |
| **工程质量保障** | 暂无自动化测试 | **配备 32 个自动化测试用例（覆盖率 100% 通过）** + Windows 一键启动脚本 |

---

## ✨ 核心增强模块深度解析

### 1. 💬 精准「楼中楼」嵌套定位与 @我的 独立监听
- **楼中楼层级修复**：依据 B 站底层评论接口协议（参考社区 [bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect) 规范），重构 `send_reply`，严格将顶层根楼层 `root_id` 与直接对话目标 `parent_id` 拆分解耦。无论是在几百楼的子评论中回复路人，机器人都能精准挂靠在被回复者的下方。
- **独立 @ 监听机制**：对接 `x/msgfeed/at` 协议流，自动捕获用户在动态、视频各处的 @ 互动，自带已处理去重库、机器人自我识别防自刷与死循环熔断。

### 2. ✉️ 闭环 B站私信安全引擎 (`private_messages.py`)
- **同质化人格体验**：私信与评论共享同一套世界观、长期向量记忆、好感度与用户档案，聊过天的朋友在私信里依然能被认出。
- **冷启动安全锚点**：首次启用自动记录当前私信位点，只处理未来产生的新消息，绝不轰炸式翻看历史老消息。
- **多层防钓鱼隔离与自动拉黑**：
  - 自动拦截非受信外链、纯 IP 链接、疑似色情/灰产引流文案；
  - 危险内容直接阻断送入大模型，支持一键调用 B 站真实拉黑；
  - 配备免拉黑白名单，主人与 Bot 自身始终受豁免保护。

### 3. 🎯 目标标签搜刷与「三级平滑降级」保底系统
- **智能多标点切分**：采用正则引擎，无缝兼容中文逗号（`，`）、顿号（`、`）、英文逗号（`,`）、分号、空格及换行，粘贴任意格式关键词均可自动识别去重。
- **排除关键词过滤**：自动过滤带有“广告”、“商业推广”、“带货”等指定负面词的内容。
- **三级降级兜底保障机制**：
  $$\text{Tier 1: 目标标签精准检索} \longrightarrow \text{Tier 2: 喜好分区热门视频} \longrightarrow \text{Tier 3: B站全站综合排行榜}$$
  当冷门标签候选视频不足时，自动放宽条件补充候选池，彻底告别“匹配到 0 个候选视频”导致流程中断的问题。

### 4. 👥 Web 管理面板全功能用户生命周期管理
- **卡片点击即编辑**：点击任意用户卡片即可唤起编辑模态框，支持修改 UID、B站昵称、机器人称呼、好感度分值、印象与特征事实。
- **UID 自动安全迁移**：修改用户 UID 时，自动关联迁移其名下的长期记忆数据（`memory.json`）与视频推荐 @ 目标列表，并具备防重复 UID 冲突拦截。
- **添加认识的人升级**：高颜值毛玻璃弹窗，支持自由输入 0~100 好感度，实时根据分值预览关系等级徽章（陌生人/粉丝/熟人/好友/主人），支持自定义标签拓展。

### 5. 🛡️ 纯动态架构与零硬编码保障
- 业务代码逻辑中**不存在任何预置硬编码 UID、魔法数字或个人隐私数据**。
- 主人判定、亲密度校准完全由 `config.json` 动态驱动，即使更换主人账号，系统也会自动执行自愈对齐（`sync_owner_state`），不留任何历史脏数据。

---

## 📦 项目结构

```
bilibot/
├── ai.py              # 主程序：评论/私信监听、主动行为调度、记忆管理
├── private_messages.py# 私信轮询、发送、去重与安全防御引擎
├── bili_login.py      # B站扫码登录与凭据保存
├── Proactive.py       # 主动刷视频 + 智能降级兜底 + 评价互动模块
├── dynamic.py         # 动态发布模块
├── local-chat.py      # Flask Web 面板 + 交互式管理 API
├── chat.html          # 前端管理面板（响应式，支持手机端）
├── config.py          # 动态配置中心（热更、Cookie 刷新、主人数据自愈）
├── config.example.json# 公开脱敏配置模板
├── Requirements.txt   # Python 运行依赖
├── start_bot.bat      # [Windows] 一键启动主后台监听
├── start_web.bat      # [Windows] 一键启动 Web 管理面板
├── start_watch.bat    # [Windows] 一键启动主动刷视频模式
├── tests/             # 自动化单元测试套件（32 个全通过）
└── data/              # 运行时数据存储（好感度、记忆、日志等，已 .gitignore）
```

---

## 🚀 快速开始

### 1. 环境准备
- Python 3.8+
- Bilibili 账号（支持直接在 Web 面板扫码登录）
- 兼容 OpenAI 格式的模型 API Key（推荐 Gemini、DeepSeek、Claude 等）

### 2. 克隆与安装

```bash
git clone https://github.com/TracyReznik1/bilibot.git
cd bilibot
pip install -r Requirements.txt
```

### 3. 配置初始化

复制脱敏配置模板：
```bash
cp config.example.json config.json
```
> 💡 强烈建议启动 Web 面板后，在「系统设置」里直接扫码登录与可视化配置。

### 4. 一键启动 (Windows / 终端)

**方式 A：使用预置批处理脚本（推荐）**
- 双击 `start_web.bat` 启动 Web 控制面板（浏览器访问 `http://127.0.0.1:5000`，默认密码 `admin()`）。
- 双击 `start_bot.bat` 启动后台常驻监听服务（负责评论、楼中楼回复与私信守护）。
- 双击 `start_watch.bat` 可手动触发一次主动刷视频与评价。

**方式 B：命令行启动**
```bash
# 终端 1：启动主守护进程
python ai.py

# 终端 2：启动 Web 控制面板
python local-chat.py
```

---

## 🧪 自动化测试与质量保障

本项目包含覆盖核心特性的完整自动化测试套件，确保重构后的逻辑高度稳健：

```bash
python -m unittest discover tests
```

- `tests/test_enhanced_replies.py`：验证楼中楼 `root/parent` 参数拆分与 @消息 去重机制。
- `tests/test_proactive_filtering_and_fallback.py`：验证多标点智能切分、排除词拦截与全站热门降级。
- `tests/test_user_management_edit.py`：验证用户卡片编辑、UID 变更连带记忆迁移与主人防删保护。
- `tests/test_owner_sync_and_mentions.py`：验证动态主人数据自愈对齐与视频推荐 @ 目标选择器。
- `tests/test_private_messages.py`：验证私信时间戳过滤、站内视频卡片解析与防钓鱼外链隔离。

---

## 📜 开源协议与免责声明

### 开源协议 (License)
本项目采用 [MIT License](LICENSE) 开源，允许任何个人或团队自由学习、修改和分发，但需保留原作者版权声明及本声明。

### 免责声明 (Disclaimer)
1. 本项目仅供 Python 自动化与 AI Agent 架构研究交流，严禁用于任何商业牟利、恶意爬虫、网络攻击或侵犯他人隐私之用途。
2. 使用本项目需自觉遵守《哔哩哔哩弹幕网用户使用协议》及国家相关法律法规。因使用不当导致账号被风控、封禁等后果，均由使用者自行承担。
3. 请妥善保管好个人凭证（API 密钥、Cookies 等），严禁公开分享包含真实个人凭证与敏感数据的 `config.json` 或 `data/` 目录。

---

## 💡 鸣谢与第三方开源项目声明

本项目站在开源社区巨人的肩膀上构建，衷心致谢以下优秀的开源项目与技术规范：

| 开源项目 / 依赖规范 | 许可证类型 | 官方主页 / 仓库 | 说明与用途 |
| :--- | :---: | :--- | :--- |
| **bilibili-ai-bot** | MIT | [chenluQwQ/bilibili-ai-bot](https://github.com/chenluQwQ/bilibili-ai-bot) | **原项目致敬**：奠定了早期版本的基础框架与原型设计 |
| **bilibili-API-collect** | MIT | [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect) | **协议规范参考**：B站评论/私信/WBI 等核心接口逆向规范与楼中楼协议 |
| **Flask** | BSD-3-Clause | [pallets/flask](https://github.com/pallets/flask) | 轻量级 Web 交互面板与后端管理 RESTful API 驱动 |
| **OpenAI Python SDK** | Apache-2.0 | [openai/openai-python](https://github.com/openai/openai-python) | 标准化 LLM 模型客户端接口抽象与多模态交互 |
| **Requests** | Apache-2.0 | [psf/requests](https://github.com/psf/requests) | 高性能 HTTP 客户端网络请求库 |
| **yt-dlp** | The Unlicense | [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) | 视频与音视频流下载提取与本地帧解析 |
| **Pillow (PIL)** | HPND | [python-pillow/Pillow](https://github.com/python-pillow/Pillow) | 图像处理、动态配图生成与二维码渲染 |
| **qrcode** | BSD-3-Clause | [lincolnloop/python-qrcode](https://github.com/lincolnloop/python-qrcode) | B 站登录二维码生成与终端/Web 呈现 |
| **cryptography** | Apache-2.0 / BSD | [pyca/cryptography](https://github.com/pyca/cryptography) | RSA 加密算法，用于 B 站 Cookie 全自动刷新续期 |
| **Google Generative AI** | Apache-2.0 | [google-gemini/generative-ai-python](https://github.com/google-gemini/generative-ai-python) | Gemini 多模态视觉与轻量化模型支持 |
| **lunardate** | MIT | [yllan/lunardate](https://github.com/yllan/lunardate) | 农历日期算法与节假日动态生成支撑 |

---

## 🌟 Star

如果本项目对你的 AI 探索有所启发，欢迎在 [GitHub](https://github.com/TracyReznik1/bilibot) 点一个 Star ⭐！

欢迎提交 Issue 或 Pull Request，一起让 B 站 AI 伴侣更加生动！
