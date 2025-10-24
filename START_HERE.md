# 🎯 从这里开始！

## 👋 欢迎使用 Mito-Forge！

这个项目已经**完全配置好**，可以立即使用。

## ⚡ 3 秒快速开始

```bash
cd /home/engine/project
./run_project.sh menu
```

这将打开交互式菜单，您可以通过图形界面探索所有功能。

## 📚 推荐阅读顺序

### 🚀 快速上手（5分钟）

1. **本文件** - START_HERE.md（您正在阅读）
2. **快速启动** - [QUICKSTART_CN.md](QUICKSTART_CN.md)
3. **运行项目**:
   ```bash
   ./run_project.sh --version
   ./run_project.sh doctor
   ./run_project.sh menu
   ```

### 📖 深入了解（15分钟）

1. **运行指南** - [README_RUN.md](README_RUN.md)
2. **配置总结** - [PROJECT_SETUP_SUMMARY.md](PROJECT_SETUP_SUMMARY.md)
3. **完整文档** - [README.md](README.md)

### 🔧 开发者资源

1. **技术细节** - [TECHNICAL_DETAILS.md](TECHNICAL_DETAILS.md)
2. **安装日志** - [INSTALLATION_LOG.md](INSTALLATION_LOG.md)
3. **任务总结** - [TASK_COMPLETION_SUMMARY.md](TASK_COMPLETION_SUMMARY.md)

## 🎮 立即尝试

### 命令 1: 查看版本

```bash
./run_project.sh --version
```

**预期输出**: `mito-forge, version 0.2.0`

### 命令 2: 系统诊断

```bash
./run_project.sh doctor
```

**说明**: 检查所有依赖工具的安装状态

### 命令 3: 交互式菜单

```bash
./run_project.sh menu
```

**说明**: 打开图形化菜单，探索所有功能

### 命令 4: 查看帮助

```bash
./run_project.sh help
```

**说明**: 显示所有可用命令

### 命令 5: 运行演示

```bash
./demo_commands.sh
```

**说明**: 交互式演示项目的基本功能

## 📊 项目状态一览

| 项目 | 状态 | 说明 |
|-----|------|------|
| 虚拟环境 | ✅ 就绪 | `.venv/` 已配置 |
| Python 依赖 | ✅ 已安装 | 所有核心包已安装 |
| 项目可执行 | ✅ 正常 | 所有命令可用 |
| 运行脚本 | ✅ 已创建 | `run_project.sh` |
| 文档 | ✅ 完整 | 6 个新文档 |
| 外部工具 | ⚠️ 可选 | 15 个工具未安装（可使用模拟模式） |

## 🛠️ 三种运行方式

### 方式 1: 便捷脚本（推荐）⭐

```bash
./run_project.sh [命令] [参数...]
```

**优点**: 
- ✅ 自动检查环境
- ✅ 彩色输出
- ✅ 错误提示清晰

**示例**:
```bash
./run_project.sh --version
./run_project.sh doctor
./run_project.sh menu
```

### 方式 2: Python 模块

```bash
.venv/bin/python -m mito_forge [命令] [参数...]
```

**示例**:
```bash
.venv/bin/python -m mito_forge --version
.venv/bin/python -m mito_forge doctor
```

### 方式 3: 直接命令

```bash
.venv/bin/mito-forge [命令] [参数...]
```

**示例**:
```bash
.venv/bin/mito-forge --version
.venv/bin/mito-forge doctor
```

## 🎯 常用命令速查

```bash
# 显示版本
./run_project.sh --version

# 显示帮助
./run_project.sh help
./run_project.sh --help

# 系统诊断
./run_project.sh doctor

# 交互式菜单
./run_project.sh menu

# 完整流水线
./run_project.sh pipeline --reads data.fastq

# 质量控制
./run_project.sh qc --reads data.fastq

# 基因组组装
./run_project.sh assembly --input qc_output/

# 基因注释
./run_project.sh annotate --input assembly_output/

# 配置管理
./run_project.sh config --show

# 模型管理
./run_project.sh model list

# 智能体管理
./run_project.sh agents --status

# 高级命令
./run_project.sh --expert --help
```

## 💡 使用提示

### 提示 1: 外部工具未安装？

**不用担心！** 项目支持模拟运行模式：

```bash
MITO_SIM="qc=ok,assembly=ok,annotate=ok" ./run_project.sh pipeline --reads test.fastq
```

### 提示 2: 想要完整功能？

安装外部生物信息学工具：

```bash
# 使用交互式向导
./run_project.sh doctor --interactive

# 或使用 conda
conda install -c bioconda spades flye unicycler fastqc blast
```

### 提示 3: 想要配置 AI 功能？

配置 LLM 模型：

```bash
# 添加 OpenAI
./run_project.sh model add openai --model gpt-4o-mini --api-key YOUR_KEY

# 添加本地 Ollama
./run_project.sh model add ollama --model qwen2.5:7b
```

## 📁 新创建的文件

本次配置创建了以下文件来帮助您使用项目：

1. ✅ **run_project.sh** - 便捷运行脚本
2. ✅ **README_RUN.md** - 详细运行指南
3. ✅ **QUICKSTART_CN.md** - 快速启动指南
4. ✅ **PROJECT_SETUP_SUMMARY.md** - 配置总结
5. ✅ **INSTALLATION_LOG.md** - 安装日志
6. ✅ **TASK_COMPLETION_SUMMARY.md** - 任务总结
7. ✅ **START_HERE.md** - 本文件
8. ✅ **demo_commands.sh** - 演示脚本

## 🚀 下一步做什么？

### 选项 A: 快速探索（推荐）

```bash
# 1. 运行演示脚本
./demo_commands.sh

# 2. 进入交互式菜单
./run_project.sh menu

# 3. 阅读快速指南
cat QUICKSTART_CN.md
```

### 选项 B: 立即开始分析

```bash
# 1. 准备数据
mkdir -p data/
# 将您的测序数据放入 data/ 目录

# 2. 运行流水线
./run_project.sh pipeline \
    --reads data/your_reads.fastq \
    --output results/ \
    --interactive

# 3. 查看结果
ls -lh results/
```

### 选项 C: 测试功能

```bash
# 使用模拟模式测试
MITO_SIM="qc=ok,assembly=ok,annotate=ok" \
./run_project.sh pipeline --reads test.fastq --output sim_results/
```

### 选项 D: 深入学习

```bash
# 1. 阅读完整文档
cat README.md

# 2. 查看技术细节
cat TECHNICAL_DETAILS.md

# 3. 运行测试套件
.venv/bin/pytest tests/ -v
```

## ❓ 需要帮助？

### 命令行帮助

```bash
./run_project.sh help              # 基础帮助
./run_project.sh --help            # CLI 帮助
./run_project.sh --expert --help   # 高级命令
./run_project.sh [命令] --help     # 特定命令帮助
```

### 文档帮助

```bash
cat QUICKSTART_CN.md              # 快速启动
cat README_RUN.md                 # 运行指南
cat PROJECT_SETUP_SUMMARY.md     # 配置总结
cat README.md                     # 完整文档
```

### 交互式帮助

```bash
./run_project.sh menu             # 交互式菜单
./demo_commands.sh                # 演示脚本
```

## ✨ 核心特性

- 🧠 **多智能体协作**: 5 个专业智能体协同工作
- 🔄 **LangGraph 状态机**: 智能工作流编排
- 🤖 **LLM 驱动**: 支持多种 AI 模型
- ⚡ **一键式分析**: 完整的自动化流程
- 🛠️ **跨平台**: Windows/Linux/macOS 支持
- 🔍 **智能诊断**: 自动环境检测
- 🛡️ **容错机制**: 断点续跑功能
- 🌍 **多语言**: 中文/英文界面

## 🎊 开始使用！

项目已完全就绪，选择一个选项开始吧：

```bash
# 最简单的开始方式
./run_project.sh menu

# 或者运行演示
./demo_commands.sh

# 或者查看快速指南
cat QUICKSTART_CN.md
```

---

**版本**: v0.2.0  
**状态**: ✅ 完全就绪  
**更新**: 2025-01-09  

**🌟 祝您使用愉快！**

**💡 提示**: 从交互式菜单开始是最简单的方式！

```bash
./run_project.sh menu
```
