"""
ORF-based annotation fallback.

Uses getorf (EMBOSS) or a pure-Python ORF finder to detect open reading frames,
then maps them to expected mitochondrial genes by length heuristics.
This replaces the previous "basic annotation" which fabricated gene positions.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

ANIMAL_MITO_GENES = {
    "protein": ["nad1", "nad2", "cox1", "cox2", "atp8", "atp6", "cox3", "nad3",
                "nad4L", "nad4", "nad5", "nad6", "cytb"],
    "trna_count": 22,
    "rrna": ["rrnS", "rrnL"],
}

PLANT_MITO_GENES = {
    "protein": ["nad1", "nad2", "nad3", "nad4", "nad4L", "nad5", "nad6", "nad7", "nad9",
                "cox1", "cox2", "cox3", "atp1", "atp4", "atp6", "atp8", "atp9",
                "ccmB", "ccmC", "ccmFC", "ccmFN", "matR", "mttB"],
    "trna_count": 22,
    "rrna": ["rrn18", "rrn5", "rrn26"],
}

GENE_LENGTH_RANGES = {
    "nad1": (800, 1000), "nad2": (900, 1100), "nad3": (300, 400),
    "nad4": (1300, 1500), "nad4L": (250, 350), "nad5": (1400, 1600),
    "nad6": (400, 600), "nad7": (1100, 1300), "nad9": (500, 700),
    "cox1": (1400, 1600), "cox2": (600, 800), "cox3": (700, 900),
    "atp1": (1100, 1300), "atp4": (400, 600), "atp6": (500, 700),
    "atp8": (150, 250), "atp9": (200, 300),
    "ccmB": (500, 700), "ccmC": (600, 800), "ccmFC": (700, 900), "ccmFN": (400, 600),
    "matR": (600, 800), "mttB": (250, 400),
    "cytb": (1000, 1200),
}


def _find_getorf() -> Optional[str]:
    import shutil
    path = shutil.which("getorf")
    if path:
        return path
    return None


def _run_getorf(assembly_file: str, output_dir: Path, min_orf_length: int = 150,
                genetic_code: int = 2) -> Optional[str]:
    exe = _find_getorf()
    if not exe:
        return None
    out_file = output_dir / "orf_predictions.gff"
    import subprocess
    cmd = [
        exe,
        "-sequence", str(assembly_file),
        "-outseq", str(out_file),
        "-minsize", str(min_orf_length),
        "-find", "3",
        "-gcnumber", str(genetic_code),
        "-gff",
        "-auto",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, cwd=str(output_dir)
        )
        if result.returncode == 0 and out_file.exists():
            return str(out_file)
    except Exception as e:
        logger.warning(f"getorf failed: {e}")
    return None


def _find_orfs_python(sequence: str, min_length: int = 150, genetic_code: int = 2) -> List[Dict[str, Any]]:
    codon_table = _get_codon_table(genetic_code)
    orfs: List[Dict[str, Any]] = []
    seq_len = len(sequence)
    for strand, seq in [(1, sequence), (-1, _reverse_complement(sequence))]:
        for frame in range(3):
            i = frame
            while i + 2 < seq_len:
                codon = seq[i:i + 3].upper()
                if codon in codon_table.get("start", {"ATG"}):
                    start_pos = i
                    protein_len = 0
                    j = i
                    while j + 2 < seq_len:
                        c = seq[j:j + 3].upper()
                        if c in codon_table.get("stop", {"TAA", "TAG", "TGA"}):
                            if protein_len * 3 >= min_length:
                                orfs.append({
                                    "start": start_pos + 1 if strand == 1 else seq_len - j - 2,
                                    "end": j + 3 if strand == 1 else seq_len - start_pos,
                                    "strand": "+" if strand == 1 else "-",
                                    "length": protein_len * 3,
                                    "frame": frame,
                                })
                            i = j + 3
                            break
                        protein_len += 1
                        j += 3
                    else:
                        i = j
                        continue
                    continue
                i += 3
    orfs.sort(key=lambda x: x["length"], reverse=True)
    return orfs


def _get_codon_table(genetic_code: int) -> Dict[str, set]:
    stop_codons = {
        1: {"TAA", "TAG", "TGA"},
        2: {"TAA", "TAG", "AGA", "AGG"},
        5: {"TAA", "TAG"},
    }
    start_codons = {"ATG", "ATA", "GTG"}
    return {
        "start": start_codons,
        "stop": stop_codons.get(genetic_code, stop_codons[1]),
    }


def _reverse_complement(seq: str) -> str:
    comp = str.maketrans("ATGCatgc", "TACGtacg")
    return seq.translate(comp)[::-1]


def _assign_genes_to_orfs(orfs: List[Dict], kingdom: str) -> List[Dict[str, Any]]:
    gene_set = PLANT_MITO_GENES if kingdom == "plant" else ANIMAL_MITO_GENES
    expected_proteins = gene_set["protein"]
    assigned = []
    used_orf_indices = set()
    for gene_name in expected_proteins:
        length_range = GENE_LENGTH_RANGES.get(gene_name)
        best_idx = None
        best_score = -1
        for i, orf in enumerate(orfs):
            if i in used_orf_indices:
                continue
            score = 0
            if length_range:
                lo, hi = length_range
                if lo <= orf["length"] <= hi:
                    score = 2
                elif lo * 0.7 <= orf["length"] <= hi * 1.3:
                    score = 1
            else:
                score = 1
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is not None and best_score > 0:
            orf = orfs[best_idx]
            used_orf_indices.add(best_idx)
            assigned.append({
                "gene_name": gene_name,
                "start": orf["start"],
                "end": orf["end"],
                "strand": orf["strand"],
                "orf_length": orf["length"],
                "confidence": best_score / 2.0,
                "source": "orf_assignment",
            })
    return assigned


def _generate_gff(assigned_genes: List[Dict], seq_id: str, kingdom: str) -> str:
    lines = ["##gff-version 3\n"]
    for g in assigned_genes:
        gene_type = "CDS"
        name = g["gene_name"]
        if name.startswith("rrn") or name.startswith("trn"):
            gene_type = "rRNA" if name.startswith("rrn") else "tRNA"
        conf = g.get("confidence", 0.0)
        source = g.get("source", "orf_annotation")
        attributes = f"Name={name};confidence={conf:.2f};source={source}"
        if conf < 0.5:
            attributes += ";note=low_confidence_ORF_assignment"
        lines.append(
            f"{seq_id}\t{source}\t{gene_type}\t{g['start']}\t{g['end']}\t.\t"
            f"{g['strand']}\t.\t{attributes}\n"
        )
    return "".join(lines)


def run_orf_annotation(assembly_file: str, output_dir: Path, kingdom: str,
                       genetic_code: int = 2, threads: int = 4,
                       config: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """
    ORF-based annotation fallback.

    Returns None if no ORFs can be detected (truly failed annotation).
    Returns annotation dict if ORFs are found and assigned to genes.
    All gene positions are derived from actual sequence features (ORFs),
    not fabricated.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    sequences = _read_fasta(assembly_file)
    if not sequences:
        logger.warning("No sequences found in assembly file for ORF annotation")
        return None

    seq_id, sequence = sequences[0]
    genome_length = len(sequence)

    all_orfs: List[Dict] = []
    gff_file_path = output_dir / "orf_annotation.gff"

    getorf_gff = _run_getorf(assembly_file, output_dir, min_orf_length=150, genetic_code=genetic_code)
    if getorf_gff:
        orfs = _parse_getorf_gff(getorf_gff)
        all_orfs.extend(orfs)
        logger.info(f"getorf found {len(orfs)} ORFs")
    else:
        orfs = _find_orfs_python(sequence, min_length=150, genetic_code=genetic_code)
        all_orfs.extend(orfs)
        logger.info(f"Python ORF finder found {len(orfs)} ORFs")

    if not all_orfs:
        logger.warning("No ORFs detected in assembly - cannot produce meaningful annotation")
        return None

    assigned = _assign_genes_to_orfs(all_orfs, kingdom)
    if not assigned:
        logger.warning("ORFs found but none could be assigned to expected mitochondrial genes")
        return None

    gff_content = _generate_gff(assigned, seq_id, kingdom)
    gff_file_path.write_text(gff_content)

    protein_genes = sum(1 for g in assigned if g["gene_name"] in
                        (PLANT_MITO_GENES if kingdom == "plant" else ANIMAL_MITO_GENES)["protein"])
    gene_set = PLANT_MITO_GENES if kingdom == "plant" else ANIMAL_MITO_GENES
    avg_conf = sum(g["confidence"] for g in assigned) / max(len(assigned), 1)

    return {
        "annotator": "orf_finder",
        "genome_length": genome_length,
        "kingdom": kingdom,
        "genetic_code": genetic_code,
        "annotation_file": str(gff_file_path),
        "total_genes": len(assigned),
        "protein_genes": protein_genes,
        "trna_genes": 0,
        "rrna_genes": 0,
        "other_genes": 0,
        "coding_coverage": 0,
        "genome_utilization": 0,
        "avg_gene_length": sum(g["orf_length"] for g in assigned) // max(len(assigned), 1),
        "detected_issues": [
            "orf_based_annotation_no_specialized_tool",
            f"average_confidence={avg_conf:.2f}",
            "no_tRNA_rRNA_predicted_by_ORF_finder",
        ],
        "gene_details": assigned,
    }


def _read_fasta(filepath: str) -> List[Tuple[str, str]]:
    sequences = []
    current_id = ""
    current_seq = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    if current_id:
                        sequences.append((current_id, "".join(current_seq)))
                    current_id = line[1:].split()[0]
                    current_seq = []
                else:
                    current_seq.append(line)
            if current_id:
                sequences.append((current_id, "".join(current_seq)))
    except Exception as e:
        logger.warning(f"Failed to read FASTA: {e}")
    return sequences


def _parse_getorf_gff(gff_path: str) -> List[Dict]:
    orfs = []
    try:
        with open(gff_path, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split('\t')
                if len(parts) < 5:
                    continue
                start = int(parts[3])
                end = int(parts[4])
                strand = parts[6] if len(parts) > 6 else "+"
                length = abs(end - start) + 1
                orfs.append({
                    "start": min(start, end),
                    "end": max(start, end),
                    "strand": strand,
                    "length": length,
                    "frame": 0,
                })
    except Exception as e:
        logger.warning(f"Failed to parse getorf GFF: {e}")
    orfs.sort(key=lambda x: x["length"], reverse=True)
    return orfs
