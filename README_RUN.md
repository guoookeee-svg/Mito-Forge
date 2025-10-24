# 🧬 Mito-Forge 项目运行指南

本文档提供 Mito-Forge 项目的快速运行指南。

## 📋 前提条件

- ✅ Python 3.9+ 已安装
- ✅ 虚拟环境已配置在 `.venv/` 目录
- ✅ 所有依赖已安装（通过 `uv pip install` 或 `pip install`）

## 🚀 快速开始

### 方法一：使用便捷运行脚本（推荐）

我们提供了一个便捷的运行脚本 `run_project.sh`，可以快速运行项目：

```bash
# 显示帮助信息
./run_project.sh help

# 显示版本信息
./run_project.sh version

# 系统诊断（检查依赖工具）
./run_project.sh doctor

# 进入交互式菜单
./run_project.sh menu

# 运行完整流水线
./run_project.sh pipeline --reads your_data.fastq --output results/

# 查看其他命令帮助
./run_project.sh pipeline --help
./run_project.sh qc --help
./run_project.sh assembly --help
```

### 方法二：直接使用 Python 命令

```bash
# 激活虚拟环境（可选）
source .venv/bin/activate

# 运行项目
.venv/bin/python -m mito_forge [命令] [参数...]

# 示例
.venv/bin/python -m mito_forge --version
.venv/bin/python -m mito_forge doctor
.venv/bin/python -m mito_forge menu
```

### 方法三：使用已安装的命令（如果已安装）

```bash
# 如果项目已通过 pip install -e . 安装
mito-forge --version
mito-forge doctor
mito-forge pipeline --reads data.fastq
```

## 📚 常用命令

### 1. 系统诊断

检查项目依赖和外部工具：

```bash
./run_project.sh doctor

# 检查工具并显示详细信息
./run_project.sh doctor --check-tools

# 进入交互式安装向导
./run_project.sh doctor --interactive
```

### 2. 交互式菜单

进入交互式菜单系统，通过图形化界面选择操作：

```bash
./run_project.sh menu
```

### 3. 完整流水线分析

运行从质控到注释的完整分析流程：

```bash
# 基础分析
./run_project.sh pipeline --reads your_reads.fastq --output results/

# 交互式分析（推荐）
./run_project.sh pipeline --reads your_reads.fastq --interactive

# 指定物种类型和线程数
./run_project.sh pipeline \
    --reads your_reads.fastq \
    --kingdom animal \
    --threads 8 \
    --output results/

# 从检查点恢复
./run_project.sh pipeline --resume work/checkpoint.json
```

### 4. 单独的分析步骤

#### 质量控制（QC）

```bash
./run_project.sh qc --reads reads.fastq --output qc_results/
```

#### 基因组组装

```bash
./run_project.sh assembly --input qc_results/ --output assembly_results/
```

#### 基因注释

```bash
./run_project.sh annotate --input assembly_results/ --output annotation_results/
```

### 5. 配置管理

```bash
# 显示当前配置
./run_project.sh config --show

# 设置参数
./run_project.sh config --set threads=16

# 重置配置
./run_project.sh config --reset
```

### 6. LLM 模型配置

```bash
# 列出可用模型
./run_project.sh model list

# 添加 OpenAI 模型
./run_project.sh model add openai --model gpt-4o-mini --api-key YOUR_KEY

# 添加本地 Ollama 模型
./run_project.sh model add ollama --model qwen2.5:7b --api-base http://localhost:11434

# 测试模型连接
./run_project.sh model test openai

# 查看当前模型
./run_project.sh model current
```

### 7. 智能体管理

```bash
# 查看智能体状态
./run_project.sh agents --status

# 查看详细信息
./run_project.sh agents --detailed

# 显示高级命令
./run_project.sh --expert agents --help
```

### 8. 查看流水线状态

```bash
./run_project.sh status --checkpoint work/checkpoint.json
```

## 🧪 模拟运行模式

用于测试和开发，无需实际工具：

```bash
# 完整流程模拟
MITO_SIM="qc=ok,assembly=ok,annotate=ok" ./run_project.sh pipeline --reads demo.fastq

# 错误场景模拟
MITO_SIM="assembly=tool_missing" ./run_project.sh pipeline --reads demo.fastq
```

## 🌍 多语言支持

```bash
# 中文界面（默认）
MITO_LANG=zh ./run_project.sh pipeline --reads reads.fastq

# 英文界面
MITO_LANG=en ./run_project.sh pipeline --reads reads.fastq
```

## 📊 示例工作流

### 完整分析流程示例

```bash
# 1. 首先运行系统诊断
./run_project.sh doctor

# 2. 检查有哪些示例数据
ls data/

# 3. 运行完整流水线（如果有示例数据）
./run_project.sh pipeline \
    --reads data/sample.fastq \
    --output results/sample_analysis \
    --threads 4 \
    --interactive

# 4. 查看结果
ls -lh results/sample_analysis/
```

### 分步分析流程示例

```bash
# 步骤 1: 质量控制
./run_project.sh qc \
    --reads data/sample.fastq \
    --output results/01_qc

# 步骤 2: 基因组组装
./run_project.sh assembly \
    --input results/01_qc \
    --output results/02_assembly

# 步骤 3: 基因注释
./run_project.sh annotate \
    --input results/02_assembly \
    --output results/03_annotation
```

## 🔍 故障排除

### 问题 1: 虚拟环境未找到

**症状**: `虚拟环境不存在` 错误

**解决方案**:
```bash
# 创建新的虚拟环境
python3 -m venv .venv

# 安装依赖
.venv/bin/pip install -e .
```

### 问题 2: 缺少依赖模块

**症状**: `ModuleNotFoundError` 错误

**解决方案**:
```bash
# 使用 uv 安装缺失的包（如果使用 uv）
uv pip install langgraph-checkpoint-sqlite

# 或使用标准 pip
.venv/bin/pip install langgraph-checkpoint-sqlite
```

### 问题 3: 权限错误

**症状**: `Permission denied` 错误

**解决方案**:
```bash
# 确保运行脚本有执行权限
chmod +x run_project.sh

# 确保输出目录有写权限
mkdir -p results/
chmod 755 results/
```

### 问题 4: 外部工具缺失

**症状**: 系统诊断显示大量工具缺失

**解决方案**:
```bash
# 使用交互式安装向导
./run_project.sh doctor --interactive

# 或手动安装 (使用 conda)
conda install -c bioconda spades flye unicycler fastqc blast
```

## 📁 项目结构

```
/home/engine/project/
├── mito_forge/          # 主要源代码
│   ├── cli/            # 命令行界面
│   ├── core/           # 核心智能体
│   ├── graph/          # LangGraph 工作流
│   ├── tools/          # 工具封装
│   └── utils/          # 工具函数
├── data/               # 示例数据
├── examples/           # 示例脚本
├── tests/              # 测试套件
├── work/               # 工作目录（运行时生成）
├── results/            # 结果输出（运行时生成）
├── .venv/              # 虚拟环境
├── run_project.sh      # 便捷运行脚本 ⭐
└── README.md           # 主要文档
```

## 🛟 获取帮助

```bash
# 查看主帮助
./run_project.sh --help

# 查看特定命令帮助
./run_project.sh pipeline --help
./run_project.sh qc --help
./run_project.sh assembly --help
./run_project.sh annotate --help

# 查看高级命令
./run_project.sh --expert --help
```

## 📞 支持和反馈

- 📖 详细文档: [README.md](README.md)
- 🏗️ 技术细节: [TECHNICAL_DETAILS.md](TECHNICAL_DETAILS.md)
- 🐛 问题报告: [GitHub Issues](https://github.com/your-org/mito-forge/issues)
- 📝 更新日志: [CHANGELOG.md](CHANGELOG.md)

---

**版本**: v0.2.0 | **更新日期**: 2025-01-09 | **状态**: ✅ 就绪

**🌟 如果这个项目对您有帮助，请给个 Star 支持我们！**
