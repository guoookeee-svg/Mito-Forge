# Mito-Forge: Mitochondrial Genome Assembly Skill

You are now operating with the **mito-forge** skill activated. This skill enables you to perform complete mitochondrial genome assembly, polishing, and annotation from raw sequencing data.

## CRITICAL RULES

1. **NEVER fabricate gene positions** — all annotation must come from real tool output or ORF detection
2. **NEVER modify input data** — all intermediate files go to the output directory
3. **ALWAYS check environment first** — run doctor before starting any pipeline
4. **ALWAYS validate results** — check assembly stats and annotation completeness before reporting success
5. **ALWAYS prefer offline tools** — use local tools over web services for reproducibility

---

## STEP 0: Determine User Requirements

Before doing anything, clarify these with the user (use reasonable defaults if they don't specify):

| Parameter | Options | Default |
|-----------|---------|---------|
| Input data | FASTQ file path(s) | **MUST ask** |
| Organism type | animal / plant | **MUST ask** |
| Sequencing platform | illumina / nanopore | Auto-detect from data |
| Output directory | Path | `./mito_forge_output/` |
| Threads | Integer | `min(8, cpu_count)` |
| Genetic code | Integer | 2 (vertebrate mitochondrial) |

**Auto-detection logic for platform:**
- If user provides 2 paired FASTQ files → illumina
- If user provides 1 FASTQ file with long reads (>1kb average) → nanopore
- If ambiguous → ask user

---

## STEP 1: Environment Setup

### 1.1 Check Environment

```bash
cd /workspace && python -m mito_forge.cli.main doctor
```

Verify:
- [x] SPAdes or Flye installed (for assembly)
- [x] minimap2 / BWA installed (for polishing alignment)
- [x] Pilon / Racon / Medaka installed (for polishing)
- [x] BLAST+ installed (for annotation)
- [x] ChromaDB available (for RAG)
- [x] Knowledge base has indexed chunks

### 1.2 Index Knowledge Base (if empty)

```bash
cd /workspace && python -m mito_forge.cli.main knowledge stats
```

If total chunks = 0:
```bash
cd /workspace && python -m mito_forge.cli.main knowledge index
```

### 1.3 Install Missing Tools (if needed)

If critical tools are missing, install via conda:
```bash
# Assembly tools
conda install -c bioconda spades flye -y

# Polishing tools
conda install -c bioconda pilon racon medaka -y

# Annotation tools
conda install -c bioconda blast getorganelle -y

# Utility tools
conda install -c bioconda fastqc bwa samtools minimap2 -y
```

---

## STEP 2: Data Preparation

### 2.1 Download from SRA (if user provides SRA accession)

```bash
# Download SRA data
prefetch SRRXXXXXXX
fasterq-dump SRRXXXXXXX --split-files -O ./input_data/

# For paired-end Illumina
# Output: SRRXXXXXXX_1.fastq, SRRXXXXXXX_2.fastq
```

### 2.2 Validate Input Data

```bash
# Check file format and size
file input_data/*.fastq
ls -lh input_data/

# Quick quality check
fastqc input_data/*.fastq -o qc_preview/
```

**Validation criteria:**
- Files must be valid FASTQ format
- File size > 0
- For Illumina: must have _1 and _2 paired files
- For Nanopore: single file with reads > 1kb average length

If validation fails → report to user and stop.

---

## STEP 3: Quality Control

### 3.1 Run FastQC

```bash
mkdir -p ${OUTPUT_DIR}/qc
fastqc ${INPUT_FILES} -o ${OUTPUT_DIR}/qc/ -t ${THREADS}
```

### 3.2 Trim Adapters (Illumina only)

```bash
# Using Trimmomatic
trimmomatic PE -threads ${THREADS} \
    ${INPUT_R1} ${INPUT_R2} \
    ${OUTPUT_DIR}/qc/trimmed_R1_paired.fastq ${OUTPUT_DIR}/qc/trimmed_R1_unpaired.fastq \
    ${OUTPUT_DIR}/qc/trimmed_R2_paired.fastq ${OUTPUT_DIR}/qc/trimmed_R2_unpaired.fastq \
    ILLUMINACLIP:TruSeq3-PE.fa:2:30:10 \
    LEADING:3 TRAILING:3 SLIDINGWINDOW:4:20 MINLEN:50
```

**Decision:**
- If >80% reads survive trimming → proceed with trimmed reads
- If <50% reads survive → warn user, use untrimmed reads
- For Nanopore: skip trimming, use raw reads

---

## STEP 4: Assembly

### 4.1 Illumina Assembly (SPAdes)

```bash
mkdir -p ${OUTPUT_DIR}/assembly

# For animal mitochondrial genome
spades.py -1 ${TRIMMED_R1} -2 ${TRIMMED_R2} \
    -o ${OUTPUT_DIR}/assembly/spades \
    -t ${THREADS} -m ${MEMORY} \
    --careful \
    -k 21,33,55,77

# For plant mitochondrial genome (larger, more complex)
spades.py -1 ${TRIMMED_R1} -2 ${TRIMMED_R2} \
    -o ${OUTPUT_DIR}/assembly/spades \
    -t ${THREADS} -m ${MEMORY} \
    --careful \
    -k 21,33,55
```

**Error handling:**
- If OOM (`bad_alloc`): reduce `-t` to half, add `--memory 16`, reduce K-mers to `21,33,55`
- If low coverage warning: add `--disable-corr`, use smaller K-mers
- If SPAdes completely fails: try GetOrganelle (see 4.3)

### 4.2 Nanopore Assembly (Flye)

```bash
mkdir -p ${OUTPUT_DIR}/assembly

# For animal mitochondrial genome
flye --nano-raw ${INPUT_FASTQ} \
    -o ${OUTPUT_DIR}/assembly/flye \
    --genome-size 16k \
    -t ${THREADS} \
    --no-chimera-detection

# For plant mitochondrial genome
flye --nano-raw ${INPUT_FASTQ} \
    -o ${OUTPUT_DIR}/assembly/flye \
    --genome-size 400k \
    -t ${THREADS}
```

**Error handling:**
- If repeat resolution fails: increase `--min-overlap 5000`
- If assembly too short: check if reads are mitochondrial, adjust `--genome-size`
- If Flye fails: try Canu or report to user

### 4.3 Alternative: GetOrganelle (targeted assembly)

Use when SPAdes/Flye produce contaminated or incomplete assemblies:

```bash
# Animal mitochondrial
get_organelle.py -1 ${TRIMMED_R1} -2 ${TRIMMED_R2} \
    -R ${REFERENCE_SEEDS} \
    -t ${THREADS} \
    -F animal_mt \
    -o ${OUTPUT_DIR}/assembly/getorganelle

# Plant mitochondrial
get_organelle.py -1 ${TRIMMED_R1} -2 ${TRIMMED_R2} \
    -R ${REFERENCE_SEEDS} \
    -t ${THREADS} \
    -F plant_mt \
    -o ${OUTPUT_DIR}/assembly/getorganelle
```

### 4.4 Assembly Validation

After assembly, validate the result:

```bash
# Check assembly statistics
cd /workspace && python -c "
from mito_forge.utils.assembly_stats import get_assembly_stats
stats = get_assembly_stats('${OUTPUT_DIR}/assembly/*/contigs.fasta')
print(f'N50: {stats[\"n50\"]}')
print(f'Total length: {stats[\"total_length\"]}')
print(f'Num contigs: {stats[\"num_contigs\"]}')
"

# Expected lengths:
# Animal mitochondrial: 14-20 kb
# Plant mitochondrial: 200-800 kb
```

**Decision:**
- If assembly length is within expected range → proceed to polishing
- If assembly is much shorter → may be incomplete, try different assembler
- If assembly is much longer → may contain contamination, try GetOrganelle
- If 0 contigs → assembly failed, try alternative tool or report to user

---

## STEP 5: Polishing

### 5.1 Nanopore Polishing (Racon + Medaka)

```bash
mkdir -p ${OUTPUT_DIR}/polishing
ASSEMBLY=${OUTPUT_DIR}/assembly/flye/assembly.fasta
READS=${INPUT_FASTQ}

# Round 1: Racon
minimap2 -x map-ont -t ${THREADS} ${ASSEMBLY} ${READS} > ${OUTPUT_DIR}/polishing/align1.paf
racon -t ${THREADS} ${READS} ${OUTPUT_DIR}/polishing/align1.paf ${ASSEMBLY} > ${OUTPUT_DIR}/polishing/racon1.fasta

# Round 2: Racon
minimap2 -x map-ont -t ${THREADS} ${OUTPUT_DIR}/polishing/racon1.fasta ${READS} > ${OUTPUT_DIR}/polishing/align2.paf
racon -t ${THREADS} ${READS} ${OUTPUT_DIR}/polishing/align2.paf ${OUTPUT_DIR}/polishing/racon1.fasta > ${OUTPUT_DIR}/polishing/racon2.fasta

# Round 3: Racon
minimap2 -x map-ont -t ${THREADS} ${OUTPUT_DIR}/polishing/racon2.fasta ${READS} > ${OUTPUT_DIR}/polishing/align3.paf
racon -t ${THREADS} ${READS} ${OUTPUT_DIR}/polishing/align3.paf ${OUTPUT_DIR}/polishing/racon2.fasta > ${OUTPUT_DIR}/polishing/racon3.fasta

# Medaka polishing
medaka_consensus -i ${READS} -d ${OUTPUT_DIR}/polishing/racon3.fasta \
    -o ${OUTPUT_DIR}/polishing/medaka \
    -t ${THREADS} -m r941_min_high_g303
```

**Error handling:**
- If Racon reports 0 overlaps: check minimap2 preset (`-x map-ont` vs `-x map-pb`)
- If Medaka model not found: run `medaka --list_models` and use an available model
- If Java OOM in Pilon: increase `-Xmx` to 32G+

### 5.2 Illumina Polishing (Pilon)

```bash
# Align Illumina reads to assembly
bwa index ${ASSEMBLY}
bwa mem -t ${THREADS} ${ASSEMBLY} ${TRIMMED_R1} ${TRIMMED_R2} | \
    samtools sort -@ ${THREADS} -o ${OUTPUT_DIR}/polishing/aligned.bam
samtools index ${OUTPUT_DIR}/polishing/aligned.bam

# Run Pilon
java -Xmx32G -jar $(which pilon) \
    --genome ${ASSEMBLY} \
    --frags ${OUTPUT_DIR}/polishing/aligned.bam \
    --output ${OUTPUT_DIR}/polishing/pilon \
    --threads ${THREADS} \
    --fix all
```

### 5.3 Hybrid Polishing (if both Illumina and Nanopore available)

```bash
# 1. Flye assembly
# 2. Racon (3 rounds with Nanopore)
# 3. Medaka (with Nanopore)
# 4. Pilon (with Illumina) — final polish
```

---

## STEP 6: Annotation

### 6.1 Animal Mitochondrial Annotation (MITOS2)

```bash
mkdir -p ${OUTPUT_DIR}/annotation

# Try MITOS2 first
mitos2.py -i ${POLISHED_ASSEMBLY} -o ${OUTPUT_DIR}/annotation/mitos2 \
    --genetic_code 2 --linear

# If MITOS2 fails, try Prokka
prokka --kingdom Mitochondria --genetic_code 2 \
    --outdir ${OUTPUT_DIR}/annotation/prokka \
    --prefix mito_annotation \
    --cpus ${THREADS} \
    ${POLISHED_ASSEMBLY}

# If both fail, use ORF finder
cd /workspace && python -c "
from mito_forge.tools.orf_annotator import run_orf_annotation
from pathlib import Path
result = run_orf_annotation(
    '${POLISHED_ASSEMBLY}',
    Path('${OUTPUT_DIR}/annotation/orf'),
    'animal',
    genetic_code=2,
)
if result:
    print(f'ORF annotation: {result[\"total_genes\"]} genes found')
else:
    print('No ORFs detected — annotation failed')
"
```

### 6.2 Plant Mitochondrial Annotation (Merge Strategy)

**Run all three tools simultaneously, then merge:**

```bash
mkdir -p ${OUTPUT_DIR}/annotation/{pmga,mitofy,blast,merged}

# Tool 1: PMGA (if Singularity available)
cd /workspace && python -c "
from mito_forge.tools.pmga import run_pmga
result = run_pmga('${POLISHED_ASSEMBLY}', Path('${OUTPUT_DIR}/annotation/pmga'), 'plant')
print(f'PMGA: {result}' if result else 'PMGA: unavailable')
"

# Tool 2: MITOFY
cd /workspace && python -c "
from mito_forge.tools.mitofy import run_mitofy
result = run_mitofy('${POLISHED_ASSEMBLY}', Path('${OUTPUT_DIR}/annotation/mitofy'), 'plant')
print(f'MITOFY: {result}' if result else 'MITOFY: unavailable')
"

# Tool 3: BLAST+ homology annotation
cd /workspace && python -c "
from mito_forge.tools.blast_annotator import run_blast_annotation
result = run_blast_annotation('${POLISHED_ASSEMBLY}', Path('${OUTPUT_DIR}/annotation/blast'), 'plant')
print(f'BLAST+: {result}' if result else 'BLAST+: unavailable')
"

# Merge annotations
cd /workspace && python -c "
from mito_forge.core.agents.annotation_agent import AnnotationAgent
agent = AnnotationAgent()
# Collect results from each tool and merge
# The merge strategy uses highest-gene-count as base,
# supplements with genes from other tools
"
```

**If ALL tools fail → ORF finder fallback:**
```bash
cd /workspace && python -c "
from mito_forge.tools.orf_annotator import run_orf_annotation
from pathlib import Path
result = run_orf_annotation(
    '${POLISHED_ASSEMBLY}',
    Path('${OUTPUT_DIR}/annotation/orf'),
    'plant',
    genetic_code=2,
)
if result:
    print(f'ORF annotation: {result[\"total_genes\"]} genes found')
    for g in result.get('gene_details', []):
        print(f'  {g[\"gene_name\"]}: {g[\"start\"]}-{g[\"end\"]} (confidence={g[\"confidence\"]})')
else:
    print('No ORFs detected — assembly may not be mitochondrial')
"
```

### 6.3 Annotation Validation

```bash
# Check annotation completeness
cd /workspace && python -c "
# Expected gene counts:
# Animal: 13 protein + 22 tRNA + 2 rRNA = 37 genes
# Plant: 24+ protein + 22 tRNA + 3 rRNA = 49+ genes

# Read GFF and count genes
from pathlib import Path
gff_file = Path('${OUTPUT_DIR}/annotation/merged/merged_annotation.gff')
if gff_file.exists():
    genes = {'CDS': 0, 'tRNA': 0, 'rRNA': 0}
    for line in gff_file.read_text().splitlines():
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 3:
            genes[parts[2]] = genes.get(parts[2], 0) + 1
    print(f'Annotation: {genes}')
else:
    print('No merged annotation file found')
"
```

---

## STEP 7: Report Generation

### 7.1 Generate Summary Report

```bash
cd /workspace && python -c "
import json
from pathlib import Path

report = {
    'pipeline': 'mito-forge',
    'kingdom': '${KINGDOM}',
    'platform': '${PLATFORM}',
    'assembly': {
        'file': '${OUTPUT_DIR}/polishing/final.fasta',
        # Add assembly stats
    },
    'annotation': {
        'file': '${OUTPUT_DIR}/annotation/merged/merged_annotation.gff',
        # Add annotation stats
    },
}

report_path = Path('${OUTPUT_DIR}/report.json')
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
print(f'Report saved to {report_path}')
"
```

### 7.2 Key Metrics to Report

| Metric | How to measure | Expected range (animal) | Expected range (plant) |
|--------|---------------|----------------------|---------------------|
| Assembly length | Count FASTA bases | 14-20 kb | 200-800 kb |
| Assembly N50 | get_assembly_stats | ≈ genome length | ≈ genome length |
| Num contigs | Count FASTA records | 1 (circular) | 1-5 |
| Protein genes | Count CDS in GFF | 13 | 24+ |
| tRNA genes | Count tRNA in GFF | 22 | 22 |
| rRNA genes | Count rRNA in GFF | 2 | 3 |
| Coverage | samtools depth | >30x | >30x |

---

## ERROR RECOVERY PROTOCOL

When any step fails, follow this protocol:

### Assembly Errors

| Error | Detection | Fix |
|-------|-----------|-----|
| SPAdes OOM | `bad_alloc` in stderr | Reduce threads, `--careful`, smaller K-mers, or switch to Flye/GetOrganelle |
| SPAdes low coverage | Warning in stdout | `--disable-corr`, smaller K-mers, or switch to GetOrganelle |
| Flye repeat failure | "repeat resolution failed" | Increase `--min-overlap`, check coverage |
| No contigs produced | Empty output FASTA | Try alternative assembler, check input data quality |

### Polishing Errors

| Error | Detection | Fix |
|-------|-----------|-----|
| Racon 0 overlaps | "zero overlaps" in output | Check minimap2 preset, verify read-assembly pairing |
| Pilon OOM | Java heap space error | Increase `-Xmx`, split BAM by region |
| Medaka model error | "unknown model" | Run `medaka --list_models`, use available model |

### Annotation Errors

| Error | Detection | Fix |
|-------|-----------|-----|
| PMGA unavailable | Import/file not found | Use MITOFY/BLAST+ instead |
| Low gene count | <50% expected genes | Try other tools, merge results |
| No genes found | 0 genes in output | Try ORF finder, check if assembly is mitochondrial |
| ORF finder: no ORFs | 0 ORFs detected | Assembly may not be mitochondrial — report failure |

### Universal Recovery

1. **First**: Check RAG knowledge base for matching FAQ
   ```bash
   cd /workspace && python -m mito_forge.cli.main knowledge query "<error description>"
   ```
2. **Second**: Try the suggested fix from FAQ
3. **Third**: Try alternative tool (switch assembler/annotator)
4. **Last resort**: Report failure to user with diagnostic information

---

## QUICK REFERENCE: Pipeline Commands

### Full Pipeline (recommended)
```bash
cd /workspace && python -m mito_forge.cli.main pipeline \
    --input ${INPUT_FILES} \
    --kingdom ${KINGDOM} \
    --platform ${PLATFORM} \
    --output ${OUTPUT_DIR} \
    --threads ${THREADS}
```

### Individual Stages
```bash
# QC
cd /workspace && python -m mito_forge.cli.main qc --input ${INPUT} --output ${QC_DIR}

# Assembly
cd /workspace && python -m mito_forge.cli.main assembly --input ${QC_DIR} --output ${ASM_DIR} --kingdom ${KINGDOM}

# Annotation
cd /workspace && python -m mito_forge.cli.main annotate --input ${ASSEMBLY} --output ${ANN_DIR} --kingdom ${KINGDOM}
```

### Resume After Crash
```bash
cd /workspace && python -m mito_forge.cli.main resume ${TASK_ID}
```

### Knowledge Base
```bash
cd /workspace && python -m mito_forge.cli.main knowledge index
cd /workspace && python -m mito_forge.cli.main knowledge query "<question>"
cd /workspace && python -m mito_forge.cli.main knowledge stats
```
