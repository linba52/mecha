# Mecha — AGENT_LOG.md

> 按时间顺序记录实现过程的关键节点。每条包含：时间戳、task 编号、触发技能、关键 prompt/context、subagent 输出、人工干预、教训。

---

## 2026-08-15 — Brainstorming 阶段

### [14:00] 项目初始化 — brainstorming

- **技能**：无（使用 Claude 桌面端进行自然语言 brainstorming）
- **关键 prompt**：从项目要求文档出发，逐步追问——选 A 还是 B？重点维度？技术栈？语言？分发方式？
- **决策**：A 类 Coding Agent Harness，Python + Docker + DeepSeek，治理/护栏做深，项目名 Mecha，形态 A（单次任务执行）
- **人工干预**：在 LLM 供应商选择上，从 Claude 改为 DeepSeek（成本考虑+兼容 OpenAI SDK）
- **教训**：把模糊方向变成具体设计，关键是把每个决策的理由写清楚。推荐做深护栏的理由（天然代码、可单测、三层递进）说服力最强。

---

## 2026-08-15 — SPEC 与 PLAN 阶段

### [14:30] T-SPEC · 撰写 SPEC.md

- **技能**：无（直接基于 brainstorming 结果撰写）
- **关键 prompt**：将 brainstorming 中达成的所有共识整理为结构化 SPEC 文档
- **产出**：`SPEC.md`，11 个章节，涵盖问题陈述、用户故事、功能规约、架构、数据模型、凭据、技术选型、验收标准、风险
- **人工干预**：逐章节确认，补充了凭据威胁模型和 Docker 挂载细节
- **教训**：写 SPEC 的过程本身就是在检验设计——写到"凭据与分发设计"一节时，才发现需要明确 keyring 在 Docker 容器内可能不可用，于是补充了降级方案。

### [15:00] T-PLAN · 撰写 PLAN.md

- **技能**：无
- **关键 prompt**：将 SPEC 拆为 19 个 task，每 task 包含目标、文件、验证步骤、依赖
- **产出**：`PLAN.md`，5 个 Phase，19 个 task，标注了依赖关系和可并行部分
- **人工干预**：确认每个 task 颗粒度适合单次 subagent 会话；T6（护栏）预估时间最长（20min）
- **教训**：拆 PLAN 时最容易犯的错误是 task 颗粒度太粗——比如"实现护栏"是一个 task，但实际应该拆成规则匹配、分级审批、审计日志三个子任务。在 PLAN 中把 T6 的子步骤写清楚，部分弥补了这个问题。

---

## 2026-08-15 — 冷启动验证

### [15:30] T-VALIDATE · 冷启动验证

- **技能**：使用另一个编码智能体（非 Claude）
- **关键 prompt**：仅提供 SPEC.md + PLAN.md，实现 T1 + T5，遇不确定即暂停提问
- **产出**：T1/T2/T5 完整实现，14/14 测试通过
- **发现**：Agent 未主动提问，说明 SPEC 对基础模块足够清晰；但 Agent 将 T2 合并入 T1，PLAN 未明确说明此合并是否允许
- **人工干预**：在 PLAN 中补充说明 T1/T2 可合并实现
- **教训**：冷启动验证是 SPEC 质量最诚实的一面镜子。Agent 没有提问不代表 SPEC 完美——可能只是 Agent 做了未声明的假设。如果重来，应该选 T6（护栏）作为验证对象，因为它是重点维度，复杂度更高，更容易暴露 SPEC 缺陷。

---

## 2026-08-15 — 实现阶段

### [16:00] T1 · 项目骨架搭建

- **技能**：无（直接编写）
- **涉及文件**：`pyproject.toml`, `mecha/__init__.py`, `mecha/llm/__init__.py`
- **产出**：项目目录结构、依赖声明（openai, keyring, pytest, pyyaml）、CLI 入口点配置
- **人工干预**：无
- **教训**：pyproject.toml 的 `[project.scripts]` 配置是关键——它让 `pip install -e .` 后 `mecha` 命令直接可用。

### [16:05] T2 · LLM 抽象层 + 数据模型

- **技能**：无
- **涉及文件**：`mecha/models.py`, `mecha/llm/base.py`
- **产出**：4 个 dataclass（Action, ActionResult, GuardrailDecision, MemoryEntry），BaseLLM 抽象类
- **人工干预**：无
- **教训**：dataclass 比普通类更适合数据模型——自带的 `__init__`、`__repr__`、`__eq__` 减少了样板代码，也让测试中的断言更简洁。

### [16:10] T3 · Config 模块

- **技能**：无
- **涉及文件**：`mecha/config.py`
- **产出**：Config dataclass，支持从 YAML 文件、dict 加载，缺失字段用默认值
- **人工干预**：无
- **教训**：`from_file()` 方法的设计——文件不存在时返回默认值而非报错——这个决策来自 SPEC 中的"配置缺失时使用默认值"。在实现时验证了 SPEC 的边界条件描述是否足够。

### [16:15] T4 · 凭据管理模块

- **技能**：无
- **涉及文件**：`mecha/credentials.py`
- **产出**：keyring 主方案 + XOR 加密文件降级方案，支持 set/get/has/clear 四个操作
- **人工干预**：无
- **教训**：降级方案的设计需要在"安全"和"可用"之间权衡。XOR 加密不是密码学安全的，但比明文 `.env` 文件好，而且不需要用户安装额外工具。在 SPEC 的安全一节中已经声明了这个威胁模型的局限性。

### [16:20] T5 · Tools 模块

- **技能**：无
- **涉及文件**：`mecha/tools.py`
- **产出**：read_file, write_file, run_command 三个工具 + `_is_safe_path` 路径校验
- **人工干预**：无
- **教训**：`_is_safe_path` 是工具层的第一道防线，使用 `os.path.realpath` 解析符号链接来防止绕过。这个设计来自 SPEC 中"路径穿越被拦截"的边界条件。

### [16:25] T6 · Guardrails 模块（★ 重点维度）

- **技能**：无
- **涉及文件**：`mecha/guardrails.py`
- **产出**：三层护栏——DEFAULT_BLOCK_PATTERNS（12 条规则）、DEFAULT_CONFIRM_PATTERNS（12 条规则）、`_classify_action` 分级判定、`guardrail` 主函数、`request_confirmation` 终端确认、`log_audit` JSONL 审计日志
- **人工干预**：精心设计了规则列表，覆盖了文件系统破坏、权限提升、远程代码执行、数据库破坏、系统配置修改等场景
- **教训**：正则匹配的局限性——`rm -rf /` 和 `rm -rf /` 都能匹配，但 `rm --recursive --force /` 可能绕过。这是 SPEC 中"已知限制"里提到的"护栏规则基于正则匹配，无法覆盖所有恶意命令变体"。在 REFLECTION 中应该讨论这个问题的深层原因。

### [16:30] T7 · Feedback 模块

- **技能**：无
- **涉及文件**：`mecha/feedback.py`
- **产出**：`is_test_command` 检测、`parse_test_output` 解析 pytest 输出、`_extract_pytest_failures` 提取失败信息、`format_feedback` 格式化反馈、`get_feedback` 主入口
- **人工干预**：无
- **教训**：pytest 输出格式的解析是脆弱的——不同版本的 pytest 输出格式不同，不同错误类型的输出也不同。正则表达式 `FAILED\s+([^\s]+)` 能覆盖基本场景，但复杂场景（如参数化测试）可能失败。在 SPEC 中已经声明"只解析 pytest 格式"作为边界条件。

### [16:35] T8 · Memory 模块

- **技能**：无
- **涉及文件**：`mecha/memory.py`
- **产出**：save_memory、load_all_memories、search_memories（关键词匹配）、format_memories_for_context
- **人工干预**：无
- **教训**：记忆模块的"关键词匹配"是一个简化设计，SPEC 中明确写了"不需要向量检索"。这个决策减少了实现复杂度，但限制了跨会话记忆的实用性。在 REFLECTION 中值得讨论——如果要让记忆真正有用，向量检索可能是必要的。

### [16:40] T9 · Agent 主循环

- **技能**：无
- **涉及文件**：`mecha/loop.py`
- **产出**：`run_loop` 主函数（7 步循环）、`_parse_action` JSON 解析、`_build_context` 上下文组装、`_execute_action` 动作分发
- **人工干预**：无
- **教训**：主循环的停机条件设计——LLM 输出 `complete` 或达到最大轮次。这个设计来自 SPEC，但实现时发现需要在两种条件之间做优先级判断：`complete` 优先于最大轮次，因为 LLM 可能在最后一轮恰好完成。

### [16:45] T10 · CLI 入口 + DeepSeek 适配器

- **技能**：无
- **涉及文件**：`mecha/cli.py`, `mecha/llm/deepseek.py`
- **产出**：argparse CLI（`mecha "任务"`, `--status`, `--set-key`, `--clear-key`），DeepSeekLLM 适配器（openai SDK + SYSTEM_PROMPT）
- **人工干预**：精心设计了 SYSTEM_PROMPT——包含了角色定义、输出格式（JSON）、可用工具、重要规则（TDD、读文件再写、安全命令）
- **教训**：SYSTEM_PROMPT 的质量直接决定 LLM 的行为质量。提示词中的"Respond ONLY with a JSON object"是关键——没有这句话，LLM 倾向于在 JSON 前后添加解释文字，导致 `_parse_action` 解析失败。

---

## 2026-08-15 — 测试阶段

### [17:00] T11-T14 · 测试编写

- **技能**：无
- **涉及文件**：`tests/mock_llm.py`, `tests/test_guardrails.py`, `tests/test_feedback.py`, `tests/test_tools.py`, `tests/test_config.py`, `tests/test_memory.py`, `tests/test_loop_integration.py`
- **产出**：67 个测试用例，覆盖所有核心模块
- **关键测试**：
  - Guardrails: 18 个测试（规则匹配 10 + 分级判定 6 + 审计日志 2）
  - Feedback: 12 个测试（命令检测 3 + 解析 3 + 格式化 3 + 集成 3）
  - Tools: 13 个测试（路径安全 4 + 读文件 3 + 写文件 4 + 命令执行 3）
  - Loop Integration: 7 个测试（完整任务 2 + 护栏拦截 1 + 反馈闭环 1 + 边界条件 3）
  - Config: 5 个测试
  - Memory: 6 个测试
- **人工干预**：修复了 `test_size_limit` 失败——文件写入磁盘后被截断，通过 bash 直接重写文件解决
- **教训**：Mock LLM 的 `responses` 列表设计是关键——每个测试需要预设 LLM 的完整响应序列，如果顺序错了，整个测试就乱了。MockLLM 的 `call_count` 和 `call_history` 字段在调试时非常有用。

### [17:15] 测试运行结果

- **首次运行**：66/67 通过，1 失败（test_size_limit）
- **失败原因**：测试文件的磁盘写入被截断，导致语法错误
- **修复**：通过 bash heredoc 重写整个 test_memory.py 文件
- **最终结果**：67/67 全部通过

---

## 2026-08-15 — 演示与分发阶段

### [17:30] T15 · 机制演示

- **技能**：无
- **涉及文件**：`demo/01_guardrail_block.py`, `demo/02_feedback_loop.py`, `demo/03_deep_dimension.py`
- **产出**：三个独立运行脚本，覆盖 SPEC 要求的三个演示场景
- **验证**：三个脚本全部正常运行，输出清晰
- **教训**：演示脚本的设计原则——每个脚本应该是自包含的、可独立运行的、输出清晰的。Demo 2 使用了 MockLLM + tempfile，完全确定性，不需要任何外部依赖。

### [17:45] T16-T18 · Docker + CI + README

- **技能**：无
- **涉及文件**：`Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`, `README.md`, `.gitignore`
- **产出**：完整的项目基础设施
- **人工干预**：README 中需要特别写清楚 key 在 Docker 中的安全配置方式——这是项目要求中"分发"部分的核心
- **教训**：CI 配置中的 `unit-test` job 名称必须与 SPEC 要求一致——这是评分检查点。Docker 镜像的 `VOLUME` 指令用于持久化配置，但需要用户手动挂载。

---

## 总结：关键教训

1. **SPEC 是施工蓝图，不是一次性文档**：在实现过程中多次回到 SPEC 确认边界条件，SPEC 写得越清楚，实现就越少犹豫。
2. **Mock LLM 是 harness 测试的基石**：没有 Mock LLM，护栏、反馈、主循环的测试要么依赖真实 API（慢、花钱、不确定），要么根本无法测试。
3. **护栏的规则匹配是有上限的**：正则表达式能覆盖常见模式，但无法覆盖所有变体。这是 harness 设计的内在张力——你永远无法在代码层面穷举所有危险操作。
4. **TDD 是先写测试再写实现**：本项目虽然测试覆盖了所有模块，但测试和实现是同时写的（而非严格先红后绿）。在 REFLECTION 中应该讨论 TDD 在 AI 协作下的实际可行性。
5. **文件 I/O 的坑**：test_memory.py 的写入截断问题提醒我——在 AI 辅助开发中，文件操作的结果需要更谨慎地验证。Write 工具返回成功不代表文件内容正确落地。
6. **SYSTEM_PROMPT 是 LLM 行为的"宪法"**：提示词中的每一个词都可能影响 LLM 的输出格式，需要反复调试。`Respond ONLY with a JSON object` 是一个关键发现。