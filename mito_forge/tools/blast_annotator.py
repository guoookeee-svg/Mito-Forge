import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..utils.logging import get_logger
from ..utils.assembly_stats import get_assembly_stats
from ..db import get_db_path, ensure_blast_db

logger = get_logger(__name__)


def _find_blastx() -> Optional[str]:
    """Find blastx executable"""
    return shutil.which("blastx")


def _find_trnascan() -> Optional[str]:
    """Find tRNAscan-SE executable"""
    return shutil.which("tRNAscan-SE") or shutil.which("tRNAscan")


def run_blast_annotation(
    assembly_file: str,
    output_dir: Path,
    kingdom: str = "plant",
    genetic_code: int = 1,
    threads: int = 4,
    evalue: float = 1e-5,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run BLAST+ homology-based annotation for plant mitochondrial genomes.

    Uses blastx to search against a built-in plant mitochondrial protein
    reference database. Optionally uses tRNAscan-SE for tRNA annotation.

    Returns None if BLAST+ is not available, allowing fallback to next tool.
    Returns dict with annotation results on success.
    """
    blastx_exe = _find_blastx()
    if not blastx_exe:
        logger.info("blastx not found, BLAST+ annotation unavailable")
        return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        db_fasta = get_db_path("plant_mito_proteins.fasta")
        db_prefix = ensure_blast_db(db_fasta)
    except Exception as e:
        logger.warning(f"Failed to prepare BLAST database: {e}")
        return None

    blast_output = output_dir / "blastx_results.tsv"

    try:
        cmd = [
            blastx_exe,
            "-query", str(assembly_file),
            "-db", str(db_prefix),
            "-out", str(blast_output),
            "-outfmt", "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore",
            "-evalue", str(evalue),
            "-num_threads", str(threads),
            "-query_gencode", str(genetic_code),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=str(output_dir)
        )

        if result.returncode != 0:
            logger.warning(f"blastx failed with exit code {result.returncode}: {result.stderr[:500]}")
            return None

    except subprocess.TimeoutExpired:
        logger.warning("blastx execution timed out")
        return None
    except Exception as e:
        logger.warning(f"blastx execution failed: {e}")
        return None

    gene_hits = _parse_blast_output(blast_output)

    trna_results = []
    trnascan_exe = _find_trnascan()
    if trnascan_exe:
        trna_results = _run_trnascan(trnascan_exe, assembly_file, output_dir, threads)

    gff_file = _generate_gff(gene_hits, trna_results, assembly_file, output_dir)

    protein_genes = len(gene_hits)
    trna_genes = len(trna_results)
    rrna_genes = 0
    total_genes = protein_genes + trna_genes + rrna_genes

    if total_genes == 0:
        logger.warning("No genes found by BLAST+ homology annotation")
        return None

    stats = get_assembly_stats(Path(assembly_file))
    genome_length = stats.get("total_length", 0)

    return {
        "annotator": "blast",
        "genome_length": genome_length,
        "kingdom": kingdom,
        "genetic_code": genetic_code,
        "annotation_file": str(gff_file),
        "total_genes": total_genes,
        "protein_genes": protein_genes,
        "trna_genes": trna_genes,
        "rrna_genes": rrna_genes,
        "other_genes": 0,
        "coding_coverage": 0,
        "genome_utilization": 0,
        "avg_gene_length": genome_length // max(total_genes, 1),
        "detected_issues": ["blast_homology_annotation"] if protein_genes > 0 else ["no_hits_found"],
        "gene_details": [
            {"name": h["gene_name"], "start": h["qstart"], "end": h["qend"],
             "identity": h["pident"], "source": "blastx"}
            for h in gene_hits
        ] + [
            {"name": t["name"], "start": t["start"], "end": t["end"], "source": "tRNAscan-SE"}
            for t in trna_results
        ]
    }


def _parse_blast_output(blast_output: Path) -> List[Dict[str, Any]]:
    """Parse blastx tabular output and deduplicate gene hits"""
    hits = []
    seen_genes = {}

    if not blast_output.exists():
        return hits

    try:
        with open(blast_output, 'r') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 12:
                    continue

                gene_name = parts[1].split()[0]
                pident = float(parts[2])
                length = int(parts[3])
                qstart = int(parts[6])
                qend = int(parts[7])
                evalue = float(parts[10])
                bitscore = float(parts[11])

                if gene_name in seen_genes:
                    if bitscore > seen_genes[gene_name]["bitscore"]:
                        seen_genes[gene_name] = {
                            "gene_name": gene_name,
                            "pident": pident,
                            "length": length,
                            "qstart": min(qstart, qend),
                            "qend": max(qstart, qend),
                            "evalue": evalue,
                            "bitscore": bitscore,
                        }
                else:
                    seen_genes[gene_name] = {
                        "gene_name": gene_name,
                        "pident": pident,
                        "length": length,
                        "qstart": min(qstart, qend),
                        "qend": max(qstart, qend),
                        "evalue": evalue,
                        "bitscore": bitscore,
                    }
    except Exception as e:
        logger.warning(f"Failed to parse blastx output: {e}")

    hits = sorted(seen_genes.values(), key=lambda x: x["qstart"])
    return hits


def _run_trnascan(trnascan_exe: str, assembly_file: str, output_dir: Path, threads: int) -> List[Dict[str, Any]]:
    """Run tRNAscan-SE for tRNA annotation"""
    trna_output = output_dir / "trnascan_results.txt"

    try:
        cmd = [
            trnascan_exe,
            "-B",
            "-o", str(trna_output),
            "--thread", str(threads),
            str(assembly_file)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(output_dir)
        )

        if result.returncode != 0:
            logger.warning(f"tRNAscan-SE failed: {result.stderr[:300]}")
            return []

    except Exception as e:
        logger.warning(f"tRNAscan-SE execution failed: {e}")
        return []

    trnas = []
    try:
        with open(trna_output, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 5:
                    name = parts[3] if len(parts) > 3 else f"trna_{len(trnas)+1}"
                    start = int(parts[1]) if parts[1].isdigit() else 0
                    end = int(parts[2]) if parts[2].isdigit() else 0
                    if start > 0 and end > 0:
                        trnas.append({
                            "name": name,
                            "start": min(start, end),
                            "end": max(start, end),
                        })
    except Exception as e:
        logger.warning(f"Failed to parse tRNAscan-SE output: {e}")

    return trnas


def _generate_gff(
    gene_hits: List[Dict[str, Any]],
    trna_results: List[Dict[str, Any]],
    assembly_file: str,
    output_dir: Path,
) -> Path:
    """Generate GFF3 file from BLAST and tRNAscan results"""
    gff_file = output_dir / "annotation.gff"

    try:
        from Bio import SeqIO
        records = list(SeqIO.parse(assembly_file, "fasta"))
        seq_id = records[0].id if records else "mitochondrion"
    except Exception:
        seq_id = "mitochondrion"

    with open(gff_file, 'w') as f:
        f.write("##gff-version 3\n")

        for hit in gene_hits:
            f.write(f"{seq_id}\tblast_annotation\tCDS\t{hit['qstart']}\t{hit['qend']}"
                   f"\t{hit['bitscore']:.1f}\t+\t.\t"
                   f"Name={hit['gene_name']};identity={hit['pident']:.1f};method=blastx\n")

        for trna in trna_results:
            f.write(f"{seq_id}\tblast_annotation\ttRNA\t{trna['start']}\t{trna['end']}"
                   f"\t.\t+\t.\tName={trna['name']};method=tRNAscan-SE\n")

    return gff_file
