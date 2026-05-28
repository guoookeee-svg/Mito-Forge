# Mito-Forge Skill Scenarios

This file defines the scenarios that the Mito-Forge skill handles, including
expected inputs, decision logic, and output formats.

---

## Scenario 1: End-to-End Pipeline Execution

**User intent**: "I have sequencing data and want a complete mitochondrial genome"

**Decision tree**:

```
User provides sequencing data
    │
    ├─ Is it paired-end Illumina?
    │   ├─ YES → platform=illumina, assembler=SPAdes, polisher=Pilon
    │   └─ NO → Is it Nanopore/PacBio?
    │       ├─ YES → platform=nanopore, assembler=Flye, polisher=Racon+Medaka
    │       └─ UNKNOWN → Ask user or auto-detect from file format
    │
    ├─ What organism?
    │   ├─ Animal → kingdom=animal, annotator=MITOS2
    │   ├─ Plant → kingdom=plant, annotator=PMGA+MITOFY+BLAST+ merge
    │   └─ UNKNOWN → Ask user
    │
    └─ Execute pipeline
        ├─ QC → Assembly → Polishing → Annotation → Report
        └─ Auto-recover from errors using RAG + LLM diagnosis
```

**Pre-flight checks**:
1. Run `mito-forge doctor` to verify environment
2. Run `mito-forge knowledge index` if knowledge base is empty
3. Verify disk space (assembly can use 10-50GB)
4. Verify memory (SPAdes needs 8-32GB)

**Output**: Annotated mitochondrial genome (FASTA + GFF + report)

---

## Scenario 2: Error Diagnosis and Recovery

**User intent**: "My assembly/annotation failed with an error"

**Decision tree**:

```
Agent encounters error
    │
    ├─ Can RAG find matching FAQ?
    │   ├─ YES → Use FAQ suggestion (high confidence)
    │   └─ NO → Use LLM diagnosis
    │       ├─ LLM suggests adjust_params → Apply and retry
    │       ├─ LLM suggests switch_tool → Switch and retry
    │       └─ LLM suggests retry → Retry with same params
    │
    ├─ Retry succeeded?
    │   ├─ YES → Continue pipeline
    │   └─ NO → Try next fallback tool
    │       ├─ Fallback succeeded?
    │       │   ├─ YES → Continue with warning
    │       │   └─ NO → Mark stage as failed, report to user
    │
    └─ Write experience to memory for future runs
```

**Common error patterns** (from RAG knowledge base):

| Error Pattern | Tool | Auto-Fix |
|--------------|------|----------|
| `bad_alloc` / OOM | SPAdes | Reduce threads, --careful, smaller K-mers |
| `repeat resolution failed` | Flye | Increase --min-overlap, check coverage |
| `Java heap space` | Pilon | Increase -Xmx to 32G+ |
| `zero overlaps` | Racon | Fix minimap2 preset |
| `unknown model` | Medaka | Use r941_min_high_g303 |
| `low gene count` | PMGA | Switch to MITOFY/BLAST+ |
| `no seed found` | GetOrganelle | Use custom seed from related species |
| `Singularity not found` | PMGA | Switch to MITOFY or install Apptainer |

---

## Scenario 3: Plant Mitochondrial Genome Annotation

**User intent**: "I need to annotate a plant mitochondrial genome"

**Decision tree**:

```
Plant annotation request
    │
    ├─ Run PMGA (if available)
    │   ├─ SUCCESS → Collect PMGA results
    │   └─ FAIL → Log unavailability
    │
    ├─ Run MITOFY (if available)
    │   ├─ SUCCESS → Collect MITOFY results
    │   └─ FAIL → Log unavailability
    │
    ├─ Run BLAST+ (if available)
    │   ├─ SUCCESS → Collect BLAST+ results
    │   └─ FAIL → Log unavailability
    │
    ├─ Any results collected?
    │   ├─ YES → Merge annotations
    │   │   ├─ Base = highest gene count result
    │   │   ├─ Supplement with genes from other tools
    │   │   ├─ Generate merged GFF with confidence scores
    │   │   └─ Return merged result
    │   │
    │   └─ NO → Try ORF finder fallback
    │       ├─ ORFs found? → Assign to genes by length heuristics
    │       └─ No ORFs → Return failure (no fabricated data)
    │
    └─ Write experience to memory
```

**Why merge instead of fallback**:
- PMGA may find 24 protein genes but miss some rRNA
- MITOFY may find different genes due to BLAST-based approach
- BLAST+ may find genes missed by both specialized tools
- Merging takes the union, giving the most complete annotation

---

## Scenario 4: Knowledge Base Management

**User intent**: "I want to query/manage the knowledge base"

**Available commands**:

```bash
# Index all knowledge sources
mito-forge knowledge index

# Rebuild from scratch (clears existing index)
mito-forge knowledge index --rebuild

# Use semantic embedding (requires sentence-transformers)
mito-forge knowledge index --embedding-level sentence_transformer

# View statistics
mito-forge knowledge stats

# Query the knowledge base
mito-forge knowledge query "SPAdes memory error"

# Evaluate retrieval quality
mito-forge knowledge evaluate
```

**Knowledge base structure**:

```
~/.mito-forge/
├── chroma/                    # ChromaDB vector store
│   ├── tool_manuals/          # Tool documentation chunks
│   ├── domain_knowledge/      # Error FAQs + genomics references
│   └── run_experience/        # Agent runtime experiences
└── experience/                # JSON experience files
    ├── assembly_1718900000.json
    ├── annotation_1718900100.json
    └── ...
```

---

## Scenario 5: Benchmark and Comparison

**User intent**: "I want to compare Mito-Forge against other tools"

**Steps**:

1. **Download datasets**: `python -m benchmark.scripts.run_all download`
2. **Run experiments**: `python -m benchmark.scripts.run_all run`
3. **Generate figures**: `python -m benchmark.scripts.run_all figures`

**7 experiment types**:

| # | Experiment | What it tests |
|---|-----------|---------------|
| 1 | End-to-end | Overall pipeline quality on 15 datasets |
| 2 | Comparison | vs MitoZ, GetOrganelle, NOVOPlasty, MITOS2, PMGA |
| 3 | Ablation | Remove components (RAG, LLM, memory) one at a time |
| 4 | LLM decision | AI diagnosis accuracy on synthetic errors |
| 5 | Auto-recovery | Error handling with injected failures |
| 6 | Plant fallback | PMGA vs MITOFY vs BLAST+ on plant data |
| 7 | RAG ablation | With vs without RAG, Hash vs semantic embedding |

**Output**: PDF/PNG figures + LaTeX tables suitable for Bioinformatics journal

---

## Scenario 6: Pipeline Resume After Crash

**User intent**: "My pipeline crashed, how do I continue?"

**Steps**:

```bash
# Find the task ID from previous run
ls ~/.mito-forge/checkpoints/

# Resume from checkpoint
mito-forge resume <task_id>

# Or with explicit checkpoint file
mito-forge resume --checkpoint /path/to/checkpoint.json
```

**How it works**:
1. LangGraph checkpointer saves state after each node execution
2. On resume, loads checkpoint and invokes graph with saved state
3. Route decisions check `stage_info[stage].status` to skip completed stages
4. Only uncompleted stages are re-executed

---

## Scenario 7: Custom Tool Configuration

**User intent**: "I want to use specific tools or parameters"

**Via command-line flags**:
```bash
mito-forge pipeline --input reads.fastq \
    --kingdom plant --platform illumina \
    --assembler getorganelle \
    --annotator pmga \
    --threads 16
```

**Via YAML config file**:
```yaml
# custom_config.yaml
pipeline:
  threads: 16
  kingdom: plant
  platform: illumina

assembly:
  assembler: getorganelle
  kmer_range: "21,33,55"

annotation:
  annotator: pmga
  merge_strategy: true

rag:
  enabled: true
  top_k: 5
  embedding_level: sentence_transformer
```

```bash
mito-forge pipeline --input reads.fastq --config custom_config.yaml
```
