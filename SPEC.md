# Mecha — SPEC.md

> Coding Agent Harness | 对话模式 + 单次任务执行 | Python + DeepSeek + Docker

---

## 1. 问题陈述

**要解决的问题**：开发者使用 AI 辅助编码时，LLM 可能执行危险操作（删除文件、执行恶意命令），且缺乏对 LLM 行为的客观反馈和治理机制。现有 AI 编码工具将安全寄托于提示词约束，而非代码级护栏。

**目标用户**：希望用 AI 辅助编码但担心安全风险的开发者。

**为什么值得做**：当 LLM 能完成大部分编码工作时，工程师的价值落在 harness 的工程层——治理、反馈、上下文、安全。Mecha 通过在代码层面实现护栏、反馈闭环和审计，让开发者能安全地驾驭 LLM 进行编码。

---

## 2. 用户故事

| 编号 | 角色 | 需求 | 目的 |
|------|------|------|------|
| US-1 | 开发者 | 用一行命令描述任务，agent 自动完成编码、测试、修正的全流程 | 提高编码效率 |
| US-2 | 开发者 | agent 在执行危险命令前被拦截，由我确认后再执行 | 避免误删代码或数据 |
| US-3 | 开发者 | agent 写完代码后自动运行测试，测试失败时能根据错误信息修正 | 保证代码质量 |
| US-4 | 开发者 | 首次使用时安全地录入 API Key，Key 不以明文出现在任何文件里 | 保护凭据安全 |
| US-5 | 开发者 | 通过 Docker 一条命令启动 agent，无需手动配置环境 | 降低使用门槛 |

---

## 3. 功能规约

### 3.1 Agent Loop（主循环）

| 项 | 内容 |
|------|------|
| 输入 | 用户任务描述（字符串） |
| 输出 | 任务完成状态 + 结果摘要 |
| 行为 | 1. 组装上下文（任务 + 项目文件 + 记忆）→ 2. 调用 LLM → 3. 解析 LLM 返回的动作 → 4. 护栏检查 → 5. 通过则执行动作 → 6. 结果回灌给 LLM → 7. 判断是否停机 |
| 边界 | 最大迭代 20 轮；LLM 调用超时 60 秒；工作目录限定在项目根目录 |
| 错误处理 | LLM 调用失败重试 3 次；LLM 返回无法解析的动作时，将错误信息回灌并请求重新输出 |

### 3.2 Tools（工具层）

| 项 | 内容 |
|------|------|
| 输入 | 动作指令（类型 + 参数） |
| 输出 | 执行结果（ActionResult） |
| 行为 | 支持三类工具：`read_file(path)`、`write_file(path, content)`、`run_command(command)` |
| 边界 | 工作目录限定项目根目录；文件写入限制 1MB；`..` 路径穿越被拦截 |
| 错误处理 | 文件不存在返回错误信息；命令执行失败返回 stdout + stderr + 退出码 |

### 3.3 Guardrails（护栏，重点维度）

| 项 | 内容 |
|------|------|
| 输入 | 待执行的 Action |
| 输出 | GuardrailDecision（allow / confirm / block） |
| 行为 | 三层递进：① 静态规则匹配危险模式（正则 + 命令解析）→ ② 分级判定（低危放行、中危 y/n 确认、高危直接拒绝）→ ③ 写入审计日志 |
| 边界 | 只拦截 `run_command` 类型动作；支持用户自定义规则文件 |
| 错误处理 | 规则文件解析失败 → 使用默认规则并告警；日志写入失败 → 告警但不阻塞 |

**危险命令分级**：

- 高危（直接拒绝）：`rm -rf /`、`sudo`、`curl | bash`、`chmod 777`、`DROP TABLE`、写 `/etc`
- 中危（y/n 确认）：`pip install`、`npm install`、修改系统配置、访问网络
- 低危（自动放行）：`ls`、`cat`、`mkdir`、`cp`、`git status`、`pytest`

### 3.4 Feedback（反馈闭环）

| 项 | 内容 |
|------|------|
| 输入 | 工具执行结果 |
| 输出 | 格式化的反馈信息（回灌给 LLM） |
| 行为 | 检测到测试命令执行 → 解析 pytest 输出 → 失败则提取错误信息 → 结构化反馈给 LLM → LLM 修正代码 → 重跑测试 |
| 边界 | 最多修正 3 轮；只解析 pytest 格式 |
| 错误处理 | 测试输出无法解析时，将原始输出原样回灌 |

### 3.5 Memory（记忆）

| 项 | 内容 |
|------|------|
| 输入 | 项目根目录 `.mecha/memory/` 下的记忆文件 |
| 输出 | 注入 LLM 上下文的记忆片段 |
| 行为 | 会话结束时自动保存关键决策；下次启动时加载相关记忆注入上下文 |
| 边界 | 记忆文件总大小 100KB；基于关键词匹配检索 |
| 错误处理 | 记忆文件损坏 → 跳过并告警 |

### 3.6 Config（配置）

| 项 | 内容 |
|------|------|
| 输入 | 项目根目录 `.mecha.yaml` |
| 输出 | 解析后的配置对象 |
| 行为 | 定义 LLM 供应商、模型名、最大迭代次数、护栏规则路径、工具白名单 |
| 边界 | 配置缺失时使用默认值；启动时一次性读取 |
| 错误处理 | 配置格式错误 → 打印错误信息并退出 |

---

## 4. 非功能性需求

### 4.1 性能

- 单次 LLM 调用超时 60 秒
- 单次任务总耗时不超过 5 分钟
- 记忆检索不超过 1 秒

### 4.2 安全（凭据威胁模型）

**威胁模型**：假设攻击者能读取进程内存（Key 在调用瞬间存在），但无法读取操作系统钥匙串。Key 绝不写入明文文件、Git、日志、Shell History。

**对策**：

- 存储：操作系统钥匙串（keyring 库），Windows Credential Manager / macOS Keychain / Linux Secret Service
- 传输：HTTPS 调用 DeepSeek API
- 运行时：从钥匙串取出后即时使用，不缓存到变量
- 状态查看：只显示"已配置/未配置"，不回显明文
- 审计：Key 的使用不写入任何日志

### 4.3 可用性

- 单条命令启动：`mecha "任务描述"`
- 首次运行自动引导 Key 录入
- 危险操作时终端 y/n 确认，清晰显示将被执行的命令

### 4.4 可观测性

- 护栏拦截时输出：被拦截的命令、触发规则、判定结果
- 审计日志记录每次动作：时间、命令、LLM 意图、判定结果
- 错误信息包含：错误类型、上下文、建议

---

## 5. 系统架构

### 5.1 组件图

```
用户输入任务
      │
      ▼
┌─────────────┐     ┌──────────────┐
│   Config    │────▶│  Agent Loop  │◀──── Credential Mgr
│ .mecha.yaml │     │  (主循环)     │     (keyring)
└─────────────┘     └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌──────────┐    ┌──────────────┐   ┌──────────┐
   │  Tools   │    │  Guardrails  │   │  Memory  │
   │ read/wri │    │  allow/conf  │   │ .mecha/  │
   │ te/exec  │    │  irm/block   │   │ memory/  │
   └──────────┘    └──────────────┘   └──────────┘
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                  ┌────────────────┐
                  │   Feedback     │
                  │  pytest parser │
                  └────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  LLM Adapter   │
                  │  DeepSeek/Mock │
                  └────────────────┘
```

### 5.2 数据流

1. 用户输入任务 → Config 加载配置 → Agent Loop 启动
2. Loop 组装上下文（任务 + 文件 + Memory）→ LLM Adapter 调用 DeepSeek
3. LLM 返回 Action → Guardrails 判定 → 通过则 Tools 执行
4. Tools 返回 ActionResult → Feedback 解析 → 回灌给 Loop
5. Loop 判断停机或继续迭代 → 会话结束后 Memory 保存

### 5.3 外部依赖

- DeepSeek API（chat/completions）
- keyring（操作系统钥匙串）
- pytest（测试运行与输出解析）
- Docker（分发）

---

## 6. 数据模型

### Action（动作）
```python
@dataclass
class Action:
    type: Literal["read_file", "write_file", "run_command", "complete"]
    params: dict  # {path?, content?, command?}
    reasoning: str  # LLM 解释为什么做这个操作
```

### ActionResult（执行结果）
```python
@dataclass
class ActionResult:
    success: bool
    output: str   # stdout 或文件内容
    error: str    # stderr 或错误信息
    exit_code: int
```

### GuardrailDecision（护栏判定）
```python
@dataclass
class GuardrailDecision:
    level: Literal["allow", "confirm", "block"]
    rule_matched: str  # 触发拦截的规则名
    reason: str        # 拦截原因（给用户看的）
    timestamp: str     # ISO 8601
```

### MemoryEntry（记忆条目）
```python
@dataclass
class MemoryEntry:
    id: str           # UUID
    session_id: str   # UUID
    task: str         # 用户原始任务
    summary: str      # 做了什么、结果如何
    decisions: list   # 关键决策列表
    created_at: str   # ISO 8601
```

---

## 7. 凭据与分发设计

### 7.1 Key 生命周期

| 操作 | 命令 | 实现 |
|------|------|------|
| 录入 | 首次运行自动提示 | `getpass` 隐藏输入 → `keyring.set()` |
| 使用 | 运行时自动读取 | `keyring.get()` → 注入 LLM 调用 |
| 查看 | `mecha status` | 显示"已配置"或"未配置"，不回显明文 |
| 更新 | `mecha config --key` | 重新录入，覆盖旧值 |
| 清除 | `mecha config --clear` | `keyring.delete()` |

### 7.2 分发

**形态**：Docker 容器

**获取**：`docker pull ghcr.io/<username>/mecha:latest`

**运行**：
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -v mecha-keyring:/root/.mecha \
  ghcr.io/<username>/mecha:latest \
  "你的任务描述"
```

**Key 在目标机配置**：首次运行容器时自动提示录入，Key 保存在挂载的 volume 中，重启后有效。

**已知限制**：仅支持 Linux/amd64；需要 Docker 环境；工作目录通过 volume 挂载。

---

## 8. 技术选型与理由

| 层 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | LLM SDK 生态最成熟，开发效率高，学生熟悉 |
| LLM 供应商 | DeepSeek | 兼容 OpenAI SDK，性价比高 |
| LLM SDK | openai (Python) | 改 base_url 即可指向 DeepSeek |
| CLI 框架 | argparse | 标准库，不需要额外依赖 |
| 测试 | pytest | Python 标准测试框架 |
| 凭据存储 | keyring | 跨平台钥匙串，非明文 |
| 配置格式 | YAML | 可读性好，Python 原生支持 |
| 分发 | Docker | 一条命令启动，无需配置环境 |
| 部署 | GitHub Release | 方案一，仅 CLI |

---

## 9. 领域与机制设计（A 类专项）

### 9.1 领域映射

Coding 领域映射到四类机制：

- **反馈信号**：pytest 测试结果（pass/fail + 错误行号 + 错误类型），确定性、可回灌
- **危险动作**：shell 命令（三级：高危直接拒绝、中危 y/n 确认、低危自动放行）
- **所需工具**：read_file、write_file、run_command（三个足够覆盖编码全流程）
- **记忆需求**：项目约定、历史决策、代码库结构（关键词匹配，不需要向量检索）

### 9.2 重点维度：治理（护栏）

选择护栏作为 main contribution 的理由：

1. 天然是代码而非提示词——规则匹配、分级判定、审计日志每层都是确定性逻辑
2. 最容易满足"移除 LLM 后还能单测验证"——传 `Action(command="rm -rf /")`，断言被拦截，每次都成立
3. 三层递进结构体现工程深度
4. 对应机制演示场景一：护栏拦截危险动作

### 9.3 实现方式（机制必须是代码）

- 规则匹配：Python 正则 + 命令模式解析，不是提示词
- 分级审批：状态机（allow → confirm → block），不是"请 LLM 注意安全"
- 审计日志：结构化 JSON 日志，每条包含时间、命令、LLM 意图、判定结果
- 测试：Mock LLM 返回预设危险动作，验证 `guardrail()` 拦截，不依赖真实 LLM

---

## 10. 验收标准

| 编号 | 功能 | 判定标准 |
|------|------|----------|
| AC-1 | 主循环 | 给定"创建 hello.py 输出 Hello World"，5 轮内完成，文件内容正确 |
| AC-2 | 工具-读文件 | 读取项目中任意文件，返回内容正确 |
| AC-3 | 工具-写文件 | 创建和修改文件，写入内容与预期一致 |
| AC-4 | 工具-执行命令 | 执行 shell 命令，返回 stdout/stderr/exit_code |
| AC-5 | 护栏-拦截 | LLM 输出 `rm -rf /` 时，护栏直接拒绝，命令不执行 |
| AC-6 | 护栏-确认 | LLM 输出 `pip install` 时，护栏提示 y/n 确认 |
| AC-7 | 护栏-放行 | LLM 输出 `ls` 时，护栏自动放行并记录日志 |
| AC-8 | 反馈闭环 | 注入语法错误，harness 自动跑测试 → 发现失败 → 修正 → 重跑通过 |
| AC-9 | 记忆 | 任务完成后关键决策保存到 `.mecha/memory/`；下次启动可加载 |
| AC-10 | 凭据 | 首次运行无 Key 时提示录入；`mecha status` 不显示明文；`mecha config --clear` 可清除 |
| AC-11 | Mock LLM 测试 | 不连网、不调 DeepSeek，`pytest` 一键跑通所有核心机制测试 |
| AC-12 | 分发 | `docker build && docker run` 在全新机器上可启动 |
| AC-13 | CI | GitHub Actions 每次 push 自动运行 `pytest`，最后一次 pass |

---

## 11. 风险与未决问题

| 风险 | 影响 | 对策 |
|------|------|------|
| LLM 输出格式不稳定 | 主循环无法解析动作 | 解析层容错，失败时回灌错误信息让 LLM 重试 |
| 护栏规则覆盖不全 | 危险命令可能漏网 | 默认拒绝未知命令类型，只允许白名单内的命令类别 |
| Mock LLM 和真实 LLM 行为差异 | Mock 测试通过不代表真实场景正确 | 额外做真实 LLM 手动集成测试 |
| Docker 内 keyring 不可用 | 凭据无法存储 | 检测并降级为加密文件存储（带主密码） |
| DeepSeek API 不可用 | 整个 harness 无法运行 | 提供清晰的错误提示；支持通过配置切换 LLM 供应商 |
| 任务超出 agent 能力 | 无限循环浪费 token | 最大迭代 20 轮硬限制 + �