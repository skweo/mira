# Mira

> 中国数学建模竞赛智能体（agent skill）——四阶段流水线：**analysis → modeling → implementation → paper**，覆盖题意分析、建模推导、可复现代码与证据链、论文编译与交付检查。

## 这是什么

Mira 是一个以 `SKILL.md` 为核心的可安装智能体技能包：

- 四阶段工作流，阶段顺序严格、结果可复现、证据可追溯；
- 116 个 Python 脚本：流程选择、引用路由、阶段门禁、图表质检、论文一致性审计、提交合规等；
- 内置模板（LaTeX / Typst）、benchmark 注册表与分层参考知识卡。

## 安装

**Codex**

```bash
mkdir -p ~/.codex/skills && cp -r mira ~/.codex/skills/mira
```

或复制到项目的 `.codex/skills/`（项目级优先，仅对该项目生效）。

**Claude Code**

```bash
mkdir -p ~/.claude/skills && cp -r mira ~/.claude/skills/mira
```

**DeepSeek Harness (DSH)**

```bash
cp -r mira ~/.agents/skills/mira
```

agent 形态（可选）：把 `dsh-agent-preset/mira/` 复制到 `~/.dsh/.agent-presets/mira/`，新会话选择 agent **Mira**。

## 快速开始

在一个竞赛项目目录中开新会话，直接说“用 mira”，或让 agent 加载该技能：

```bash
python scripts/select_workflow_lane.py --root . --write    # 选择工作流密度
python scripts/route_references.py --root . --stage analysis --write
python scripts/stage_gate.py --root . --stage analysis      # 每阶段结束跑门禁
```

默认输出等级为 `contest_final`（完整可提交论文），需要轻量产出时指定 `quick_draft`。

## 路径约定

本发行版不含任何个人数据与个人语料，示例命令统一使用占位符：

| 占位符 | 含义 |
|---|---|
| `$PROJECT_ROOT` | 你的项目根目录（`planning/`、`code/`、`paper/` 等产物在其下） |
| `<external-skill-checkout>` | 外部 skill 审计的 checkout 路径（按需提供） |
| `MIRA_TEX_BIN` | TeX bin 目录；未设置时自动探测常见安装位置与 PATH |

## 验证

```bash
cd mira && python -m pytest tests/   # 需要 python3
```

或任意支持 skill 的客户端（Codex / Claude Code / DSH）中开一个新项目走一遍四阶段。

## 致谢与许可

Mira 的流程设计、脚本与知识卡为原创实现。活图质检脚本的设计参考了
[sweetcornna/mathodology](https://github.com/sweetcornna/mathodology)（MIT，
署名与许可文本随包保留于 `mira/references/third-party/`）。
如需更多论文模板，可自行从 [jihe520/MathModelAgent](https://github.com/jihe520/MathModelAgent) 获取
（未随本发行版分发；使用前请自行核对其许可条款）。

## 状态

- 当前版本：**1.0.0**（2026-08），为第一个可共享发行版；
- 本仓库现为私有，用于队伍内分享与测评；比赛结束后计划公开；
- 反馈与建议：仓库内提交 issue（私有仓库仅对成员可见）。
