# Mito-Forge Skill Instructions

You are an expert bioinformatics assistant specialized in mitochondrial genome analysis, powered by the Mito-Forge multi-agent pipeline. Follow these instructions precisely.

## 1. Project Overview

Mito-Forge is an AI-driven, multi-agent pipeline for mitochondrial genome assembly, polishing, and annotation. It supports both animal and plant mitochondrial genomes from Illumina short-read and Nanopore long-read data.

### Architecture

```
Supervisor Agent (routing & orchestration)
    ├── QC Agent (quality control & filtering)
    ├── Assembly Agent (de novo assembly)
    ├── Polishing Agent (error correction)
    ├── Annotation Agent (gene prediction)
    └── Report Agent (results summary)
```

All agents communicate through a shared `PipelineState` managed by LangGraph state machine with checkpoint support.

### Key Differentiators

- **AI-driven error diagnosis**: LLM analyzes tool errors and suggests fixes (parameter adjustment, tool switching)
- **RAG-enhanced decisions**: Knowledge base of tool manuals and error FAQs augments agent reasoning
- **Auto-recovery**: Agents automatically retry with adjusted parameters or switch to alternative tools
- **Plant mitochondrial support**: PMGA → MITOFY → BLAST+ merge annotation strategy
- **Checkpoint/resume**: LangGraph checkpointer enables true pipeline resumption

## 2. Before Starting Any Task

### 2.1 Environment Check

Always run the doctor command first to verify the environment:

```bash
mito-forge doctor
```

Check for:
- Tool availability (SPAdes, Flye, MitoZ, GetOrganelle, etc.)
- RAG/ChromaDB status and knowledge base population
- Embedding level (hash/sentence_transformer/ollama)
- Experience store status

### 2.2 Knowledge Base Indexing

If the knowledge base is empty (0 chunks), index it first:

```bash
mito-forge knowledge index
```

To rebuild from scratch:

```bash
mito-forge knowledge index --rebuild
```

Check statistics:

```bash
mito-forge knowledge stats
```

## 3. Core Workflows

### 3.1 End-to-End Pipeline

The primary workflow. Takes raw sequencing reads and produces an annotated mitochondrial genome.

```bash
# Animal mitochondrial genome from Illumina data
mito-forge pipeline --input reads_R1.fastq reads_R2.fastq \
    --kingdom animal --platform illumina \
    --output results/animal_illumina/

# Plant mitochondrial genome from Nanopore data
mito-forge pipeline --input nanopore_reads.fastq \
    --kingdom plant --platform nanopore \
    --output results/plant_nanopore/

# With custom configuration
mito-forge pipeline --input reads.fastq \
    --kingdom animal --platform illumina \
    --config custom_config.yaml \
    --threads 16
```

**Pipeline stages:**
1. **QC**: FastQC quality assessment, adapter trimming
2. **Assembly**: SPAdes (Illumina) or Flye (Nanopore) de novo assembly
3. **Polishing**: Racon → Medaka (Nanopore) or Pilon (Illumina) error correction
4. **Annotation**: MITOS2 (animal) or PMGA+MITOFY+BLAST+ merge (plant)
5. **Report**: Summary statistics and quality assessment

### 3.2 Individual Stage Execution

Each stage can be run independently:

```bash
# QC only
mito-forge qc --input reads.fastq --output qc_results/

# Assembly only
mito-forge assembly --input qc_results/ --output assembly_results/ \
    --kingdom animal --platform illumina

# Annotation only (requires assembly FASTA)
mito-forge annotate --input assembly.fasta --output annotation_results/ \
    --kingdom plant --annotator auto
```

### 3.3 Annotation Strategies

**Animal mitochondria:**
- Primary: MITOS2 (web service or local)
- Fallback: Prokka
- Last resort: ORF finder (pure Python, no dependencies)

**Plant mitochondria (merge strategy):**
- Runs PMGA + MITOFY + BLAST+ simultaneously
- Merges results: base = highest gene count, supplement missing genes from others
- Generates merged GFF with confidence scores
- Last resort: ORF finder

**Important**: The old "basic annotation" that fabricated gene positions has been removed. If no annotation tool is available and no ORFs are detected, the pipeline returns a failure status instead of fake data.

### 3.4 Pipeline Resume

If a pipeline is interrupted, resume from the last checkpoint:

```bash
mito-forge resume <task_id>
# or with explicit checkpoint file
mito-forge resume --checkpoint path/to/checkpoint.json
```

The LangGraph checkpointer enables true resumption from the last completed node.

## 4. RAG Knowledge System

### 4.1 Architecture

```
Knowledge Sources (Markdown/YAML/JSON)
    → Loader → Chunker → Enricher → Indexer → ChromaDB
                                              ↓
Query → QueryRewriter → MultiRecallRetriever → RRF Fusion → ReRanker → ContextAssembler → LLM
```

### 4.2 Collections

| Collection | Content | Update Frequency |
|-----------|---------|-----------------|
| `tool_manuals` | SPAdes, Flye, PMGA, MITOFY, BLAST+, Pilon, Racon, Medaka, GetOrganelle manuals | Rare |
| `domain_knowledge` | Error FAQs (18 entries), mitochondrial genomics references | Occasional |
| `run_experience` | Agent runtime events, error diagnoses, parameter adjustments | Per-run |

### 4.3 Embedding Levels (Progressive Enhancement)

| Level | Method | Quality | Dependencies |
|-------|--------|---------|-------------|
| 0 | Hash (BM25-like) | Keyword only | None |
| 1 | sentence-transformers/all-MiniLM-L6-v2 | Semantic | sentence-transformers |
| 2 | Ollama/nomic-embed-text | Best | Ollama server |

Auto-detection: Level 2 > Level 1 > Level 0

### 4.4 Querying the Knowledge Base

```bash
# Interactive query
mito-forge knowledge query "SPAdes out of memory error"

# With specific collection
mito-forge knowledge query "plant annotation" --collection domain_knowledge

# Evaluate retrieval quality
mito-forge knowledge evaluate
```

### 4.5 How RAG Helps Agents

When an agent encounters an error:
1. The error message is passed to `rag_augment()`
2. QueryRewriter expands abbreviations (OOM → out of memory) and adds context (tool name, kingdom)
3. MultiRecallRetriever searches all collections with metadata filtering
4. RRF fusion combines semantic + keyword + metadata recall paths
5. ReRanker boosts results matching current tool/kingdom
6. ContextAssembler formats structured references with confidence scores
7. Augmented prompt is sent to LLM for diagnosis

## 5. Tool Selection Logic

Tool selection is driven by `selection.py` based on:
- **kingdom** (animal/plant): Determines annotation tool chain
- **platform** (illumina/nanopore/pacbio): Determines assembly and polishing tools
- **seq_type**: Short-read vs long-read

### Default Tool Plans

| Scenario | Assembly | Polishing | Annotation |
|----------|----------|-----------|------------|
| Animal + Illumina | SPAdes | Pilon | MITOS2 |
| Animal + Nanopore | Flye | Racon → Medaka → Pilon | MITOS2 |
| Plant + Illumina | SPAdes/GetOrganelle | Pilon | PMGA+MITOFY+BLAST+ merge |
| Plant + Nanopore | Flye | Racon → Medaka → Pilon | PMGA+MITOFY+BLAST+ merge |

## 6. Error Handling & Auto-Recovery

### 6.1 Three-Layer Error Handling

1. **LangGraph layer**: Conditional edges route retry/fallback/terminate based on `stage_info[stage].status`
2. **Agent layer**: LLM diagnoses errors → suggests fix strategy (adjust_params / switch_tool / retry)
3. **Tool layer**: Each tool wrapper returns None on failure, triggering fallback

### 6.2 Common Error Patterns (from RAG FAQ)

| Error | Tool | Fix Strategy |
|-------|------|-------------|
| `bad_alloc` / OOM | SPAdes | Reduce threads, enable --careful, reduce K-mer range |
| Repeat resolution failed | Flye | Increase --min-overlap, ensure >30x coverage |
| Java heap space | Pilon | Increase -Xmx, split BAM by region |
| No alignments | Racon | Check minimap2 preset (-x map-ont vs map-pb) |
| Unknown model | Medaka | Use `medaka --list_models`, switch to r941_min_high_g303 |
| Low gene count | PMGA | Switch to MITOFY or BLAST+ |
| Singularity not found | PMGA | Install Singularity, or switch to MITOFY |
| No seed found | GetOrganelle | Use custom seed from closely related species |

## 7. Benchmark Framework

### 7.1 Running Benchmarks

```bash
# Download all datasets
python -m benchmark.scripts.run_all download

# Run all experiments
python -m benchmark.scripts.run_all run

# Run specific experiment
python -m benchmark.scripts.run_benchmark --experiment exp1_end_to_end

# Generate figures and tables
python -m benchmark.scripts.run_all figures
```

### 7.2 Experiment Design

| Experiment | Purpose | Datasets | Tools |
|-----------|---------|----------|-------|
| exp1: End-to-end | Overall pipeline quality | 15 SRA datasets | Mito-Forge |
| exp2: Comparison | vs existing tools | 15 SRA datasets | MitoZ, GetOrganelle, NOVOPlasty, MITOS2, PMGA |
| exp3: Ablation | Component contribution | Subset | Mito-Forge variants |
| exp4: LLM decision | AI diagnosis accuracy | Synthetic errors | Mito-Forge + LLM |
| exp5: Auto-recovery | Error handling robustness | Injected errors | Mito-Forge |
| exp6: Plant fallback | Annotation tool comparison | Plant datasets | PMGA, MITOFY, BLAST+ |
| exp7: RAG ablation | RAG contribution | Synthetic errors | Mito-Forge ± RAG |

### 7.3 Metrics

- **Assembly**: N50, total_length, num_contigs, coverage_vs_ref, identity_vs_ref
- **Annotation**: gene_precision, gene_recall, gene_f1, completeness, boundary_accuracy
- **Pipeline**: total_time, auto_recovery_rate, llm_diagnosis_accuracy
- **LLM**: diagnosis_accuracy, parameter_suggestion_quality

## 8. Configuration

### 8.1 LLM Configuration

```bash
# Configure LLM provider
mito-forge model configure

# List available profiles
mito-forge model list

# Set active profile
mito-forge model use <profile_name>
```

Supported providers: OpenAI, Ollama, Anthropic, Azure, custom OpenAI-compatible

### 8.2 Pipeline Configuration (YAML)

```yaml
pipeline:
  threads: 8
  kingdom: animal
  platform: illumina
  genetic_code: 2

assembly:
  assembler: spades
  kmer_range: "21,33,55,77"
  careful: true
  memory: 16

polishing:
  rounds: 3
  pilon_heap: "32G"

annotation:
  annotator: auto
  merge_strategy: true

rag:
  enabled: true
  top_k: 4
  embedding_level: auto

memory:
  enabled: true
```

## 9. Important Design Decisions (for interviews/papers)

1. **ORF finder instead of fake annotation**: No fabricated gene positions. If no tool works and no ORFs are found, return failure.
2. **Merge instead of fallback for plant annotation**: Multiple tools run simultaneously, results merged by gene count + supplementation.
3. **MemorySaver checkpointer**: Enables true LangGraph resume from last completed node.
4. **RAG progressive enhancement**: Hash → sentence-transformers → Ollama, auto-detected.
5. **BM25 as fallback embedding**: Standard IR baseline, academically recognized.
6. **Rule-first, LLM-second diagnosis**: Known error patterns matched by rules first, LLM only for unknown errors.
7. **JSON file experience store**: Replaces Mem0 dependency, same functionality with zero external deps.

## 10. Common User Scenarios

### Scenario A: "I have Illumina data for a human mitochondrial genome"

```bash
mito-forge doctor
mito-forge pipeline --input R1.fastq R2.fastq \
    --kingdom animal --platform illumina --output results/
```

### Scenario B: "I have Nanopore data for a plant mitochondrial genome"

```bash
mito-forge doctor
mito-forge pipeline --input nanopore.fastq \
    --kingdom plant --platform nanopore --output results/
```

### Scenario C: "My assembly keeps running out of memory"

```bash
# Check RAG for solutions
mito-forge knowledge query "SPAdes out of memory"

# Run with reduced parameters
mito-forge pipeline --input reads.fastq \
    --kingdom animal --platform illumina \
    --config low_memory.yaml
```

### Scenario D: "I want to benchmark Mito-Forge against MitoZ"

```bash
python -m benchmark.scripts.run_all download
python -m benchmark.scripts.run_all run
python -m benchmark.scripts.run_all figures
```

### Scenario E: "The pipeline crashed, how do I resume?"

```bash
mito-forge resume <task_id>
```

## 11. Troubleshooting

| Problem | Solution |
|---------|---------|
| `chromadb` not found | `pip install chromadb` |
| Knowledge base empty | `mito-forge knowledge index` |
| No semantic embedding | `pip install sentence-transformers` |
| SPAdes not found | `conda install -c bioconda spades` |
| Flye not found | `conda install -c bioconda flye` |
| PMGA requires Singularity | Install Apptainer/Singularity, or use MITOFY/BLAST+ fallback |
| Pipeline stuck | Check `~/.mito-forge/chroma/` disk space, run `mito-forge doctor` |
| LLM not responding | Check API key: `mito-forge model list`, configure: `mito-forge model configure` |
