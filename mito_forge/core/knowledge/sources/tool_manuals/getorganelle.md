# GetOrganelle - Targeted Organelle Genome Assembly

## Overview

GetOrganelle is a specialized toolkit for assembling organelle genomes (mitochondria and chloroplast)
from whole-genome sequencing data using a baiting and iterative mapping approach.

## Key Parameters

### Seed Sequences
- -R: Reference seed sequences for baiting
- Use mitochondrial gene sequences from closely related species
- Multiple seed sequences improve recruitment success
- Default includes common mitochondrial gene references

### Assembly Parameters
- -t: Number of threads
- --max-extension: Maximum extension per iteration
- -F: Assembly format (animal_mt, plant_mt, plant_cp)
- -k: K-mer sizes for SPAdes assembly step

### Read Filtering
- GetOrganelle automatically filters reads by mapping to seed sequences
- Can also accept pre-filtered reads
- Sliding window quality trimming applied automatically

## Common Error Patterns

### No Seed Found
- Error: "no seed" or "cannot find seed sequences"
- Cause: Reference seed too divergent from target species
- Solution: Use custom seed from closely related species

### Low Read Recruitment
- Error: Very few reads recruited by baiting
- Cause: Low mitochondrial read fraction in input data
- Solution: Increase input read count, use more sensitive seed

### Assembly Failure
- Error: SPAdes assembly step fails
- Cause: Insufficient recruited reads for assembly
- Solution: Adjust K-mer parameters, increase read input

## Best Practices

1. Use appropriate -F flag (animal_mt or plant_mt)
2. For novel species: provide custom seed sequences
3. Use multiple K-mer sizes for SPAdes step
4. Check assembly completeness with reference comparison
5. GetOrganelle often outperforms SPAdes alone for mitochondrial assembly

## Output Format

- FASTA assembly file
- Assembly graph
- Read recruitment statistics
- Can output GenBank-ready files
