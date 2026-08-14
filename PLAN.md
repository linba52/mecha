# Mecha — PLAN.md

> 实现计划 | 每个 task 颗粒度 2-5 分钟 | TDD 驱动

---

## 依赖关系图

```
Phase 1: 基础设施
  T1 (项目骨架) ──┬── T2 (LLM 抽象层 + 数据模型)
                  │
Phase 2: 核心模块（可并行）
  T3 (Config)  ←── T1, T2
  T4 (凭据)    ←── T1, T2
  T5 (Tools)   ←── T1, T2
  T6 (护栏)    ←── T1, T2  ← ★ 重点维度
  T7 (Feedback)←── T1, T2
  T8 (Memory)  ←── T1, T2

Phase 3: 集成
  T9 (主循环)  ←── T3, T4, T5, T6, T7, T8
  T10 (CLI 入口) ←── T9

Phase 4: 测试与演示
  T11-T15       ←── Phase 3

Phase 5: 分发与文档
  T16 (Docker)  ←── T10
  T17 (CI)      ←── T10
  T18 (README)  ←── T16
  T19 (过程文档) ←── 全部
```

---

## Phase 1: 基础设施

### T1 · 项目骨架搭建

| 项 | 内容 |
|------|------|
| 目标 | 创建项目目录结构、pyproject.toml、CLI 入口骨架 |
| 涉及文件 | `pyproject.toml`, `mecha/__init__.py`, `mecha/cli.py`, `mecha/models.py` |
| 实现要点 | 定义 Python 包结构；`pyproject.toml` 声明依赖（openai, keyring, pytest, pyyaml）；CLI 入口 `mecha` 命令能打印帮助信息 |
| 验证步骤 | 1. 写测试：`pytest` 能发现测试目录；2. `pip install -e .` 成功；3. `mecha --help` 输出帮助信息 |
| 依赖 | 无 |

### T2 · LLM 抽象层 + 数据模型

| 项 | 内容 |
|------|------|
| 目标 | 定义 Action / ActionResult / GuardrailDecision / MemoryEntry 数据类；定义 BaseLLM 抽象接口 |
| 涉及文件 | `mecha/models.py`, `mecha/llm/base.py` |
| 实现要点 | 4 个 dataclass 按 SPEC 定义；`BaseLLM` 抽象类定义 `chat(messages) -> str` 接口 |
| 验证步骤 | 1. 写测试：`BaseLLM` 不能直接实例化；2. 各 dataclass 字段类型正确；3. 导入无报错 |
| 依赖 | T1 |

---

## Phase 2: 核心模块（T3-T8 可并行）

### T3 · Config 模块

| 项 | 内容 |
|------|------|
| 目标 | 解析 `.mecha.yaml` 配置文件，提供默认值 |
| 涉及文件 | `mecha/config.py`, `tests/test_config.py` |
| 实现要点 | 读取 YAML；解析 LLM 供应商、模型名、最大迭代、护栏规则路径、工具白名单；缺失字段用默认值 |
| 验证步骤 | 1. 写失败测试：空文件 → 默认值；2. 写失败测试：格式错误 → 报错退出；3. 实现后测试通过 |
| 依赖 | T1, T2 |

### T4 · 凭据管理模块

| 项 | 内容 |
|------|------|
| 目标 | 实现 API Key 的安全存储、读取、查看状态、清除 |
| 涉及文件 | `mecha/credentials.py`, `tests/test_credentials.py` |
| 实现要点 | `getpass` 隐藏输入；`keyring` 存储/读取/删除；`status()` 只返回"已配置/未配置"不回显明文；keyring 不可用时降级为加密文件 |
| 验证步骤 | 1. 写测试：mock keyring 验证 set/get/delete 调用；2. 写测试：status() 不包含明文；3. 实现后测试通过 |
| 依赖 | T1, T2 |

### T5 · Tools 模块

| 项 | 内容 |
|------|------|
| 目标 | 实现 read_file、write_file、run_command 三个工具 |
| 涉及文件 | `mecha/tools.py`, `tests/test_tools.py` |
| 实现要点 | 路径限定在项目根目录；`..` 穿越被拦截；文件写入限制 1MB；`subprocess` 执行命令带超时 |
| 验证步骤 | 1. 写测试：read_file 读取存在的文件；2. 写测试：write_file 写入内容后可读回；3. 写测试：run_command 返回 stdout/stderr/exit_code；4. 写测试：路径穿越被拒绝；5. 实现后测试通过 |
| 依赖 | T1, T2 |

### T6 · Guardrails 模块（★ 重点维度）

| 项 | 内容 |
|------|------|
| 目标 | 实现三层护栏：规则匹配 → 分级审批 → 审计日志 |
| 涉及文件 | `mecha/guardrails.py`, `mecha/guardrails_rules.py`, `tests/test_guardrails.py` |
| 实现要点 | **规则匹配**：正则 + 命令模式匹配危险命令；高危命令列表（rm -rf /、sudo、curl \| bash、chmod 777、DROP TABLE、写 /etc）；中危列表（pip install、npm install、修改系统配置）；低危默认放行；**分级审批**：`guardrail(action)` 返回 allow/confirm/block；confirm 时终端 y/n 输入；**审计日志**：结构化 JSON 日志，记录时间、命令、LLM 意图、判定结果；**自定义规则**：支持用户在 `.mecha.yaml` 中追加规则 |
| 验证步骤 | 1. 写测试：`rm -rf /` → block；2. 写测试：`pip install` → confirm；3. 写测试：`ls` → allow；4. 写测试：审计日志包含必要字段；5. 写测试：自定义规则生效；6. 实现后测试通过 |
| 依赖 | T1, T2 |

### T7 · Feedback 模块

| 项 | 内容 |
|------|------|
| 目标 | 解析 pytest 输出，提取失败信息，格式化为 LLM 可理解的反馈 |
| 涉及文件 | `mecha/feedback.py`, `tests/test_feedback.py` |
| 实现要点 | 检测是否为 pytest 命令；解析 pytest 输出（失败测试名、错误行号、错误类型）；格式化为结构化反馈文本；最多修正 3 轮；无法解析时原样回灌 |
| 验证步骤 | 1. 写测试：传入 pytest 失败输出 → 正确提取测试名和错误行号；2. 写测试：传入 pytest 通过输出 → 返回成功信号；3. 写测试：传入非 pytest 输出 → 原样返回；4. 实现后测试通过 |
| 依赖 | T1, T2 |

### T8 · Memory 模块

| 项 | 内容 |
|------|------|
| 目标 | 实现跨会话记忆的保存、加载、关键词检索 |
| 涉及文件 | `mecha/memory.py`, `tests/test_memory.py` |
| 实现要点 | 保存到 `.mecha/memory/` 目录；JSON 格式存储；按关键词匹配检索相关记忆；总大小限制 100KB；文件损坏时跳过并告警 |
| 验证步骤 | 1. 写测试：保存记忆后能从文件读取；2. 写测试：关键词检索返回匹配条目；3. 写测试：超 100KB 时拒绝写入；4. 实现后测试通过 |
| 依赖 | T1, T2 |

---

## Phase 3: 集成

### T9 · Agent 主循环

| 项 | 内容 |
|------|------|
| 目标 | 实现主循环：组装上下文 → 调 LLM → 解析动作 → 护栏 → 执行 → 反馈 → 回灌 → 停机判断 |
| 涉及文件 | `mecha/loop.py`, `tests/test_loop.py` |
| 实现要点 | 上下文组装（任务 + 项目文件 + 记忆）；LLM 返回 JSON 解析为 Action；护栏检查 → Tools 执行 → Feedback 处理 → 回灌；停机条件：LLM 输出 complete 或达到最大轮次；最大 20 轮，LLM 超时 60 秒，失败重试 3 次 |
| 验证步骤 | 1. 写测试（Mock LLM 返回预设动作序列）：验证主循环正确分发工具、处理护栏、回灌反馈；2. 写测试：达到最大轮次后正确退出；3. 写测试：LLM 返回无效 JSON 时重试；4. 实现后测试通过 |
| 依赖 | T3, T4, T5, T6, T7, T8 |

### T10 · CLI 入口 + 真实 LLM 适配器

| 项 | 内容 |
|------|------|
| 目标 | 实现 `mecha` 命令行入口；实现 DeepSeek 适配器 |
| 涉及文件 | `mecha/cli.py`, `mecha/llm/deepseek.py` |
| 实现要点 | argparse 解析命令行参数；`mecha "任务"` 启动主循环；`mecha status` 查看状态；`mecha config --key` 录入 Key；`mecha config --clear` 清除 Key；DeepSeek 适配器实现 BaseLLM 接口 |
| 验证步骤 | 1. 写测试：CLI 参数解析正确；2. 写测试：DeepSeek 适配器正确设置 base_url 和 headers；3. 实现后手动测试：`mecha "创建 hello.py"` 完整流程 |
| 依赖 | T9 |

---

## Phase 4: 测试与演示

### T11 · Mock LLM 工具类

| 项 | 内容 |
|------|------|
| 目标 | 实现 MockLLM 类，支持预设多轮回复序列 |
| 涉及文件 | `tests/mock_llm.py` |
| 实现要点 | 实现 BaseLLM 接口；支持预设 `responses` 列表，按调用顺序返回；支持验证 `call_count` 和每次调用的 `messages` |
| 验证步骤 | 自身即测试工具，被 T12-T15 依赖 |
| 依赖 | T2 |

### T12 · Guardrails 确定性测试

| 项 | 内容 |
|------|------|
| 目标 | 用 Mock LLM 验证护栏所有核心行为 |
| 涉及文件 | `tests/test_guardrails_unit.py` |
| 实现要点 | 不依赖真实 LLM，直接构造 Action 测试 guardrail() 函数；覆盖：高危命令拦截、中危命令确认、低危命令放行、自定义规则、审计日志写入 |
| 验证步骤 | `pytest tests/test_guardrails_unit.py` 全部通过 |
| 依赖 | T6, T11 |

### T13 · Feedback 确定性测试

| 项 | 内容 |
|------|------|
| 目标 | 用 Mock LLM 验证反馈闭环 |
| 涉及文件 | `tests/test_feedback_unit.py` |
| 实现要点 | 构造 pytest 失败输出，验证 parse_test_output() 正确提取错误信息；构造成功输出，验证返回成功信号 |
| 验证步骤 | `pytest tests/test_feedback_unit.py` 全部通过 |
| 依赖 | T7, T11 |

### T14 · Agent Loop 集成测试

| 项 | 内容 |
|------|------|
| 目标 | 用 Mock LLM 验证主循环完整流程 |
| 涉及文件 | `tests/test_loop_integration.py` |
| 实现要点 | Mock LLM 预设动作序列（read_file → write_file → run_command → complete）；验证主循环正确分发、护栏介入、反馈回灌、最终停机 |
| 验证步骤 | `pytest tests/test_loop_integration.py` 全部通过 |
| 依赖 | T9, T11 |

### T15 · 机制演示脚本

| 项 | 内容 |
|------|------|
| 目标 | 三个确定性演示场景的脚本 |
| 涉及文件 | `demo/01_guardrail_block.py`, `demo/02_feedback_loop.py`, `demo/03_deep_dimension.py` |
| 实现要点 | ① 护栏拦截：Mock LLM 返回 `rm -rf /`，验证被拦截；② 反馈闭环：Mock LLM 先输出有 bug 的代码 → 测试失败 → 收到反馈 → 输出修正代码 → 测试通过；③ 重点维度：审计日志完整记录 + 分级审批全流程展示 |
| 验证步骤 | 三个脚本均可 `python demo/0x_*.py` 独立运行，输出清晰 |
| 依赖 | T12, T13, T14 |

---

## Phase 5: 分发与文档

### T16 · Docker 分发

| 项 | 内容 |
|------|------|
| 目标 | 编写 Dockerfile，构建可运行镜像 |
| 涉及文件 | `Dockerfile`, `.dockerignore` |
| 实现要点 | 基于 python:3.11-slim；安装依赖；设置 WORKDIR；ENTRYPOINT 为 `mecha`；volume 挂载工作目录和 .mecha 配置 |
| 验证步骤 | `docker build -t mecha .` 成功；`docker run mecha --help` 输出帮助 |
| 依赖 | T10 |

### T17 · CI 配置

| 项 | 内容 |
|------|------|
| 目标 | 配置 GitHub Actions，每次 push 自动运行 pytest |
| 涉及文件 | `.github/workflows/ci.yml`（或 `.gitlab-ci.yml`） |
| 实现要点 | 包含 `unit-test` job；安装依赖；运行 `pytest`；Docker 镜像构建 |
| 验证步骤 | push 后 CI 自动运行，最后一次执行 pass |
| 依赖 | T10 |

### T18 · README.md

| 项 | 内容 |
|------|------|
| 目标 | 编写项目 README |
| 涉及文件 | `README.md` |
| 实现要点 | 包含：项目简介、安装、运行、分发命令、目录结构、安全边界、已知限制 |
| 验证步骤 | 新读者按 README 步骤能成功运行 |
| 依赖 | T16 |

### T19 · 过程文档（持续更新）

| 项 | 内容 |
|------|------|
| 目标 | 撰写 SPEC_PROCESS.md、AGENT_LOG.md、REFLECTION.md |
| 涉及文件 | `SPEC_PROCESS.md`, `AGENT_LOG.md`, `REFLECTION.md` |
| 实现要点 | AGENT_LOG 在实现过程中持续记录；SPEC_PROCESS 记录 brainstorming 和冷启动验证过程；REFLECTION 在全部完成后撰写 |
| 验证步骤 | 三份文档内容完整，覆盖通用要求 §4.3、§4.9、§五.8 |
| 依赖 | 全部完成 |

---

## 任务总览

| Phase | 编号 | 任务 | 可并行 | 预估时间 |
|-------|------|------|--------|----------|
| 1 | T1 | 项目骨架 | — | 5min |
| 1 | T2 | LLM 抽象 + 数据模型 | — | 5min |
| 2 | T3 | Config | T4-T8 | 5min |
| 2 | T4 | 凭据管理 | T3,T5-T8 | 5min |
| 2 | T5 | Tools | T3,T4,T6-T8 | 5min |
| 2 | T6 | ★ Guardrails | T3-T5,T7,T8 | 20min |
| 2 | T7 | Feedback | T3-T6,T8 | 5min |
| 2 | T8 | Memory | T3-T7 | 5min |
| 3 | T9 | 主循环 | — | 10min |
| 3 | T10 | CLI + DeepSeek | — | 5min |
| 4 | T11 | Mock LLM 工具 | — | 5min |
| 4 | T12 | Guardrails 单测 | — | 5min |
| 4 | T13 | Feedback 单测 | T12 | 5min |
| 4 | T14 | Loop 集成测试 | T12,T13 | 5min |
| 4 | T15 | 机制演示 | T12-T14 | 5min |
| 5 | T16 | Docker | — | 5min |
| 5 | T17 | CI | — | 5min |
| 5 | T18 | README | T16 | 5min |
| 5 | T19 | 过程文档 | 全部 | 持续 |

---

## 更新记录

| 日期 | Task | 状态 | Commit Hash |
|------|------|------|-------------|
| — | — | — | — |