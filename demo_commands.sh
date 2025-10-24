#!/bin/bash
# Mito-Forge 演示命令脚本
# 此脚本展示了项目的基本使用方法

# 设置颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🧬 Mito-Forge 项目演示脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 函数：打印并执行命令
run_demo() {
    echo -e "${BLUE}▶ 演示命令: ${YELLOW}$1${NC}"
    echo ""
    eval "$1"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    read -p "按 Enter 继续下一个演示..."
    echo ""
}

cd /home/engine/project

echo -e "${BLUE}📋 本演示将展示以下命令：${NC}"
echo "  1. 显示版本信息"
echo "  2. 显示帮助信息"
echo "  3. 运行系统诊断"
echo "  4. 查看配置"
echo "  5. 查看智能体状态"
echo "  6. 查看模型配置"
echo ""
read -p "按 Enter 开始演示..."
echo ""

# 演示 1: 版本信息
run_demo "./run_project.sh --version"

# 演示 2: 帮助信息
run_demo "./run_project.sh help"

# 演示 3: 系统诊断
run_demo "./run_project.sh doctor"

# 演示 4: 查看配置
run_demo "./run_project.sh config --show"

# 演示 5: 查看智能体状态
run_demo "./run_project.sh agents --status"

# 演示 6: 查看模型配置
run_demo "./run_project.sh model list"

# 演示 7: 查看所有命令
run_demo "./run_project.sh --expert --help"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✅ 演示完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}💡 更多使用方法请参考：${NC}"
echo "  - README_RUN.md         (详细运行指南)"
echo "  - QUICKSTART_CN.md      (快速启动指南)"
echo "  - PROJECT_SETUP_SUMMARY.md (配置总结)"
echo ""
echo -e "${BLUE}🚀 快速开始：${NC}"
echo "  ./run_project.sh menu   (交互式菜单)"
echo ""
