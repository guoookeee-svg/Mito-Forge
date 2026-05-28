"""
Mito-Forge CLI 主入口 (LangGraph Edition)
"""
import click
from pathlib import Path
import os
from .commands.pipeline import pipeline, status
from .commands.doctor import doctor
from .commands.config import config
from .commands.model import model
from .commands.agents import agents
from .commands.qc import qc
from .commands.assembly import assembly
from .commands.annotate import annotate
from .commands.tools_setup import tools_group
from .commands.resume import resume
from .commands.knowledge import knowledge_group

class MitoGroup(click.Group):
    """自定义分组：默认仅显示核心命令；--expert 时显示全部命令"""
    core_commands = {"pipeline", "status", "doctor", "menu", "run"}

    def list_commands(self, ctx):
        names = super().list_commands(ctx)
        expert_on = False
        if ctx:
            if getattr(ctx, "params", None) and ctx.params.get("expert"):
                expert_on = True
            elif getattr(ctx, "obj", None) and ctx.obj.get("expert"):
                expert_on = True
        if not expert_on and os.environ.get("MITO_EXPERT") == "1":
            expert_on = True
        if expert_on:
            return names
        return [n for n in names if n in self.core_commands]

def _expert_cb(ctx, param, value):
    if value:
        os.environ["MITO_EXPERT"] = "1"
        ctx.ensure_object(dict)
        ctx.obj["expert"] = True
    return value

@click.group(cls=MitoGroup)
@click.version_option(version="0.2.0", prog_name="mito-forge")
@click.option("--lang", type=click.Choice(["zh","en"]), default="zh", help="输出语言")
@click.option("--expert", is_flag=True, is_eager=True, expose_value=True, callback=_expert_cb, help="显示高级命令")
@click.pass_context
def cli(ctx, lang, expert):
    """
    🧬 Mito-Forge: 基于 LangGraph 的智能线粒体基因组组装工具

    一个使用多智能体协作的线粒体基因组分析流水线：

    \b
    • Supervisor Agent: 智能分析数据并制定执行策略
    • QC Agent: 自动质量控制和数据清理  
    • Assembly Agent: 多工具组装策略选择
    • Annotation Agent: 基因功能注释
    • Report Agent: 综合结果报告生成

    支持状态机编排、检查点恢复、失败重试等高级功能。
    """
    if lang:
        os.environ["MITO_LANG"] = lang
    ctx.ensure_object(dict)
    if ctx.invoked_subcommand is None:
        _menu(ctx)

cli.add_command(pipeline, name="pipeline")
cli.add_command(status, name="status") 
cli.add_command(doctor, name="doctor")
cli.add_command(config, name="config")
cli.add_command(model, name="model")
cli.add_command(agents, name="agents")
cli.add_command(qc, name="qc")
cli.add_command(assembly, name="assembly")
cli.add_command(annotate, name="annotate")
cli.add_command(tools_group, name="tools")
cli.add_command(resume, name="resume")
cli.add_command(knowledge_group, name="knowledge")

@cli.command()
@click.pass_context
def run(ctx, **kwargs):
    """运行流水线 (pipeline 命令的别名)"""
    ctx.invoke(pipeline, **kwargs)

@cli.command()
@click.pass_context
def menu(ctx):
    """进入交互式菜单"""
    _menu(ctx)


def _menu(ctx):
    """简单交互式菜单，不需用户记命令行参数"""
    lang = os.getenv("MITO_LANG", "zh")
    texts = {
        "zh": {
            "title": "=== Mito-Forge 菜单 ===",
            "run_pipeline": "1) 运行流水线",
            "agents": "2) 智能体管理",
            "doctor": "3) 系统诊断",
            "config": "4) 配置管理",
            "status_checkpoint": "5) 查看流水线状态（检查点）",
            "exit": "6) 退出",
            "choose": "请选择功能编号",
            "prompt_checkpoint": "请输入检查点文件路径",
            "bye": "已退出。",
            "invalid": "无效选择，请重试。"
        },
        "en": {
            "title": "=== Mito-Forge Menu ===",
            "run_pipeline": "1) Run pipeline",
            "agents": "2) Manage agents",
            "doctor": "3) System doctor",
            "config": "4) Config management",
            "status_checkpoint": "5) View pipeline status (checkpoint)",
            "exit": "6) Exit",
            "choose": "Choose a number",
            "prompt_checkpoint": "Enter checkpoint file path",
            "bye": "Bye.",
            "invalid": "Invalid choice, please retry."
        }
    }
    t = texts.get(lang, texts["zh"])
    while True:
        click.echo(t["title"])
        click.echo(t["run_pipeline"])
        click.echo(t["agents"])
        click.echo(t["doctor"])
        click.echo(t["config"])
        click.echo(t["status_checkpoint"])
        click.echo(t["exit"])
        choice = click.prompt(t["choose"], type=int, default=1)

        if choice == 1:
            from .main_menu_refactored import run_pipeline_interactive
            run_pipeline_interactive(ctx, lang, t, pipeline)
            continue
        elif choice == 2:
            detailed = click.confirm("显示详细信息?", default=False)
            ctx.invoke(agents, status=True, detailed=detailed, restart=None)
        elif choice == 3:
            click.echo()
            click.echo("=" * 50)
            click.echo("系统诊断" if lang != "en" else "System Doctor")
            click.echo("=" * 50)
            auto_fix = click.confirm(
                "是否自动安装缺失的工具?" if lang != "en" else "Auto-install missing tools?",
                default=False
            )
            from mito_forge.utils.toolcheck import DEFAULT_TOOLS
            default_tools_str = ",".join(DEFAULT_TOOLS)
            ctx.invoke(doctor, tools=default_tools_str, fix=auto_fix)
            click.echo()
            input("按 Enter 继续..." if lang != "en" else "Press Enter to continue...")
        elif choice == 4:
            ctx.invoke(config)
        elif choice == 5:
            cp_default = str(Path("user_analysis_results") / "work" / "checkpoint.json")
            cp = click.prompt(t["prompt_checkpoint"], default=cp_default)
            ctx.invoke(status, checkpoint=cp)
        elif choice == 6:
            click.echo(t["bye"])
            break
        else:
            click.echo(t["invalid"])

main = cli

if __name__ == "__main__":
    cli()
