from pathlib import Path
from typing import Dict, Any


def get_assembly_stats(fasta_file: Path) -> Dict[str, Any]:
    if not fasta_file.exists():
        return {}
    try:
        from Bio import SeqIO

        sequences = list(SeqIO.parse(str(fasta_file), "fasta"))
        lengths = [len(seq) for seq in sequences]

        if not lengths:
            return {}

        total_length = sum(lengths)
        num_contigs = len(lengths)

        lengths_sorted = sorted(lengths, reverse=True)
        cumsum = 0
        n50 = 0
        for length in lengths_sorted:
            cumsum += length
            if cumsum >= total_length / 2:
                n50 = length
                break

        return {
            "total_length": total_length,
            "num_contigs": num_contigs,
            "n50": n50,
            "max_contig_length": max(lengths),
            "min_contig_length": min(lengths)
        }
    except Exception as e:
        from ..utils.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to get assembly stats: {e}")
        return {}
