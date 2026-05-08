# 植物线粒体基因组注释工具集成 Spec

## Why
当前项目对植物(kingdom=plant)线粒体基因组的注释支持严重不足：MITOS 仅支持动物(Metazoan)，GeSeq 是纯 Web 工具需要手动操作且在非交互模式下不可用，`_run_basic_annotation` 的植物路径只是返回硬编码的基因数量（24蛋白基因+22tRNA+3rRNA），完全不产生真实的 GFF 注释文件。植物线粒体基因组研究者无法通过本工具获得任何有意义的注释结果。

## What Changes
- 新增 PMGA (Plant Mitochondrial Genome Annotator) 本地注释工具集成，支持 conda/singularity 安装和命令行调用
- 新增 MITOFY 本地注释工具集成，支持命令行调用
- 新增 BLAST+ 同源注释策略作为植物注释的通用 fallback（无需专用工具即可运行）
- 重构 `AnnotationAgent` 的植物注释工具链选择逻辑：PMGA → MITOFY → BLAST+ 同源注释 → Basic 预设
- 更新 `GeSeqGuide` 为可选的辅助工具而非唯一路径
- 更新 CLI annotate 命令，新增 `pmga`/`mitofy`/`blast` 注释工具选项
- 更新 `selection.py` 工具选择逻辑，根据 kingdom 自动推荐植物注释工具
- 更新 `doctor` 命令，检测植物注释工具的安装状态

## Impact
- Affected specs: annotation_agent, tool_chain_selection, cli_annotate, doctor
- Affected code:
  - `mito_forge/core/agents/annotation_agent.py` — 新增 PMGA/MITOFY/BLAST+ 注释方法
  - `mito_forge/tools/pmga.py` — 新增 PMGA 工具封装
  - `mito_forge/tools/mitofy.py` — 新增 MITOFY 工具封装
  - `mito_forge/tools/blast_annotator.py` — 新增 BLAST+ 同源注释工具
  - `mito_forge/utils/selection.py` — 更新工具选择逻辑
  - `mito_forge/cli/commands/annotate.py` — 更新 CLI 选项
  - `mito_forge/utils/tool_env_manager.py` — 新增 PMGA/MITOFY 环境配置
  - `mito_forge/cli/commands/doctor.py` — 新增植物注释工具检测

## ADDED Requirements

### Requirement: PMGA 本地注释工具集成
系统 SHALL 提供 PMGA (Plant Mitochondrial Genome Annotator) 的本地命令行集成，支持通过 conda 或 singularity 安装并执行植物线粒体基因组注释。

#### Scenario: PMGA 已安装且注释成功
- **WHEN** 用户指定 `kingdom=plant` 且 PMGA 已安装
- **THEN** 系统调用 PMGA 执行注释，解析输出 GFF/GenBank 文件，返回包含基因详情的注释结果

#### Scenario: PMGA 未安装
- **WHEN** 用户指定 `kingdom=plant` 且 PMGA 未安装
- **THEN** 系统自动 fallback 到下一个可用工具（MITOFY → BLAST+ → Basic）

### Requirement: MITOFY 本地注释工具集成
系统 SHALL 提供 MITOFY 的本地命令行集成，MITOFY 使用 BLAST + tRNAscan-SE 对植物线粒体基因组进行注释。

#### Scenario: MITOFY 已安装且注释成功
- **WHEN** 用户指定 `kingdom=plant`，PMGA 不可用，MITOFY 已安装
- **THEN** 系统调用 MITOFY 执行注释，解析 HTML/文本输出，转换为标准 GFF 格式

### Requirement: BLAST+ 同源注释策略
系统 SHALL 提供 BLAST+ 同源注释作为植物线粒体注释的通用 fallback，无需安装专用注释工具即可运行。

#### Scenario: 使用 BLAST+ 同源注释
- **WHEN** 用户指定 `kingdom=plant`，PMGA 和 MITOFY 均不可用，但 BLAST+ 已安装
- **THEN** 系统使用内置的植物线粒体参考蛋白序列数据库，通过 blastx 同源比对注释蛋白编码基因，使用 tRNAscan-SE（如可用）注释 tRNA，生成 GFF 文件

#### Scenario: BLAST+ 也不可用
- **WHEN** 所有专用工具和 BLAST+ 均不可用
- **THEN** 系统使用 Basic 预设注释（基于序列特征的推断注释），并明确告知用户注释结果为低置信度

### Requirement: 植物线粒体参考数据库
系统 SHALL 内置植物线粒体基因组的核心蛋白编码基因参考序列数据库，用于 BLAST+ 同源注释。

#### Scenario: 参考数据库初始化
- **WHEN** 首次使用 BLAST+ 同源注释
- **THEN** 系统在 `~/.mito-forge/db/plant_mito_proteins.fasta` 创建参考数据库，包含至少 24 个核心蛋白编码基因的参考序列

### Requirement: 植物注释工具链自动选择
系统 SHALL 根据 kingdom 和工具可用性自动选择最优的植物注释工具链。

#### Scenario: 自动选择植物注释工具
- **WHEN** `kingdom=plant` 且未显式指定 annotator
- **THEN** 系统按优先级尝试：PMGA → MITOFY → BLAST+ 同源注释 → Basic 预设

### Requirement: CLI 植物注释工具选项
系统 SHALL 在 CLI annotate 命令中支持 `pmga`、`mitofy`、`blast` 作为 `--annotation-tool` 选项。

#### Scenario: 用户指定 PMGA
- **WHEN** 用户执行 `mito-forge annotate input.fasta --annotation-tool pmga`
- **THEN** 系统尝试使用 PMGA 执行注释

### Requirement: Doctor 植物注释工具检测
系统 SHALL 在 `doctor` 命令中检测植物专用注释工具（PMGA、MITOFY）的安装状态。

#### Scenario: 运行 doctor 检测植物工具
- **WHEN** 用户执行 `mito-forge doctor`
- **THEN** 报告中包含 PMGA 和 MITOFY 的安装状态和安装建议

## MODIFIED Requirements

### Requirement: AnnotationAgent 植物注释路径
原实现：植物注释强制走 GeSeq（Web 工具），非交互模式下 fallback 到 Basic 预设（仅返回硬编码数字）。
新实现：植物注释按优先级尝试 PMGA → MITOFY → BLAST+ 同源注释 → Basic 预设，GeSeq 降级为可选的交互式辅助工具。

### Requirement: GeSeqGuide 定位
原实现：GeSeq 是植物注释的唯一路径，非交互模式下直接失败。
新实现：GeSeq 是可选的交互式辅助工具，用户可显式选择 `--annotation-tool geseq` 使用，不再是默认路径。

### Requirement: Basic 注释的植物路径
原实现：仅返回硬编码的基因数量（24/22/3），不生成真实 GFF 文件。
新实现：基于序列长度和植物线粒体基因组特征推断基因位置，生成包含基因结构的 GFF 文件，并标注为低置信度。

## REMOVED Requirements

### Requirement: 植物注释强制 GeSeq 路径
**Reason**: GeSeq 是纯 Web 工具，无法在命令行流水线中自动化执行，不应作为植物注释的唯一路径。
**Migration**: PMGA/MITOFY/BLAST+ 替代 GeSeq 成为植物注释的主要工具，GeSeq 保留为可选的交互式辅助。
