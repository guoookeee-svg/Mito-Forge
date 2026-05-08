import os
import shutil
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, Optional

from ..utils.logging import get_logger
from ..utils.assembly_stats import get_assembly_stats

logger = get_logger(__name__)


def _find_mitofy() -> Optional[str]:
    """Find MITOFY executable (mitofy.pl)"""
    for name in ["mitofy.pl", "mitofy"]:
        path = shutil.which(name)
        if path:
            return path
    try:
        from ..utils.tools_manager import ToolsManager
        tm = ToolsManager(project_root=Path.cwd())
        p = tm.where("mitofy")
        if p:
            return str(p)
    except Exception:
        pass
    return None


def run_mitofy(
    assembly_file: str,
    output_dir: Path,
    kingdom: str = "plant",
    genetic_code: int = 1,
    threads: int = 4,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run MITOFY for plant mitochondrial genome annotation.

    MITOFY uses BLAST + tRNAscan-SE to annotate plant mitochondrial genomes.
    It searches against databases of 41 protein-coding genes and 27 tRNA + 3 rRNA genes
    known from seed plant mitochondrial genomes.

    Returns None if MITOFY is not available, allowing fallback to next tool.
    Returns dict with annotation results on success.
    """
    mitofy_exe = _find_mitofy()
    if not mitofy_exe:
        logger.info("MITOFY not found")
        return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mitofy_output = output_dir / "mitofy_output"
    mitofy_output.mkdir(exist_ok=True)

    try:
        cmd = [
            mitofy_exe,
            str(Path(assembly_file).resolve()),
        ]

        env = os.environ.copy()
        env["MITOFY_DIR"] = str(Path(mitofy_exe).parent)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            cwd=str(mitofy_output),
            env=env
        )

        if result.returncode != 0:
            logger.warning(f"MITOFY failed with exit code {result.returncode}: {result.stderr[:500]}")
            return None

        return _parse_mitofy_output(mitofy_output, assembly_file, kingdom)

    except subprocess.TimeoutExpired:
        logger.warning("MITOFY execution timed out")
        return None
    except FileNotFoundError:
        logger.warning("MITOFY executable not found at runtime")
        return None
    except Exception as e:
        logger.warning(f"MITOFY execution failed: {e}")
        return None


def _parse_mitofy_output(output_dir: Path, assembly_file: str, kingdom: str) -> Optional[Dict[str, Any]]:
    """Parse MITOFY output directory and convert to standard format"""
    gene_count = 0
    protein_genes = 0
    trna_genes = 0
    rrna_genes = 0
    gene_details = []

    for html_file in output_dir.glob("*.html"):
        try:
            content = html_file.read_text(errors='ignore')
            hits = re.findall(r'(\w+)\s+<.*?>\s*(\d+)\s*-\s*(\d+)', content)
            for gene_name, start, end in hits:
                gene_count += 1
                gene_details.append({
                    "name": gene_name,
                    "start": int(start),
                    "end": int(end),
                    "source": "mitofy"
                })
                if gene_name.startswith("trn"):
                    trna_genes += 1
                elif gene_name.startswith("rrn"):
                    rrna_genes += 1
                else:
                    protein_genes += 1
        except Exception as e:
            logger.warning(f"Failed to parse MITOFY HTML output {html_file}: {e}")

    for txt_file in output_dir.glob("*.txt"):
        try:
            with open(txt_file, 'r', errors='ignore') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) >= 3:
                        gene_name = parts[0]
                        try:
                            start = int(parts[1])
                            end = int(parts[2])
                        except ValueError:
                            continue
                        gene_count += 1
                        gene_details.append({
                            "name": gene_name,
                            "start": start,
                            "end": end,
                            "source": "mitofy"
                        })
                        if gene_name.startswith("trn"):
                            trna_genes += 1
                        elif gene_name.startswith("rrn"):
                            rrna_genes += 1
                        else:
                            protein_genes += 1
        except Exception as e:
            logger.warning(f"Failed to parse MITOFY text output {txt_file}: {e}")

    gff_file = output_dir / "annotation.gff"
    if gene_details:
        try:
            from Bio import SeqIO
            records = list(SeqIO.parse(assembly_file, "fasta"))
            seq_id = records[0].id if records else "mitochondrion"
        except Exception:
            seq_id = "mitochondrion"

        with open(gff_file, 'w') as f:
            f.write("##gff-version 3\n")
            for gene in gene_details:
                feat_type = "tRNA" if gene["name"].startswith("trn") else \
                           "rRNA" if gene["name"].startswith("rrn") else "CDS"
                f.write(f"{seq_id}\tMITOFY\t{feat_type}\t{gene['start']}\t{gene['end']}"
                       f"\t.\t+\t.\tName={gene['name']}\n")

    if gene_count == 0:
        logger.warning("No genes found in MITOFY output")
        return None

    stats = get_assembly_stats(Path(assembly_file))
    genome_length = stats.get("total_length", 0)

    return {
        "annotator": "mitofy",
        "genome_length": genome_length,
        "kingdom": kingdom,
        "genetic_code": 1,
        "annotation_file": str(gff_file) if gff_file.exists() else "",
        "total_genes": gene_count,
        "protein_genes": protein_genes,
        "trna_genes": trna_genes,
        "rrna_genes": rrna_genes,
        "other_genes": 0,
        "coding_coverage": 0,
        "genome_utilization": 0,
        "avg_gene_length": genome_length // max(gene_count, 1),
        "detected_issues": [],
        "gene_details": gene_details
    }
