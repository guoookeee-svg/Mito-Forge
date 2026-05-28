# Pilon - Illumina Polishing Tool

## Overview

Pilon is a genome polishing tool that uses Illumina reads to correct errors in assemblies.
It is the primary tool for polishing long-read assemblies with short-read data.

## Requirements

- Java 1.8+ (JDK or JRE)
- Sufficient Java heap memory (recommend 32GB+)
- BAM file from BWA-MEM alignment of Illumina reads to assembly

## Key Parameters

### Java Heap Size
- Use -Xmx flag to set maximum heap size
- Example: java -Xmx32G -jar pilon.jar
- For large genomes: use 64GB or more
- Insufficient heap is the most common error

### Polishing Mode
- --fix all: Fix all types of errors (default)
- --fix snps: Fix only SNP errors
- --fix indels: Fix only insertion/deletion errors
- --fix gaps: Fix only gap errors

### Input Requirements
- Assembled genome (FASTA)
- Aligned reads (BAM, sorted and indexed)
- BAM must be from BWA-MEM (not Bowtie2) for best results

## Common Error Patterns

### Java OutOfMemoryError
- Error: "java.lang.OutOfMemoryError: Java heap space"
- Cause: Java heap size insufficient for input BAM file
- Solution: Increase -Xmx, or split BAM by region

### Empty Output
- Error: Pilon produces no changes
- Cause: No variants detected, or BAM alignment quality issues
- Solution: Check BAM alignment quality, verify read mapping rate

## Best Practices

1. Sort and index BAM file before running Pilon
2. Use BWA-MEM for alignment (not Bowtie2)
3. Run 2-3 rounds of Pilon for best results
4. Monitor memory usage and adjust -Xmx accordingly
5. For long-read assemblies: Racon first, then Pilon with Illumina

## Output Interpretation

- Polished FASTA file
- Changes file listing all corrections
- VCF file with variant calls
