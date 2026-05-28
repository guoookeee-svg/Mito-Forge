# BLAST+ Homology Annotation

## Overview

BLAST+ can be used for homology-based annotation of mitochondrial genomes.
This is the most universal annotation approach but has lower precision than specialized tools.

## Key Tools

- blastx: Translate-nucleotide query, search protein database
- blastp: Protein query against protein database
- makeblastdb: Build BLAST databases from FASTA files
- blastn: Nucleotide search against nucleotide database

## Key Parameters

### blastx for Gene Annotation
- -evalue: E-value threshold (default 10, use 1e-5 for annotation)
- -max_target_seqs: Maximum hits per query (use 1 for best hit)
- -outfmt: Output format (use 6 for tabular, 5 for XML)
- -qcov_hsp_perc: Query coverage per HSP percentage (use 50+)

### Database Building
- makeblastdb -in proteins.fasta -dbtype prot -out mito_plant_db
- Parse_seqids recommended for tracking sequence IDs
- Build with -parse_seqids for consistent ID references

## Common Error Patterns

### No Hits Found
- Error: "No hits found" or zero significant matches
- Cause: Assembly contains non-mitochondrial sequences, or database lacks homologs
- Solution: Verify assembly origin, try more permissive e-value

### Database Format Error
- Error: "BLAST database error" or "database format error"
- Cause: Database not built properly or corrupted
- Solution: Rebuild database with makeblastdb

## Best Practices

1. Use curated mitochondrial protein databases (not nr)
2. Set appropriate e-value threshold (1e-5 for annotation)
3. Use blastx for nucleotide-against-protein search
4. Combine with tRNAscan-SE for complete annotation
5. Filter results by coverage and identity thresholds
6. Use as fallback when PMGA and MITOFY are unavailable

## Output Parsing

- Tabular format (outfmt 6): qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore
- Parse for gene boundaries, identity scores, and coverage
- Convert to GFF3 using custom parsing scripts
