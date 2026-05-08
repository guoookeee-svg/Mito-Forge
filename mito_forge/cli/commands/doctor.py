import click
import os
from pathlib import Path
from ...utils.toolcheck import check_tools, DEFAULT_TOOLS, PLANT_ANNOTATION_TOOLS

def run_checks(base_dir: Path | None = None) -> dict:
    """
    检查 RAG/Mem0 相关依赖与存储可写性，返回结构化结果。
    仅做探测，不抛异常，便于单元测试与 CLI 复用。
    """
    base = Path(base_dir) if base_dir else Path.cwd() / "work"
    chroma_dir = base / "chroma"
    res = {
        "rag": {
            "chromadb": {"available": False, "detail": ""},
            "embedding": {"available": False, "detail": ""},
            "storage": {"path": str(chroma_dir), "writable": False},
        },
        "memory": {
            "mem0": {"available": False, "detail": ""},
        },
    }

    # 检查 chromadb 与 embedding
    try:
        import importlib
        chromadb_mod = importlib.import_module("chromadb")
        # embedding 既可能来自 chromadb.utils.embedding_functions，也可能使用 sentence-transformers
        emb_detail = ""
        emb_available = False
        try:
            ef = importlib.import_module("chromadb.utils.embedding_functions")
            _ = getattr(ef, "SentenceTransformerEmbeddingFunction")
            emb_available = True
            emb_detail = "chromadb.utils.embedding_functions OK"
        except Exception as e1:
            # 退化检查 sentence-transformers 是否存在
            try:
                importlib.import_module("sentence_transformers")
                emb_available = True
                emb_detail = "sentence-transformers OK"
            except Exception as e2:
                emb_detail = f"missing sentence-transformers ({e2})"
        res["rag"]["chromadb"]["available"] = True
        res["rag"]["chromadb"]["detail"] = f"chromadb OK: {getattr(chromadb_mod, '__version__', 'unknown')}"
        res["rag"]["embedding"]["available"] = emb_available
        res["rag"]["embedding"]["detail"] = emb_detail
    except Exception as e:
        res["rag"]["chromadb"]["available"] = False
        res["rag"]["chromadb"]["detail"] = f"module not found or init failed: {e}"
        res["rag"]["embedding"]["available"] = False
        res["rag"]["embedding"]["detail"] = "embedding unavailable due to chromadb missing"

    # 检查存储可写
    try:
        chroma_dir.mkdir(parents=True, exist_ok=True)
        test_file = chroma_dir / ".write_test"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        test_file.unlink(missing_ok=True)
        res["rag"]["storage"]["writable"] = True
    except Exception:
        res["rag"]["storage"]["writable"] = False

    # 检查 mem0
    try:
        import importlib
        mem0_mod = importlib.import_module("mem0")
        # 进一步探测构造是否可用（不必真的操作后端）
        _Mem0 = getattr(mem0_mod, "Mem0", None)
        if _Mem0 is None:
            raise RuntimeError("mem0.Mem0 not found")
        # 尝试轻量构造（可能会失败，保持容错）
        try:
            _ = _Mem0()
            mem_detail = "Mem0 OK"
            available = True
        except Exception as e:
            mem_detail = f"Mem0 import OK but init failed: {e}"
            available = True  # 认为模块可用，初始化问题交给运行时
        res["memory"]["mem0"]["available"] = available
        res["memory"]["mem0"]["detail"] = mem_detail
    except Exception as e:
        res["memory"]["mem0"]["available"] = False
        res["memory"]["mem0"]["detail"] = f"module not found: {e}"

    return res

def print_report(result: dict) -> None:
    """
    将 run_checks 的结果以人类可读形式输出。
    """
    rag = result.get("rag", {})
    mem = result.get("memory", {})

    chroma_ok = rag.get("chromadb", {}).get("available", False)
    emb_ok = rag.get("embedding", {}).get("available", False)
    storage = rag.get("storage", {})
    mem0_ok = mem.get("mem0", {}).get("available", False)

    click.echo(f"RAG/ChromaDB: {'OK' if chroma_ok else 'MISSING'}")
    click.echo(f"Embedding: {'OK' if emb_ok else 'MISSING'}")
    click.echo(f"RAG Storage: {storage.get('path', '')} (writable={storage.get('writable', False)})")
    click.echo(f"Mem0: {'OK' if mem0_ok else 'MISSING'}")


def interactive_install(missing_tools: list, detail: dict):
    """交互式安装向导"""
    import subprocess
    import sys
    
    if not missing_tools:
        click.echo("✅ 所有工具都已安装!")
        return
    
    click.echo("\n" + "=" * 70)
    click.echo("🔧 交互式工具安装向导")
    click.echo("=" * 70)
    
    # 工具分类和优先级
    tool_priority = {
        # 必需工具
        "mitos": {"priority": "必需", "reason": "Annotation阶段必需"},
        # 推荐工具
        "unicycler": {"priority": "推荐", "reason": "Assembly备选工具"},
        "flye": {"priority": "推荐", "reason": "长读长组装"},
        "racon": {"priority": "推荐", "reason": "序列抛光"},
        "pilon": {"priority": "推荐", "reason": "Illumina数据抛光"},
        "medaka": {"priority": "推荐", "reason": "Nanopore数据抛光"},
        "quast": {"priority": "推荐", "reason": "质量评估"},
        # 可选工具
        "nanoplot": {"priority": "可选", "reason": "Nanopore数据QC"},
        "getorganelle": {"priority": "可选", "reason": "细胞器基因组组装"},
        "novoplasty": {"priority": "可选", "reason": "de novo组装"},
        "blast": {"priority": "可选", "reason": "序列比对"},
        # Plant mitochondrial annotation tools
        "pmga": {"priority": "可选", "reason": "植物线粒体基因组注释"},
        "mitofy": {"priority": "可选", "reason": "植物线粒体基因识别"},
        "blastx": {"priority": "可选", "reason": "BLAST+蛋白比对"},
        "tRNAscan-SE": {"priority": "可选", "reason": "tRNA基因预测"},
    }
    
    # 按优先级分组
    critical = [t for t in missing_tools if tool_priority.get(t, {}).get("priority") == "必需"]
    recommended = [t for t in missing_tools if tool_priority.get(t, {}).get("priority") == "推荐"]
    optional = [t for t in missing_tools if tool_priority.get(t, {}).get("priority") == "可选"]
    
    # 让用户选择要安装的工具
    to_install = []
    
    if critical:
        click.echo(f"\n🔴 必需工具 ({len(critical)}个):")
        for tool in critical:
            info = tool_priority.get(tool, {})
            click.echo(f"  • {tool:15s} - {info.get('reason', '')}")
        
        if click.confirm(f"\n是否安装必需工具? (推荐安装)", default=True):
            to_install.extend(critical)
        else:
            click.echo("⚠️  跳过必需工具可能导致部分功能无法使用")
    
    if recommended:
        click.echo(f"\n🟡 推荐工具 ({len(recommended)}个):")
        for tool in recommended:
            info = tool_priority.get(tool, {})
            click.echo(f"  • {tool:15s} - {info.get('reason', '')}")
        
        if click.confirm("\n是否安装所有推荐工具?", default=True):
            to_install.extend(recommended)
        else:
            click.echo("您可以逐个选择:")
            for tool in recommended:
                info = tool_priority.get(tool, {})
                if click.confirm(f"  安装 {tool} ({info.get('reason', '')})?", default=True):
                    to_install.append(tool)
    
    if optional:
        click.echo(f"\n⚪ 可选工具 ({len(optional)}个):")
        for tool in optional:
            info = tool_priority.get(tool, {})
            click.echo(f"  • {tool:15s} - {info.get('reason', '')}")
        
        if click.confirm("\n是否浏览并选择可选工具?", default=False):
            for tool in optional:
                info = tool_priority.get(tool, {})
                if click.confirm(f"  安装 {tool} ({info.get('reason', '')})?", default=False):
                    to_install.append(tool)
    
    if not to_install:
        click.echo("\n您没有选择任何工具,退出安装向导。")
        return
    
    # 选择安装方式
    click.echo("\n" + "=" * 70)
    click.echo("选择安装方式:")
    click.echo("=" * 70)
    click.echo("  [1] Conda安装 (推荐,快速,需要conda环境)")
    click.echo("  [2] 从GitHub下载到项目 (离线可用,但可能较慢)")
    click.echo("  [0] 取消安装")
    
    choice = click.prompt("\n请选择", type=int, default=1)
    
    if choice == 0:
        click.echo("已取消安装。")
        return
    
    elif choice == 1:
        # Conda安装
        click.echo("\n" + "=" * 70)
        click.echo("🚀 开始Conda安装...")
        click.echo("=" * 70)
        
        # 检查conda是否可用
        try:
            result = subprocess.run(["conda", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                click.echo("❌ Conda不可用,请先安装Miniconda或Anaconda")
                click.echo("   下载地址: https://docs.conda.io/en/latest/miniconda.html")
                return
            click.echo(f"✅ Conda版本: {result.stdout.strip()}")
        except FileNotFoundError:
            click.echo("❌ Conda不可用,请先安装Miniconda或Anaconda")
            click.echo("   下载地址: https://docs.conda.io/en/latest/miniconda.html")
            return
        
        # 构建conda安装命令
        conda_packages = []
        for tool in to_install:
            # 特殊处理某些工具名称
            if tool == "nanoplot":
                conda_packages.append("nanoplot")
            elif tool == "blast":
                conda_packages.append("blast")
            else:
                conda_packages.append(tool)
        
        cmd = ["conda", "install", "-c", "bioconda", "-y"] + conda_packages
        
        click.echo(f"\n执行命令: {' '.join(cmd)}")
        
        if not click.confirm("\n确认执行?", default=True):
            click.echo("已取消。")
            return
        
        # 执行安装
        try:
            click.echo("\n正在安装,请稍候...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            if result.returncode == 0:
                click.echo("\n✅ 安装成功!")
                
                # 验证安装
                click.echo("\n验证安装:")
                for tool in to_install:
                    verify_result = subprocess.run(
                        ["which", tool],
                        capture_output=True,
                        text=True
                    )
                    if verify_result.returncode == 0:
                        click.echo(f"  ✅ {tool:15s} -> {verify_result.stdout.strip()}")
                    else:
                        click.echo(f"  ⚠️  {tool:15s} -> 未找到,可能需要重新激活环境")
            else:
                click.echo(f"\n❌ 安装失败:")
                click.echo(result.stdout)
                
        except Exception as e:
            click.echo(f"\n❌ 安装出错: {e}")
    
    elif choice == 2:
        # 项目本地安装 (基于sources.json)
        click.echo("\n" + "=" * 70)
        click.echo("📦 从GitHub下载到项目工具目录...")
        click.echo("=" * 70)
        click.echo("⚠️  注意: 只有在sources.json中配置的工具才能自动下载")
        
        try:
            from ...utils.tools_manager import ToolsManager
            tm = ToolsManager(project_root=Path.cwd())
            
            success_count = 0
            fail_count = 0
            
            for tool in to_install:
                click.echo(f"\n安装 {tool} ...")
                try:
                    path = tm.install(tool)
                    click.echo(f"  ✅ 安装成功: {path}")
                    success_count += 1
                except Exception as e:
                    click.echo(f"  ❌ 安装失败: {e}")
                    click.echo(f"  建议: 使用Conda安装或手动下载")
                    fail_count += 1
            
            click.echo("\n" + "=" * 70)
            click.echo(f"安装完成: 成功 {success_count}/{len(to_install)}, 失败 {fail_count}/{len(to_install)}")
            
        except Exception as e:
            click.echo(f"\n❌ 安装过程出错: {e}")
    
    else:
        click.echo("无效选择,已退出。")


@click.command("doctor")
@click.option(
    "--tools",
    default=",".join(DEFAULT_TOOLS),
    show_default=True,
    help="Comma-separated external tools to check",
)
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Install missing tools into project-local mito_forge/tools using sources.json"
)
@click.option(
    "--interactive",
    is_flag=True,
    default=False,
    help="Interactive installation wizard (recommended for first-time setup)"
)
def doctor(tools: str, fix: bool, interactive: bool):
    """
    检查外部依赖工具是否可用，并给出缺失的安装建议。
    
    使用 --interactive 进入交互式安装向导 (推荐)
    使用 --fix 可按 mito_forge/tools/sources.json 一键安装缺失工具。
    """
    tool_list = [t.strip() for t in tools.split(",") if t.strip()]
    project_root = Path.cwd()
    result = check_tools(tool_list, project_root=project_root)
    present = result["present"]
    missing = result["missing"]

    if present:
        click.echo(f"Present/已安装: {', '.join(present)}")
    else:
        click.echo("Present/已安装: None")

    if missing:
        click.echo(f"Missing/缺失: {', '.join(missing)}")
        
        if interactive:
            # 交互式安装向导
            interactive_install(missing, result["detail"])
        elif fix:
            # 旧的--fix逻辑 (基于sources.json)
            click.echo("Suggestions/安装建议:")
            for m in missing:
                detail = result["detail"].get(m, {})
                if not detail.get("found"):
                    click.echo(f"- {m}: {detail.get('suggest', 'see bioconda')}")
            # 一键安装缺失工具（基于 tools/sources.json）
            try:
                from ...utils.tools_manager import ToolsManager
                tm = ToolsManager(project_root=Path.cwd())
                for m in missing:
                    click.echo(f"Installing {m} ...")
                    path = tm.install(m)
                    click.echo(f"Installed: {path}")
            except Exception as e:
                click.echo(f"Fix failed: {e}")
        else:
            # 只显示建议
            click.echo("Suggestions/安装建议:")
            for m in missing:
                detail = result["detail"].get(m, {})
                if not detail.get("found"):
                    click.echo(f"- {m}: {detail.get('suggest', 'see bioconda')}")
            click.echo("\n提示: 使用 'doctor --interactive' 启动交互式安装向导")
    else:
        click.echo("Missing/缺失: None")

    click.echo(f"Summary: total={result['summary']['total']}, present={result['summary']['present']}, missing={result['summary']['missing']}")
    
    click.echo("\n" + "="*60)
    click.echo("Plant Mitochondrial Annotation Tools / 植物线粒体注释工具")
    click.echo("="*60)
    
    plant_result = check_tools(PLANT_ANNOTATION_TOOLS, project_root=project_root)
    plant_present = plant_result["present"]
    plant_missing = plant_result["missing"]
    
    for t in PLANT_ANNOTATION_TOOLS:
        d = plant_result["detail"].get(t, {})
        if d.get("found"):
            alias_info = f" (via {d['alias']})" if d.get("alias") and d["alias"] != t else ""
            click.echo(f"  ✅ {t}: OK{alias_info}")
        else:
            click.echo(f"  ❌ {t}: MISSING")
            click.echo(f"     → {d.get('suggest', 'see bioconda')}")
    
    click.echo(f"\n  Plant Tools Summary: present={len(plant_present)}, missing={len(plant_missing)}")
    
    if plant_missing and not (fix or interactive):
        click.echo("\n  💡 提示: 使用 'doctor --interactive' 或 '--fix' 来安装缺失工具")
    
    if plant_missing and (fix or interactive):
        click.echo("\n  缺失的植物注释工具安装建议:")
        for m in plant_missing:
            d = plant_result["detail"].get(m, {})
            click.echo(f"  - {m}: {d.get('suggest', 'see bioconda')}")
    
    # 检查已安装工具的依赖环境
    if present:
        click.echo("\n" + "="*60)
        click.echo("检查工具依赖环境...")
        click.echo("="*60)
        
        from ...utils.tool_env_manager import ToolEnvironmentManager
        env_mgr = ToolEnvironmentManager()
        
        tools_need_env = []
        for tool in present:
            required_env = env_mgr.get_tool_required_env(tool)
            if required_env:
                env_exists = env_mgr.env_exists(required_env)
                env_name = env_mgr.get_env_name(required_env)
                deps = env_mgr.get_env_dependencies(tool)
                
                if env_exists:
                    click.echo(f"✅ {tool}: 环境 {env_name} 已配置")
                else:
                    click.echo(f"⚠️  {tool}: 需要环境 {env_name} (依赖: {', '.join(deps.keys())})")
                    tools_need_env.append((tool, required_env, deps))
        
        # 如果有工具需要环境,询问是否创建
        if tools_need_env and (fix or interactive):
            click.echo("\n发现工具需要依赖环境:")
            for tool, env, deps in tools_need_env:
                deps_str = ", ".join([f"{k}{v}" for k, v in deps.items()])
                click.echo(f"  • {tool} 需要: {deps_str}")
            
            if click.confirm("\n是否为这些工具创建conda环境?", default=True):
                for tool, env, deps in tools_need_env:
                    env_name = env_mgr.get_env_name(env)
                    click.echo(f"\n创建环境: {env_name}...")
                    click.echo("(这可能需要几分钟,请耐心等待)")
                    
                    success = env_mgr.create_env(env)
                    if success:
                        click.echo(f"✅ {env_name} 创建成功")
                    else:
                        click.echo(f"❌ {env_name} 创建失败")
                        # 构建正确的手动创建命令(版本约束需要引号)
                        pkg_list = ' '.join([f'"{k}{v}"' if v and v != '*' else k for k, v in deps.items()])
                        click.echo(f"   您可以手动创建: conda create -n {env_name} {pkg_list} -c bioconda -c conda-forge -y")
        elif tools_need_env:
            click.echo("\n💡 提示: 使用 'mito-forge doctor --fix' 或 '--interactive' 来配置环境")