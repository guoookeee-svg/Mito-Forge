# Racon - Consensus Module for Long-Read Polishing

## Overview

Racon is a consensus module for correcting raw contigs produced by long-read assemblers.
It is the first polishing step for ONT and PacBio assemblies.

## Key Parameters

### Window Length
- -w: Average length of window used for POA (default: 500)
- Smaller windows: more sensitive but slower
- Larger windows: faster but may miss small errors

### Quality Threshold
- -q: Quality threshold for sequences (default: 10)
- Lower threshold: more reads included, potentially noisier
- Higher threshold: fewer reads, potentially missing coverage

### Match/Mismatch/Gap Scores
- -m: Match score (default: 5)
- -x: Mismatch penalty (default: -4)
- -g: Gap penalty (default: -8)
- Tuning these can improve consensus quality for specific data types

## Common Error Patterns

### No Alignments
- Error: "zero overlaps processed" or empty output
- Cause: Minimap2 alignment produced no overlaps
- Solution: Check minimap2 preset (-x map-ont vs -x map-pb)

### Slow Performance
- Racon can be slow for large datasets
- Solution: Reduce window size, use fewer threads, subsample reads

## Best Practices

1. Use correct minimap2 preset for read type
2. Run 2-3 rounds of Racon for best results
3. Follow with Medaka for ONT-specific polishing
4. Then use Pilon with Illumina reads for final polish
5. Typical pipeline: Flye → Racon (3x) → Medaka → Pilon

## Output Format

- Corrected FASTA file
- Same format as input assembly
- Can be used directly for annotation
