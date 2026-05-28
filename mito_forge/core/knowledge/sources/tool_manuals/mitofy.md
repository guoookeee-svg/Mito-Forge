# MITOFY - Plant Mitochondrial Genome Identification

## Overview

MITOFY is a tool for identifying and annotating mitochondrial genes in plant genomes.
It uses BLAST-based homology search against curated protein databases.

## Requirements

- Perl 5.10+
- BLAST+ (makeblastdb, blastx, blastp)
- tRNAscan-SE (optional, for tRNA detection)

## Key Parameters

### BLAST Parameters
- E-value threshold: default 1e-5
- For more sensitive search: use 1e-3
- For faster search: use 1e-10

### Database Configuration
- Uses custom BLAST protein databases
- Set BLASTDB environment variable for database location
- Databases can be built from NCBI RefSeq plant mitochondrial proteins

## Common Error Patterns

### BLAST Database Not Found
- Error: "BLAST database error" or "cannot find database"
- Cause: Required BLAST database not built or not in path
- Solution: Build database with makeblastdb, set BLASTDB env var

### No Genes Detected
- Error: Zero genes found in annotation
- Cause: Assembly may not be mitochondrial, or database lacks related species
- Solution: Verify assembly origin, try BLAST+ with broader database

## Best Practices

1. Build BLAST databases before running MITOFY
2. Use tRNAscan-SE for complementary tRNA detection
3. Cross-validate with PMGA when available
4. Good for non-seed plants where PMGA reference is limited
5. Can detect partial genes that PMGA might miss

## Output Format

- Tab-delimited gene list
- Can be converted to GFF3 format
- Includes gene boundaries, scores, and strand information
