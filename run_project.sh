#!/bin/bash
# Mito-Forge 项目运行脚本
# 此脚本用于方便地运行 Mito-Forge 项目

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="/home/engine/project"
VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON="${VENV_DIR}/bin/python"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查虚拟环境
check_venv() {
    if [ ! -d "${VENV_DIR}" ]; then
        print_error "虚拟环境不存在: ${VENV_DIR}"
        return 1
    fi
    
    if [ ! -f "${PYTHON}" ]; then
        print_error "Python 可执行文件不存在: ${PYTHON}"
        return 1
    fi
    
    return 0
}

# 显示帮助信息
show_help() {
    cat << EOF
${GREEN}🧬 Mito-Forge 项目运行脚本${NC}

使用方法:
    $0 [命令] [参数...]

常用命令:
    help                    显示此帮助信息
    version                 显示版本信息
    doctor                  系统诊断
    menu                    进入交互式菜单
    pipeline [选项]         运行完整流水线
    qc [选项]              质量控制分析
    assembly [选项]         基因组组装
    annotate [选项]         基因注释
    config [选项]           配置管理
    model [选项]            模型管理
    agents [选项]           智能体管理
    status [选项]           查看状态

示例:
    $0 version              # 显示版本
    $0 doctor               # 系统诊断
    $0 menu                 # 交互式菜单
    $0 pipeline --help      # 查看 pipeline 命令帮助
    $0 pipeline --reads data/sample.fastq --output results/

更多信息请访问: https://github.com/your-org/mito-forge
EOF
}

# 主函数
main() {
    cd "${PROJECT_DIR}" || exit 1
    
    # 检查虚拟环境
    if ! check_venv; then
        print_error "环境检查失败"
        exit 1
    fi
    
    # 如果没有参数或参数是 help，显示帮助
    if [ $# -eq 0 ] || [ "$1" = "help" ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_help
        exit 0
    fi
    
    # 运行命令
    print_info "运行 Mito-Forge: mito_forge $@"
    echo ""
    
    "${PYTHON}" -m mito_forge "$@"
    
    exit_code=$?
    
    echo ""
    if [ $exit_code -eq 0 ]; then
        print_success "命令执行完成"
    else
        print_error "命令执行失败 (退出码: $exit_code)"
    fi
    
    exit $exit_code
}

# 运行主函数
main "$@"
