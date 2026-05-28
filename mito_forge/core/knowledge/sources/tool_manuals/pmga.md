# PMGA - Plant Mitochondrial Genome Annotator

## Overview

PMGA is a specialized tool for annotating plant mitochondrial genomes.
It uses a reference-based approach with a curated database of plant mitochondrial genes.

## Requirements

- Python 3.6+
- BLAST+
- Preferably run via Singularity container for reproducibility

## Key Parameters

### Input Requirements
- Input: FASTA file of assembled mitochondrial genome
- Works best with complete circular genomes
- Partial genomes may have reduced annotation quality

### Annotation Scope
- Protein-coding genes: 24-41 genes depending on species
- tRNA genes: ~22 genes
- rRNA genes: 3 genes (18S, 26S, 5S)
- Introns and CDS boundaries

## Common Error Patterns

### Low Gene Count
- Fewer than 20 protein-coding genes detected
- Cause: Incomplete assembly, species not in reference database
- Solution: Try MITOFY or BLAST+ annotation as alternatives

### Singularity Not Found
- PMGA distributed as Singularity container
- Cause: Singularity/Apptainer not installed
- Solution: Install Singularity or use alternative annotation tools

### Timeout
- Large plant mitochondrial genomes (>500kb) may take longer
- Solution: Increase timeout, or pre-filter contigs

## Best Practices

1. Ensure assembly is complete (circular) for best results
2. Use the latest PMGA version for updated reference database
3. Cross-validate with MITOFY for critical annotations
4. For seed plants: PMGA is the first choice
5. For non-seed plants: MITOFY may be more appropriate

## Output Format

- GFF3 file with gene annotations
- GenBank file with feature table
- Summary statistics (gene count, genome coverage)
