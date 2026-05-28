# Medaka - ONT Consensus Polishing

## Overview

Medaka is a tool for creating consensus sequences from ONT reads using a neural network model.
It provides the best polishing results for Oxford Nanopore data after Racon.

## Requirements

- Python 3.6+
- ONT-specific neural network models
- HDF5 libraries (for some input formats)

## Key Parameters

### Model Selection
- -m: Model name (e.g., r941_min_high_g303)
- Use `medaka --list_models` to see available models
- Match model to your basecaller and chemistry version
- Common models:
  - r941_min_high_g303: R9.4.1 flowcell, MinKNOW, high accuracy
  - r941_min_sup_g507: R9.4.1, super-accurate basecalling
  - r10_e7.1_sup: R10 chemistry, super-accurate

### Thread Configuration
- -t: Number of threads (default: auto)
- Use -t 8 for balanced performance
- More threads = faster but more memory

## Common Error Patterns

### Model Not Found
- Error: "unknown model" or "model not found"
- Cause: Specified model not available in installed version
- Solution: Use `medaka --list_models` to see available models

### Insufficient Coverage
- Error: Poor polishing quality despite running
- Cause: Coverage too low for neural network to learn patterns
- Solution: Ensure at least 30x coverage for best results

## Best Practices

1. Run Racon first (2-3 rounds) before Medaka
2. Select correct model for your basecaller version
3. Ensure sufficient coverage (>30x recommended)
4. Follow with Pilon using Illumina reads if available
5. Typical pipeline: Flye → Racon (3x) → Medaka → Pilon

## Output Format

- Consensus FASTA file
- Quality scores in FASTQ format (optional)
- Can be used directly for annotation
