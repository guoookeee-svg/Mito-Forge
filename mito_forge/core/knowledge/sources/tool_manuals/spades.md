# SPAdes Genome Assembler

## Overview

SPAdes is a de novo genome assembler for single-cell and multi-cell bacterial and eukaryotic genomes.
For mitochondrial genome assembly, SPAdes is the primary tool for Illumina short-read data.

## Key Parameters

### K-mer Selection
- Default K-mer sizes: 21,33,55,77,99,127
- For mitochondrial genomes: use smaller K-mer range (21,33,55)
- Larger K-mers provide better resolution of repeats but require more memory
- K-mer size must be odd and less than read length

### Memory Management
- Default memory limit: 250GB
- Use --memory flag to set memory limit (e.g., --memory 16)
- Reducing thread count also reduces peak memory usage
- --careful mode reduces memory but is slower

### Thread Configuration
- Default: auto-detect (uses all available cores)
- Use -t flag to set thread count (e.g., -t 8)
- For memory-constrained environments: reduce threads to 4 or fewer

## Common Error Patterns

### Out of Memory (OOM)
- Error: "std::bad_alloc" or process killed (exit code 137)
- Solution: Reduce threads, enable --careful, reduce K-mer range
- Alternative: Switch to Flye for long-read data

### Low Coverage Warning
- Error: "coverage is too low" or "K-mer coverage threshold"
- Solution: Disable error correction (--disable-corr), use smaller K-mers
- Alternative: Use GetOrganelle which requires less coverage

### Input Format Errors
- Error: "unsupported file format"
- Solution: Convert to FASTQ format, ensure proper gzip compression
- Check for corrupted files with `file` command

## Best Practices for Mitochondrial Assembly

1. Use --careful mode to avoid mismatches
2. Set appropriate K-mer range based on read length
3. For animal mitochondria: K=21,33,55,77
4. For plant mitochondria: K=21,33,55 (larger genomes need less aggressive K-mers)
5. Always check assembly completeness with QUAST

## Output Interpretation

- `contigs.fasta`: Final assembly contigs
- `scaffolds.fasta`: Scaffolded assembly
- `assembly_graph.fastg`: Assembly graph for visualization
- `K*/`: Intermediate results for each K-mer size
