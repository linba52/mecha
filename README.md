# Mecha — A Safety-First Coding Agent Harness

Mecha 是一个安全的编码智能体框架，让 LLM 在你的项目里写代码、跑测试、自我修正，同时在代码层面拦截一切危险操作。

## 项目简介

Mecha 是一个 Coding Agent Harness——它把 LLM（DeepSeek）封装成一个能稳定、安全工作的编码系统。核心机制全部由代码实现，不依赖 LLM 的"自觉"。

**核心特性：**

- **WebUI**：提供浏览器端聊天界面，支持多轮对话、实时 token 统计、危险操作拦截
- **对话模式**：CLI 和 WebUI 均支持自然语言多轮对话，跨轮次记忆上下文，可同时聊天和编码
- **三层护栏**：静态规则匹配 → 分级审批（低危放行/中危确认/高危拒绝）→ 审计日志
- **反馈闭环**：自动运行 pytest，测试失败时解析错误并回灌给 LLM 自我修正
- **安全凭据**：API Key 存储在操作系统钥匙串中，绝不写入明文文件
- **Mock 可测**：所有核心机制可用 Mock LLM 做确定性单元测试

## 安装

### Docker（推荐）

```bash
docker pull ghcr.io/<username>/mecha:latest
```

### 从源码安装

```bash
git clone https://github.com/<username>/mecha.git
cd mecha
pip install -e .
```

## 运行

```bash
# 设置 API Key（首次运行前）
mecha --set-key

# WebUI 模式（推荐）：浏览器端聊天界面
mecha-server
# 然后打开 http://127.0.0.1:8080

# 对话模式：终端 REPL，支持多轮对话和编码
mecha

# 单次任务模式：一行命令完成一个任务
mecha "在 src/utils.py 中创建一个日期格式化函数，并写测试"

# 查看状态
mecha --status

# 清除 Key
mecha --clear-key
```

### Docker 运行

```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -v mecha-keyring:/root/.mecha \
  ghcr.io/<username>/mecha:latest \
  "你的任务描述"
```

## 安全边界

### API Key 存储

- **存储位置**：操作系统钥匙串（Windows Credential Manager / macOS Keychain / Linux Secret Service）
- **降级方案**：keyring 不可用时，使用主密码加密的 fallback 文件（`~/.mecha/credentials.enc`）
- **绝不**：写入 `.env`、Git、日志、Shell History
- **状态查看**：`mecha --status` 只显示"已配置/未配置"，不回显明文

### 护栏机制

三个安全等级：

| 等级 | 示例 | 行为 |
|------|------|------|
| 低危 | `ls`, `cat`, `mkdir`, `pytest` | 自动放行 |
| 中危 | `pip install`, `npm install`, `rm temp.txt` | 终端 y/n 确认 |
| 高危 | `rm -rf /`, `sudo`, `curl \| bash`, `DROP TABLE` | 直接拒绝 |

审计日志记录每次动作：时间、命令、LLM 意图、判定结果 → `.mecha/logs/audit.jsonl`

## 运行测试

```bash
# 全部测试（不依赖真实 LLM，不需要网络）
PYTHONPATH=. python -m pytest tests/ -v

# 机制演示
python demo/01_guardrail_block.py    # 护栏拦截危险动作
python demo/02_feedback_loop.py      # 反馈闭环自我修正
python demo/03_deep_dimension.py     # 三层分级审批
```

## 目录结构

```
mecha/
├── mecha/
│   ├── __init__.py
│   ├── models.py          # 数据模型（Action, ActionResult, GuardrailDecision, MemoryEntry）
│   ├── config.py          # 配置文件解析
│   ├── credentials.py     # 凭据管理（keyring + fallback）
│   ├── tools.py           # 工具层（read_file, write_file, run_command）
│   ├── guardrails.py      # 护栏（规则匹配 + 分级审批 + 审计日志）
│   ├── feedback.py        # 反馈闭环（pytest 输出解析）
│   ├── memory.py          # 跨会话记忆
│   ├── loop.py            # Agent 主循环
│   ├── cli.py             # CLI 入口
│   └── llm/
│       ├── __init__.py
│       ├── base.py        # BaseLLM 抽象接口
│       └── deepseek.py    # DeepSeek 适配器
├── tests/
│   ├── mock_llm.py        # Mock LLM（预设响应序列）
│   ├── test_config.py
│   ├── test_guardrails.py
│   ├── test_feedback.py
│   ├── test_tools.py
│   ├── test_memory.py
│   └── test_loop_integration.py
├── demo/
│   ├── 01_guardrail_block.py
│   ├── 02_feedback_loop.py
│   └── 03_deep_dimension.py
├── Dockerfile
├── .github/workflows/ci.yml
├── pyproject.toml
├── SPEC.md
├── PLAN.md
└── README.md
```

## 技术栈

- **语言**：Python 3.11+
- **LLM**：DeepSeek（openai SDK 兼容）
- **凭据**：keyring（操作系统钥匙串）
- **配置**：YAML
- **测试**：pytest
- **分发**：Docker

## 已知限制

- Docker 镜像仅支持 Linux/amd64
- 工作目录通过 volume 挂载，不支持 Windows 路径格式
- �