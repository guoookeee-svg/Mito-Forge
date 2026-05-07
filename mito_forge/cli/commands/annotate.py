"""
Annotate 命令

基因注释分析
"""

import click
from pathlib import Path
from rich.console import Console

from ...core.agents.annotation_agent import AnnotationAgent
from ...core.agents.types import TaskSpec
from ...utils.config import Config
from ...utils.exceptions import MitoForgeError

console = Console()

import os
from ...utils.i18n import t as _it


def _t(key):
    return _it(key, os.getenv("MITO_LANG", "zh"))


def _help(key):
    try:
        return _it(key, os.getenv("MITO_LANG", "zh"))
    except Exception:
        return key

@click.command(help=_help("ann.help.desc"))
@click.argument('input_file', type=click.Path(exists=True))
@click.option('-o', '--output-dir', default='./annotation_results',
              help=_help('ann.opt.output_dir'))
@click.option('-t', '--annotation-tool',
              type=click.Choice(['mitos', 'geseq', 'prokka']),
              default='mitos',
              help=_help('ann.opt.annotation_tool'))
@click.option('-j', '--threads', default=4, type=int,
              help=_help('ann.opt.threads'))
@click.option('--genetic-code', default=2, type=int,
              help=_help('ann.opt.genetic_code'))
@click.option('--reference-db', default='mitochondria',
              help=_help('ann.opt.reference_db'))
@click.pass_context
def annotate(ctx, input_file, output_dir, annotation_tool, threads, genetic_code, reference_db):
    """
    执行基因注释分析
    
    INPUT_FILE: 输入的FASTA文件路径
    
    示例:
        mito-forge annotate contigs.fasta
        mito-forge annotate genome.fasta --annotation-tool mitos --threads 8
    """
    from ...utils.path_validation import validate_file_path
    try:
        validate_file_path(input_file, must_exist=True, allowed_extensions=['.fasta', '.fa', '.fna', '.fas'])
    except ValueError as e:
        console.print(f"\n❌ [bold red]{e}[/bold red]")
        raise SystemExit(1)
    verbose = ctx.obj.get('verbose', False)
    quiet = ctx.obj.get('quiet', False)
    
    try:
        # Simulation hook
        sim = os.getenv("MITO_SIM", "")
        sim_map = dict(kv.split("=", 1) for kv in sim.split(",") if "=" in kv) if sim else {}
        scenario = sim_map.get("annotate")
        if scenario:
            # prepare output dir
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            lang = os.getenv("MITO_LANG", "zh")
            def msg(zh, en): return zh if lang == "zh" else en

            if scenario == "ok":
                if not quiet:
                    console.print(f"\n📝 [bold blue]{_t('ann_title')}[/bold blue]")
                    console.print(f"📁 {_t('input_file')}: {input_file}")
                    console.print(f"📂 {_t('output_dir')}: {output_dir}")
                    console.print(f"🔧 {_t('annotation_tool')}: {annotation_tool}")
                    console.print(f"⚡ {_t('threads')}: {threads}")
                    console.print(f"🧬 {_t('genetic_code')}: {genetic_code}\n")
                    console.print(f"✅ [bold green]{_t('ann_done')}[/bold green]\n")
                    console.print(f"📊 {_t('ann_stats')}:")
                    console.print(f"  • 蛋白编码基因: 13")
                    console.print(f"  • tRNA基因: 22")
                    console.print(f"  • rRNA基因: 2")
                    console.print(f"  • 总基因数: 37")
                    console.print(f"\n📄 {_t('ann_file')}: [link]{output_path}/annotation.gff[/link]")
                    console.print(f"📄 {_t('gb_file')}: [link]{output_path}/annotation.gb[/link]")
                return 0
            elif scenario == "db_missing":
                console.print(f"\n❌ [bold red]{msg('参考数据库缺失或未配置','Reference database missing or not configured')}[/bold red]")
                console.print(msg("请准备/配置 reference-db 后重试",
                                  "Prepare/configure the reference DB and retry"))
                raise SystemExit(1)
            elif scenario == "invalid_genetic_code":
                console.print(f"\n❌ [bold red]{msg('遗传密码表不合法或不匹配','Invalid or mismatched genetic code')}[/bold red]")
                raise SystemExit(1)
            elif scenario == "timeout":
                console.print(f"\n⏱️ [bold red]{msg('执行超时','Execution timeout')}[/bold red]")
                console.print(msg("可减少线程/缩小数据量后重试",
                                  "Try fewer threads or smaller input chunks"))
                raise SystemExit(1)
        if not quiet:
            console.print(f"\n📝 [bold blue]{_t('ann_title')}[/bold blue]")
            console.print(f"📁 {_t('input_file')}: {input_file}")
            console.print(f"📂 {_t('output_dir')}: {output_dir}")
            console.print(f"🔧 {_t('annotation_tool')}: {annotation_tool}")
            console.print(f"⚡ {_t('threads')}: {threads}")
            console.print(f"🧬 {_t('genetic_code')}: {genetic_code}\n")
        
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 配置参数
        config = Config()
        config.update({
            'annotation_tool': annotation_tool,
            'threads': threads,
            'genetic_code': genetic_code,
            'reference_db': reference_db,
            'verbose': verbose
        })
        
        # 初始化注释智能体
        annotation_agent = AnnotationAgent(config)
        
        # 执行注释
        with console.status(f"[bold green]{_t('ann_running')}") if not quiet else console:
            task = TaskSpec(
                task_id="annotate_cli",
                agent_type="annotation",
                inputs={"assembly": str(input_file), "assembly_file": str(input_file), "tool": annotation_tool, "annotator": annotation_tool, "kingdom": "animal"},
                config={
                    "threads": threads,
                    "genetic_code": genetic_code,
                    "reference_db": reference_db,
                    "verbose": verbose
                },
                workdir=str(output_path)
            )
            stage_result = annotation_agent.execute_task(task)
            # 失败处理：若 Agent 返回失败，退出码为 1
            # 失败处理：若 Agent 返回失败，退出码为 1（兼容枚举/字符串）
            status_raw = getattr(stage_result, "status", None)
            status_name = (getattr(status_raw, "name", status_raw) or "").lower()
            success = getattr(stage_result, "success", True)
            if (status_name in {"failed", "error"}) or (success is False):
                raise SystemExit(1)
        
        # 显示结果
        if not quiet:
            console.print(f"✅ [bold green]{_t('ann_done')}[/bold green]\n")
            console.print(f"📊 {_t('ann_stats')}:")
            ann_data = getattr(stage_result, "outputs", {}).get('annotation_results', {})
            console.print(f"  • 蛋白编码基因: {ann_data.get('protein_genes', 'N/A')}")
            console.print(f"  • tRNA基因: {ann_data.get('trna_genes', 'N/A')}")
            console.print(f"  • rRNA基因: {ann_data.get('rrna_genes', 'N/A')}")
            console.print(f"  • 总基因数: {ann_data.get('total_genes', 'N/A')}")
            console.print(f"\n📄 {_t('ann_file')}: [link]{ann_data.get('gff_file', str(output_path / 'annotation.gff'))}[/link]")
            console.print(f"📄 {_t('gb_file')}: [link]{ann_data.get('gb_file', str(output_path / 'annotation.gb'))}[/link]")
        
        return 0
        
    except MitoForgeError as e:
        console.print(f"\n❌ [bold red]错误:[/bold red] {e}")
        if verbose:
            console.print_exception()
        return 1
    except Exception as e:
        console.print(f"\n💥 [bold red]未预期的错误:[/bold red] {e}")
        if verbose:
            console.print_exception()
        return 1