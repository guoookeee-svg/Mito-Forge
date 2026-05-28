# Flye Long-Read Assembler

## Overview

Flye is a de novo assembler for single-molecule sequencing reads (PacBio and Oxford Nanopore).
It is the primary tool for long-read mitochondrial genome assembly.

## Key Parameters

### Genome Size Estimation
- Use --genome-size flag with estimated size (e.g., --genome-size 16k for animal mitochondria)
- For plant mitochondria: use larger estimates (e.g., --genome-size 400k)
- Overestimating is better than underestimating

### Overlap Settings
- --min-overlap: Minimum overlap length (default: auto)
- For low-coverage data: reduce to 1000-2000
- For high-coverage data: increase to 5000+ for better repeat resolution

### Polishing
- Flye performs self-polishing by default
- Additional polishing with Racon + Medaka recommended
- Use --polish-rounds to set self-polishing iterations

## Common Error Patterns

### Repeat Resolution Failure
- Error: "repeat resolution failed" or "unresolved repeats"
- Cause: Insufficient coverage to resolve repeat regions
- Solution: Increase coverage, adjust --min-overlap

### Assembly Too Short
- Error: Total assembly length much shorter than expected
- Cause: Non-mitochondrial reads dominate, or parameters too stringent
- Solution: Pre-filter reads with minimap2, adjust genome-size estimate

### Memory Issues
- Less common than SPAdes but can occur with very large datasets
- Solution: Reduce input read count with seqkit sample

## Best Practices for Mitochondrial Assembly

1. For ONT data: use --nano-raw or --nano-corr depending on basecalling
2. For PacBio HiFi: use --pacbio-hifi
3. Set --genome-size to expected mitochondrial genome size
4. Use --no-chimera-detection for mitochondrial data (low chimera rate)
5. Follow with Racon (3 rounds) + Medaka for best quality

## Output Interpretation

- `assembly.fasta`: Final polished assembly
- `assembly_graph.gfa`: Assembly graph
- `flye.log`: Detailed execution log
- `00-assembly/`: Raw assembly before polishing
- `10-consensus/`: Consensus sequences after polishing
