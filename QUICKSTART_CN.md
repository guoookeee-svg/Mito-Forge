# 🚀 Mito-Forge 快速启动指南

## 欢迎使用 Mito-Forge！

这是一个基于 LangGraph 多智能体架构的智能化线粒体基因组组装与分析平台。

## 一、立即开始 (3 步走)

### 第 1 步: 进入项目目录

```bash
cd /home/engine/project
```

### 第 2 步: 运行系统诊断

```bash
./run_project.sh doctor
```

这会检查所有依赖工具的安装状态。

### 第 3 步: 探索功能

```bash
# 查看帮助
./run_project.sh help

# 进入交互式菜单
./run_project.sh menu

# 查看所有命令
./run_project.sh --expert --help
```

## 二、基本命令速查

| 命令 | 说明 | 示例 |
|-----|------|------|
| `help` | 显示帮助 | `./run_project.sh help` |
| `--version` | 显示版本 | `./run_project.sh --version` |
| `doctor` | 系统诊断 | `./run_project.sh doctor` |
| `menu` | 交互式菜单 | `./run_project.sh menu` |
| `pipeline` | 完整流水线 | `./run_project.sh pipeline --reads data.fastq` |
| `qc` | 质量控制 | `./run_project.sh qc --reads data.fastq` |
| `assembly` | 基因组组装 | `./run_project.sh assembly --input qc_output/` |
| `annotate` | 基因注释 | `./run_project.sh annotate --input assembly_output/` |
| `config` | 配置管理 | `./run_project.sh config --show` |
| `model` | 模型管理 | `./run_project.sh model list` |
| `agents` | 智能体管理 | `./run_project.sh agents --status` |

## 三、快速示例

### 示例 1: 查看版本和帮助

```bash
# 查看版本
./run_project.sh --version

# 查看基础命令
./run_project.sh help

# 查看高级命令
./run_project.sh --expert --help
```

### 示例 2: 系统诊断

```bash
# 基础诊断
./run_project.sh doctor

# 检查工具详情
./run_project.sh doctor --check-tools

# 交互式安装向导
./run_project.sh doctor --interactive
```

### 示例 3: 运行完整流水线

```bash
# 准备数据（如果有的话）
ls data/

# 运行流水线（替换为实际的数据文件）
./run_project.sh pipeline \
    --reads data/your_reads.fastq \
    --output results/analysis_001 \
    --threads 4

# 交互式模式
./run_project.sh pipeline \
    --reads data/your_reads.fastq \
    --interactive
```

### 示例 4: 分步执行

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

### 示例 5: 配置 LLM 模型

```bash
# 查看当前模型
./run_project.sh model current

# 列出所有可用模型配置
./run_project.sh model list

# 添加 OpenAI 模型
./run_project.sh model add openai \
    --model gpt-4o-mini \
    --api-key "your-api-key-here"

# 添加本地 Ollama 模型
./run_project.sh model add ollama \
    --model qwen2.5:7b \
    --api-base http://localhost:11434

# 测试模型连接
./run_project.sh model test openai
```

### 示例 6: 模拟运行（无需外部工具）

```bash
# 设置模拟模式
export MITO_SIM="qc=ok,assembly=ok,annotate=ok"

# 运行模拟流水线
./run_project.sh pipeline \
    --reads demo.fastq \
    --output sim_results/

# 清除模拟设置
unset MITO_SIM
```

## 四、常用场景

### 场景 1: 第一次使用

```bash
# 1. 检查环境
./run_project.sh doctor

# 2. 查看帮助
./run_project.sh help

# 3. 进入交互式菜单探索
./run_project.sh menu
```

### 场景 2: 完整分析流程

```bash
# 1. 准备数据
mkdir -p data/
# 将您的测序数据放入 data/ 目录

# 2. 运行完整流水线
./run_project.sh pipeline \
    --reads data/sample.fastq \
    --output results/sample_001 \
    --kingdom animal \
    --threads 8 \
    --interactive

# 3. 查看结果
ls -lh results/sample_001/
```

### 场景 3: 测试和开发

```bash
# 1. 使用模拟模式测试
MITO_SIM="qc=ok,assembly=ok,annotate=ok" \
./run_project.sh pipeline --reads test.fastq

# 2. 运行测试套件
.venv/bin/pytest tests/ -v

# 3. 检查代码质量
.venv/bin/black mito_forge/ --check
```

### 场景 4: 故障排查

```bash
# 1. 运行系统诊断
./run_project.sh doctor

# 2. 检查配置
./run_project.sh config --show

# 3. 查看智能体状态
./run_project.sh agents --status --detailed

# 4. 检查日志（如果有的话）
ls -lh work/logs/
```

## 五、环境变量

### 常用环境变量

```bash
# 设置语言（中文）
export MITO_LANG=zh

# 设置语言（英文）
export MITO_LANG=en

# 启用模拟模式
export MITO_SIM="qc=ok,assembly=ok,annotate=ok"

# 启用内存优化
export MITO_MEMORY_OPTIMIZE=1

# 设置日志级别
export MITO_LOG_LEVEL=DEBUG
```

### 使用示例

```bash
# 英文界面运行
MITO_LANG=en ./run_project.sh pipeline --reads data.fastq

# 模拟模式运行
MITO_SIM="qc=ok,assembly=ok" ./run_project.sh pipeline --reads test.fastq

# 调试模式运行
MITO_LOG_LEVEL=DEBUG ./run_project.sh doctor
```

## 六、项目文件说明

### 核心文件

- `run_project.sh` - 便捷运行脚本（推荐使用）⭐
- `README.md` - 完整项目文档
- `README_RUN.md` - 详细运行指南
- `QUICKSTART_CN.md` - 本快速启动指南
- `PROJECT_SETUP_SUMMARY.md` - 配置总结

### 目录结构

- `mito_forge/` - 主源代码
- `data/` - 示例数据
- `examples/` - 示例脚本
- `tests/` - 测试套件
- `work/` - 工作目录（运行时创建）
- `results/` - 结果输出（运行时创建）
- `.venv/` - Python 虚拟环境

## 七、获取更多帮助

### 查看文档

```bash
# 查看运行指南
cat README_RUN.md

# 查看技术细节
cat TECHNICAL_DETAILS.md

# 查看更新日志
cat CHANGELOG.md
```

### 命令行帮助

```bash
# 主帮助
./run_project.sh --help

# 特定命令帮助
./run_project.sh pipeline --help
./run_project.sh qc --help
./run_project.sh assembly --help

# 高级命令帮助
./run_project.sh --expert --help
```

### 交互式帮助

```bash
# 进入交互式菜单
./run_project.sh menu

# 系统诊断
./run_project.sh doctor

# 查看智能体状态
./run_project.sh agents --status
```

## 八、常见问题

### Q1: 如何运行项目？

**A**: 使用便捷脚本：
```bash
./run_project.sh [命令] [参数...]
```

### Q2: 外部工具都没安装怎么办？

**A**: 可以使用模拟模式：
```bash
MITO_SIM="qc=ok,assembly=ok,annotate=ok" ./run_project.sh pipeline --reads test.fastq
```

### Q3: 如何安装外部工具？

**A**: 使用交互式安装向导：
```bash
./run_project.sh doctor --interactive
```
或使用 conda:
```bash
conda install -c bioconda spades flye unicycler fastqc blast
```

### Q4: 如何配置 LLM 模型？

**A**: 使用 model 命令：
```bash
./run_project.sh model add openai --model gpt-4o-mini --api-key YOUR_KEY
```

### Q5: 如何查看帮助？

**A**: 多种方式：
```bash
./run_project.sh help            # 脚本帮助
./run_project.sh --help          # CLI 帮助
./run_project.sh pipeline --help # 命令帮助
./run_project.sh menu            # 交互式菜单
```

## 九、快速参考卡

### 最常用的 5 个命令

```bash
# 1. 查看帮助
./run_project.sh help

# 2. 系统诊断
./run_project.sh doctor

# 3. 交互式菜单
./run_project.sh menu

# 4. 运行流水线
./run_project.sh pipeline --reads data.fastq

# 5. 查看状态
./run_project.sh agents --status
```

### 三种运行方式

```bash
# 方式 1: 便捷脚本（推荐）
./run_project.sh [命令]

# 方式 2: Python 模块
.venv/bin/python -m mito_forge [命令]

# 方式 3: 已安装命令
.venv/bin/mito-forge [命令]
```

## 十、开始使用

现在就开始探索 Mito-Forge 吧！

```bash
# 第一步：查看版本
./run_project.sh --version

# 第二步：系统诊断
./run_project.sh doctor

# 第三步：探索功能
./run_project.sh menu
```

---

**版本**: v0.2.0  
**更新**: 2025-01-09  
**状态**: ✅ 就绪

**🎯 提示**: 从交互式菜单开始是最简单的方式！

```bash
./run_project.sh menu
```

**🌟 祝您使用愉快！**
