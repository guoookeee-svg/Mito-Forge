# Mito-Forge Skill Constraints

## Hard Constraints (NEVER violate)

1. **Never fabricate annotation data**
   - If no annotation tool is available and no ORFs are found, return a failure status
   - Never generate gene positions based on genome length division
   - All gene positions must come from actual sequence analysis (tool output or ORF detection)

2. **Never expose API keys or secrets**
   - LLM API keys must be stored in environment variables or config files
   - Never log API keys in pipeline output
   - Use `sanitize_for_log()` for any user-facing output

3. **Never run untrusted commands**
   - Tool names must pass `validate_safe_name()` check
   - Parameters must be properly escaped with `shlex.quote()`
   - API base URLs must pass SSRF validation (`_validate_api_base()`)

4. **Never silently ignore critical failures**
   - If assembly produces 0 contigs, report failure explicitly
   - If annotation finds 0 genes, report failure explicitly
   - If all tools in a chain fail, report failure explicitly

5. **Never modify input data**
   - Raw reads must never be modified in-place
   - All intermediate files go to the output directory
   - Original files must remain untouched

## Soft Constraints (follow unless user overrides)

1. **Prefer offline tools over web services**
   - MITOS2 local > MITOS2 web
   - PMGA/MITOFY/BLAST+ > GeSeq (web service)
   - This ensures reproducibility and offline capability

2. **Prefer merge over fallback for plant annotation**
   - Run PMGA + MITOFY + BLAST+ simultaneously when possible
   - Merge results rather than using first-success fallback
   - Only fall back to ORF finder when all specialized tools fail

3. **Prefer rule-based diagnosis before LLM**
   - Match known error patterns from FAQ first (fast, reliable)
   - Only use LLM diagnosis for unknown error patterns
   - Always log which diagnosis path was taken

4. **Prefer semantic embedding when available**
   - sentence-transformers > Hash embedding for RAG
   - But Hash/BM25 must always work as zero-dependency fallback

5. **Prefer checkpoint-enabled execution**
   - Always use LangGraph checkpointer when available
   - Save checkpoints after each stage completion
   - Enable resume from any intermediate point

## Performance Constraints

1. **Memory**: SPAdes default 250GB limit may be excessive; auto-adjust to system memory
2. **Disk**: Warn if < 10GB free space before starting assembly
3. **Time**: Assembly may take 10min-2hr depending on data size; show progress
4. **Threads**: Default to min(8, cpu_count); never exceed system thread count

## Data Constraints

1. **Input formats**: FASTQ (.fastq/.fq/.fastq.gz), FASTA (.fasta/.fa/.fna)
2. **Output formats**: FASTA (assembly), GFF3 (annotation), JSON (report)
3. **Maximum input size**: No hard limit, but warn if > 50GB
4. **Reference genomes**: NCBI RefSeq accession or local FASTA path

## Security Constraints

1. **Path validation**: All file paths must pass `validate_file_path()` and `validate_within_dir()`
2. **Command injection**: All tool parameters must be properly escaped
3. **SSRF prevention**: API base URLs must not resolve to internal networks
4. **Config whitelist**: Only `_ALLOWED_CONFIG_KEYS` and `_ALLOWED_PROFILE_KEYS` accepted
5. **Log sanitization**: Use `sanitize_for_log()` for all user-visible output
