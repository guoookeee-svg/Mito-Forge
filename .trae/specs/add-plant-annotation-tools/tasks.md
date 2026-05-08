# Tasks

- [x] Task 1: 创建植物线粒体参考蛋白数据库
  - [x] 1.1 创建 `mito_forge/db/plant_mito_proteins.fasta`，包含 31 个核心蛋白编码基因的参考序列
  - [x] 1.2 创建 `mito_forge/db/__init__.py`，提供 `get_db_path()` 函数返回数据库路径
  - [x] 1.3 创建数据库索引构建函数 `ensure_blast_db()`，首次使用时自动 makeblastdb

- [x] Task 2: 实现 BLAST+ 同源注释工具
  - [x] 2.1 创建 `mito_forge/tools/blast_annotator.py`，实现 `run_blast_annotation()` 函数
  - [x] 2.2 实现 blastx 比对逻辑：输入 FASTA + 参考蛋白库 → blastx → 解析输出
  - [x] 2.3 实现 tRNAscan-SE 调用（如可用）注释 tRNA 基因
  - [x] 2.4 实现结果合并和 GFF 文件生成
  - [x] 2.5 处理 BLAST+ 不可用的情况，返回 None 以触发 fallback

- [x] Task 3: 实现 PMGA 工具封装
  - [x] 3.1 创建 `mito_forge/tools/pmga.py`，实现 `run_pmga()` 函数
  - [x] 3.2 支持 conda 环境和 singularity 两种执行方式
  - [x] 3.3 解析 PMGA 输出（GFF/GenBank 格式）
  - [x] 3.4 处理 PMGA 未安装的情况，返回 None 以触发 fallback

- [x] Task 4: 实现 MITOFY 工具封装
  - [x] 4.1 创建 `mito_forge/tools/mitofy.py`，实现 `run_mitofy()` 函数
  - [x] 4.2 调用 mitofy.pl 脚本执行注释
  - [x] 4.3 解析 MITOFY 的 HTML/文本输出，转换为标准 GFF 格式
  - [x] 4.4 处理 MITOFY 未安装的情况，返回 None 以触发 fallback

- [x] Task 5: 重构 AnnotationAgent 植物注释逻辑
  - [x] 5.1 更新 `supported_annotators` 列表，添加 `pmga`、`mitofy`、`blast`
  - [x] 5.2 实现 `_try_pmga_annotation()` 方法
  - [x] 5.3 实现 `_try_mitofy_annotation()` 方法
  - [x] 5.4 实现 `_try_blast_annotation()` 方法
  - [x] 5.5 重构 `run_annotation()` 的植物路径：PMGA → MITOFY → BLAST+ → Basic
  - [x] 5.6 更新 GeSeq 为可选工具（不再作为植物默认路径）
  - [x] 5.7 改进 `_run_basic_annotation()` 的植物路径，生成真实 GFF 文件

- [x] Task 6: 更新工具选择逻辑
  - [x] 6.1 更新 `mito_forge/utils/selection.py`，植物注释工具推荐顺序：PMGA > MITOFY > BLAST+ > GeSeq > Basic
  - [x] 6.2 更新 `mito_forge/cli/commands/annotate.py`，CLI 选项添加 `pmga`/`mitofy`/`blast`

- [x] Task 7: 更新 doctor 命令
  - [x] 7.1 在 `mito_forge/cli/commands/doctor.py` 中添加 PMGA/MITOFY/BLAST+/tRNAscan-SE 检测
  - [x] 7.2 为未安装的植物注释工具提供安装建议

- [x] Task 8: 测试验证
  - [x] 8.1 编写 BLAST+ 同源注释的单元测试
  - [x] 8.2 编写 AnnotationAgent 植物注释路径的集成测试
  - [x] 8.3 编写工具 fallback 链的测试
  - [x] 8.4 验证 CLI annotate 命令的植物注释功能

# Task Dependencies
- [Task 2] depends on [Task 1] (BLAST+ 注释需要参考数据库)
- [Task 5] depends on [Task 2, Task 3, Task 4] (AnnotationAgent 需要调用各工具)
- [Task 6] depends on [Task 5] (工具选择逻辑依赖 Agent 实现)
- [Task 7] depends on [Task 3, Task 4] (doctor 检测需要知道工具名称)
- [Task 8] depends on [Task 5, Task 6, Task 7] (测试在实现完成后进行)
- [Task 1] 和 [Task 3] 和 [Task 4] 可并行执行
