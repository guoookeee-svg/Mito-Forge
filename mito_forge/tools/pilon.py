"""
Pilon 工具封装 - 短读数据序列抛光

Pilon 使用短读数据（Illumina）对组装进行抛光，修正碱基错误、小片段插入缺失等。
需要先进行读段比对（BWA/Bowtie2）生成 BAM 文件。
"""
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from ..utils.logging import get_logger
from ..utils.assembly_stats import get_assembly_stats

logger = get_logger(__name__)


def run_pilon(
    reads: Path,
    reads2: Optional[Path],
    assembly: Path,
    output_dir: Path,
    threads: int = 4,
    memory: str = "16G",
    iterations: int = 1
) -> Dict[str, Any]:
    """
    运行 Pilon 抛光
    
    Args:
        reads: R1 读段文件（FASTQ）
        reads2: R2 读段文件（FASTQ，双端）
        assembly: 组装结果（FASTA）
        output_dir: 输出目录
        threads: 线程数
        memory: Java 堆内存大小（如 "16G"）
        iterations: 抛光迭代次数（推荐 1-2 次）
    
    Returns:
        结果字典，包含抛光后的序列文件和统计信息
    """
    logger.info(f"Starting Pilon polishing with {iterations} iterations")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查工具
    if not shutil.which("pilon"):
        # 尝试查找 pilon.jar
        pilon_jar = None
        for jar_path in ["/usr/local/bin/pilon.jar", "/opt/pilon/pilon.jar"]:
            if Path(jar_path).exists():
                pilon_jar = jar_path
                break
        if not pilon_jar:
            raise RuntimeError("Pilon not found. Install: conda install -c bioconda pilon")
    
    if not shutil.which("bwa"):
        raise RuntimeError("BWA not found. Install: conda install -c bioconda bwa")
    
    if not shutil.which("samtools"):
        raise RuntimeError("samtools not found. Install: conda install -c bioconda samtools")
    
    current_assembly = assembly
    
    for i in range(1, iterations + 1):
        logger.info(f"Pilon iteration {i}/{iterations}")
        print(f"[Pilon] Iteration {i}/{iterations}...")
        
        # 1. 建立 BWA 索引
        logger.debug("Building BWA index")
        subprocess.run(
            ["bwa", "index", str(current_assembly)],
            check=True,
            timeout=600
        )
        
        # 2. 比对读段
        sam_file = output_dir / f"iter{i}.sam"
        logger.debug("Aligning reads with BWA")
        
        bwa_cmd = ["bwa", "mem", "-t", str(threads), str(current_assembly), str(reads)]
        if reads2:
            bwa_cmd.append(str(reads2))
        
        with open(sam_file, "w") as f:
            subprocess.run(
                bwa_cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                check=True,
                timeout=3600
            )
        
        # 3. 转换为 BAM 并排序
        bam_file = output_dir / f"iter{i}.sorted.bam"
        logger.debug("Converting to sorted BAM")
        view_proc = subprocess.Popen(
            ["samtools", "view", "-@", str(threads), "-bS", str(sam_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        subprocess.run(
            ["samtools", "sort", "-@", str(threads), "-o", str(bam_file)],
            stdin=view_proc.stdout,
            check=True,
            timeout=1800
        )
        view_proc.wait()
        subprocess.run(
            ["samtools", "index", str(bam_file)],
            check=True
        )
        
        # 删除临时 SAM 文件
        sam_file.unlink()
        
        # 4. 运行 Pilon
        polished_prefix = output_dir / f"polished_iter{i}"
        polished_file = output_dir / f"polished_iter{i}.fasta"
        
        logger.debug("Running Pilon")
        pilon_cmd = [
            "pilon",
            f"-Xmx{memory}",
            "--genome", str(current_assembly),
            "--bam", str(bam_file),
            "--output", str(polished_prefix),
            "--threads", str(threads),
            "--changes"
        ]
        
        subprocess.run(
            pilon_cmd,
            check=True,
            timeout=3600
        )
        
        current_assembly = polished_file
        logger.info(f"Iteration {i} completed: {polished_file}")
    
    # 最终输出
    final_output = output_dir / "polished.fasta"
    shutil.copy(current_assembly, final_output)
    
    stats = get_assembly_stats(final_output)
    
    logger.info(f"Pilon polishing completed after {iterations} iterations")
    
    return {
        "tool": "pilon",
        "polished_file": str(final_output),
        "iterations": iterations,
        "stats": stats,
        "success": True
    }
