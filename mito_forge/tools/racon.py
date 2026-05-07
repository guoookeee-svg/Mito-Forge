"""
Racon 工具封装 - 长读数据序列抛光

Racon 是一个用于长读数据的快速一致性序列抛光工具。
适用于 Nanopore 和 PacBio CLR 数据。
"""
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from ..utils.logging import get_logger
from ..utils.assembly_stats import get_assembly_stats

logger = get_logger(__name__)


def run_racon(
    reads: Path,
    assembly: Path,
    output_dir: Path,
    threads: int = 4,
    iterations: int = 2,
    minimap_preset: str = "map-ont"
) -> Dict[str, Any]:
    """
    运行 Racon 抛光
    
    Args:
        reads: 原始读段文件（FASTQ/FASTA）
        assembly: 组装结果（FASTA）
        output_dir: 输出目录
        threads: 线程数
        iterations: 抛光迭代次数（推荐 2-4 次）
        minimap_preset: minimap2 预设（map-ont 用于 Nanopore，map-pb 用于 PacBio）
    
    Returns:
        结果字典，包含抛光后的序列文件和统计信息
    """
    logger.info(f"Starting Racon polishing with {iterations} iterations")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查工具
    if not shutil.which("racon"):
        raise RuntimeError("Racon not found in PATH. Install: conda install -c bioconda racon")
    if not shutil.which("minimap2"):
        raise RuntimeError("minimap2 not found in PATH. Install: conda install -c bioconda minimap2")
    
    current_assembly = assembly
    
    for i in range(1, iterations + 1):
        logger.info(f"Racon iteration {i}/{iterations}")
        print(f"[Racon] Iteration {i}/{iterations}...")
        
        # 1. 使用 minimap2 比对
        paf_file = output_dir / f"iter{i}.paf"
        minimap_cmd = [
            "minimap2",
            "-x", minimap_preset,
            "-t", str(threads),
            str(current_assembly),
            str(reads)
        ]
        
        logger.debug(f"Running minimap2: {' '.join(minimap_cmd)}")
        with open(paf_file, "w") as f:
            result = subprocess.run(
                minimap_cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                check=True,
                timeout=3600
            )
        
        # 2. 运行 racon
        polished_file = output_dir / f"polished_iter{i}.fasta"
        racon_cmd = [
            "racon",
            "-t", str(threads),
            str(reads),
            str(paf_file),
            str(current_assembly)
        ]
        
        logger.debug(f"Running racon: {' '.join(racon_cmd)}")
        with open(polished_file, "w") as f:
            result = subprocess.run(
                racon_cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                check=True,
                timeout=3600
            )
        
        current_assembly = polished_file
        logger.info(f"Iteration {i} completed: {polished_file}")
    
    # 最终输出
    final_output = output_dir / "polished.fasta"
    shutil.copy(current_assembly, final_output)
    
    stats = get_assembly_stats(final_output)
    
    logger.info(f"Racon polishing completed with {iterations} iterations")
    
    return {
        "tool": "racon",
        "polished_file": str(final_output),
        "iterations": iterations,
        "stats": stats,
        "success": True
    }
