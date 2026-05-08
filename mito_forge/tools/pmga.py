import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from ..utils.logging import get_logger
from ..utils.assembly_stats import get_assembly_stats

logger = get_logger(__name__)


def _find_pmga() -> Optional[str]:
    """Find PMGA executable"""
    for name in ["pmga", "PMGA", "pmga.py"]:
        path = shutil.which(name)
        if path:
            return path
    try:
        from ..utils.tools_manager import ToolsManager
        tm = ToolsManager(project_root=Path.cwd())
        p = tm.where("pmga")
        if p:
            return str(p)
    except Exception:
        pass
    return None


def _find_singularity() -> Optional[str]:
    """Find singularity/apptainer executable"""
    return shutil.which("singularity") or shutil.which("apptainer")


def run_pmga(
    assembly_file: str,
    output_dir: Path,
    kingdom: str = "plant",
    genetic_code: int = 1,
    threads: int = 4,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run PMGA (Plant Mitochondrial Genome Annotator) for plant mitochondrial genome annotation.

    PMGA can be installed via:
    - Singularity container from figshare
    - Conda (if available)
    - Direct download from GitHub

    Returns None if PMGA is not available, allowing fallback to next tool.
    Returns dict with annotation results on success.
    """
    pmga_exe = _find_pmga()
    singularity_exe = None

    if not pmga_exe:
        singularity_exe = _find_singularity()
        if not singularity_exe:
            logger.info("PMGA not found (neither direct nor singularity)")
            return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pmga_output = output_dir / "pmga_output"
    pmga_output.mkdir(exist_ok=True)

    try:
        if pmga_exe:
            cmd = [
                pmga_exe,
                "-i", str(assembly_file),
                "-o", str(pmga_output),
                "-t", str(threads),
            ]
            if genetic_code:
                cmd.extend(["--genetic_code", str(genetic_code)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=str(output_dir)
            )
        elif singularity_exe:
            sif_path = config.get("pmga_sif") if config else None
            if not sif_path:
                logger.info("PMGA singularity image not configured")
                return None

            cmd = [
                singularity_exe,
                "exec",
                str(sif_path),
                "pmga",
                "-i", str(Path(assembly_file).resolve()),
                "-o", str(pmga_output.resolve()),
                "-t", str(threads),
            ]
            if genetic_code:
                cmd.extend(["--genetic_code", str(genetic_code)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=str(output_dir)
            )
        else:
            return None

        if result.returncode != 0:
            logger.warning(f"PMGA failed with exit code {result.returncode}: {result.stderr[:500]}")
            return None

        return _parse_pmga_output(pmga_output, assembly_file, kingdom)

    except subprocess.TimeoutExpired:
        logger.warning("PMGA execution timed out")
        return None
    except FileNotFoundError:
        logger.warning("PMGA executable not found at runtime")
        return None
    except Exception as e:
        logger.warning(f"PMGA execution failed: {e}")
        return None


def _parse_pmga_output(output_dir: Path, assembly_file: str, kingdom: str) -> Optional[Dict[str, Any]]:
    """Parse PMGA output directory"""
    gff_file = None
    gb_file = None

    for f in output_dir.rglob("*.gff"):
        if f.stat().st_size > 0:
            gff_file = f
            break

    for f in output_dir.rglob("*.gb*"):
        if f.stat().st_size > 0:
            gb_file = f
            break

    if not gff_file and not gb_file:
        logger.warning("No GFF or GenBank output found from PMGA")
        return None

    gene_count = 0
    protein_genes = 0
    trna_genes = 0
    rrna_genes = 0

    if gff_file:
        try:
            with open(gff_file, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        feat = parts[2]
                        gene_count += 1
                        if feat == 'CDS':
                            protein_genes += 1
                        elif feat == 'tRNA':
                            trna_genes += 1
                        elif feat == 'rRNA':
                            rrna_genes += 1
        except Exception as e:
            logger.warning(f"Failed to parse PMGA GFF: {e}")

    stats = get_assembly_stats(Path(assembly_file))
    genome_length = stats.get("total_length", 0)

    return {
        "annotator": "pmga",
        "genome_length": genome_length,
        "kingdom": kingdom,
        "genetic_code": 1,
        "annotation_file": str(gff_file or gb_file),
        "total_genes": gene_count,
        "protein_genes": protein_genes,
        "trna_genes": trna_genes,
        "rrna_genes": rrna_genes,
        "other_genes": 0,
        "coding_coverage": 0,
        "genome_utilization": 0,
        "avg_gene_length": genome_length // max(gene_count, 1),
        "detected_issues": [],
        "gene_details": []
    }
