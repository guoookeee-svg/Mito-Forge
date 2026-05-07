"""
Medaka 工具封装 - Nanopore 数据序列抛光

Medaka 是 Oxford Nanopore 官方推荐的抛光工具，使用神经网络模型进行碱基校正。
适用于 Nanopore 数据，需要根据测序化学配方选择正确的模型。
"""
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any
from ..utils.logging import get_logger
from ..utils.assembly_stats import get_assembly_stats

logger = get_logger(__name__)


# Medaka 模型对应表
MEDAKA_MODELS = {
    "r941_min_high_g360": "R9.4.1 MinION/GridION high accuracy (Guppy ≥3.6.0)",
    "r941_min_fast_g303": "R9.4.1 MinION/GridION fast basecalling (Guppy 3.0.3+)",
    "r941_prom_high_g360": "R9.4.1 PromethION high accuracy (Guppy ≥3.6.0)",
    "r103_min_high_g360": "R10.3 MinION high accuracy (Guppy ≥3.6.0)",
    "r104_e81_sup_g5015": "R10.4.1 SUP basecalling (Guppy 5.0.15+)",
}


def run_medaka(
    reads: Path,
    assembly: Path,
    output_dir: Path,
    model: str = "r941_min_high_g360",
    threads: int = 4
) -> Dict[str, Any]:
    """
    运行 Medaka 抛光
    
    Args:
        reads: 原始读段文件（FASTQ）
        assembly: 组装结果（FASTA）
        output_dir: 输出目录
        model: Medaka 模型名称（根据测序化学配方和 basecaller 版本选择）
        threads: 线程数
    
    Returns:
        结果字典，包含抛光后的序列文件和统计信息
    """
    logger.info(f"Starting Medaka polishing with model {model}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查工具
    if not shutil.which("medaka_consensus"):
        raise RuntimeError("Medaka not found. Install: conda install -c bioconda medaka")
    
    # Medaka 一步完成比对和抛光
    medaka_cmd = [
        "medaka_consensus",
        "-i", str(reads),
        "-d", str(assembly),
        "-o", str(output_dir / "medaka_output"),
        "-m", model,
        "-t", str(threads)
    ]
    
    logger.debug(f"Running medaka: {' '.join(medaka_cmd)}")
    
    result = subprocess.run(
        medaka_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=7200  # Medaka 可能需要较长时间
    )
    
    # Medaka 输出文件
    medaka_output = output_dir / "medaka_output" / "consensus.fasta"
    
    if not medaka_output.exists():
        raise RuntimeError("Medaka did not produce output file")
    
    # 复制到标准输出位置
    final_output = output_dir / "polished.fasta"
    shutil.copy(medaka_output, final_output)
    
    stats = get_assembly_stats(final_output)
    
    logger.info(f"Medaka polishing completed with model {model}")
    
    return {
        "tool": "medaka",
        "polished_file": str(final_output),
        "model": model,
        "stats": stats,
        "success": True
    }
