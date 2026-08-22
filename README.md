# Mira 1.0.0 — 发行版

中国数学建模竞赛智能体 skill。四个阶段：**analysis → modeling → implementation → paper**。
本目录是与个人项目数据解耦后的**可共享版本**（约 5 MB，无需任何个人语料即可运行基础流程）。

## 目录结构

```
mira-1.0.0/
├── mira/                  ← 主 skill（SKILL.md + scripts/ + references/ + tests/ + benchmarks/ + assets/）
├── MathModelAgent/        ← 上游模板快照（382 个模板，可选引用；paper 阶段 LaTeX 模板用）
├── dsh-agent-preset/
│   └── mira/              ← DeepSeek Harness（DSH）的 agent 定义（可选）
├── README.md
└── .gitignore
```

## 安装

**Codex**（OpenAI）：
```
mira/  →  ~/.codex/skills/mira/          （全局）
      或  <你的项目>/.codex/skills/mira/ （项目级，优先级更高）
```

**Claude Code**：
```
mira/  →  ~/.claude/skills/mira/  或 <你的项目>/.claude/skills/mira/
```

**DeepSeek Harness (DSH)**：
```
mira/ → ~/.agents/skills/mira/     （技能，所有会话可见）
agent preset：把 dsh-agent-preset/mira/ 整个目录放到 ~/.dsh/.agent-presets/mira/
             （agent.cordis.yml 自动被识别；新建会话时选择 agent "Mira"）
```

## 路径约定（与原版的重要差异）

原版所有示例命令写死了作者机器路径，本版统一改为占位符：

| 占位符 | 含义 |
|---|---|
| `$PROJECT_ROOT` | 你的竞赛项目根目录（`planning/`、`code/`、`paper/` 等产物都在它下面） |
| `<external-skill-checkout>` | 外部 skill 审计时由你提供的 checkout 路径 |
| `MIRA_TEX_BIN` 环境变量 | 你的 TeX bin 目录；未设置时自动探测常见安装位置与 PATH |

示例：`python "scripts/select_workflow_lane.py" --root $PROJECT_ROOT --write`（脚本请按 skill 实际安装路径补齐，或用 DSH skill loader 的相对基底引用）。

## 与原版的差异（干净化清单）

- 所有本机绝对路径（个人语料/项目目录，含转义形式）→ `$PROJECT_ROOT`（82 个文件）；
- 删除知识卡中的 99 行"来源出处"行（个人语料库路径、优秀论文 ID、提取笔记引用），知识内容保留；
- 移除 `benchmarks/` 中基于私有语料的 B136 外部校准条目；
- 删除 `materials/`（个人论文提取笔记）；
- TeX 工具链候选路径移植化（Windows/Linux/macOS 常见位置 + `MIRA_TEX_BIN`）；
- **不包含**：个人语料库、竞赛材料、运行产物——如需语料支持，请同学自己提供。

## 上游与许可

Mira 引用了以下开源项目（仅署名与许可证，未携带其代码/语料）：

- `sweetcornna/mathodology`（MIT）— 活图质检方法
- `handsomeZR-netizen/mathmodel-skill`（MIT）
- `Yuan1z0825/nature-skills`（MIT）
- `jihe520/MathModelAgent` — 模板来源（见 `MathModelAgent/TEMPLATE_SOURCE.md` 版本说明）

完整 NOTICE/LICENSE 见 `mira/references/third-party/`；分发时请保留。

## 验证

```
cd mira && python -m pytest tests/     # 需要 python3
```

或直接在 Codex/Claude/DSH 中开一个新项目让 agent 走一遍四阶段。

## GitHub / 分享

把本目录推上去即可（约 5 MB）。`.gitignore` 已排除 zip 与缓存。
建议 README 保留本文件，删除任何提及个人仓库的内容。
