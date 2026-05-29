---
name: mito-forge
description: "Mitochondrial genome assembly, polishing, and annotation from raw sequencing data. Use this skill when the user wants to assemble, annotate, polish, or analyze mitochondrial genomes from Illumina short-read or Nanopore long-read data. Supports both animal and plant mitochondria with AI-driven error recovery and RAG-enhanced decisions."
---

# Mitochondrial Genome Assembly with Mito-Forge

## Critical Rules

- **NEVER fabricate gene positions** — all annotation must come from real tool output or ORF detection
- **NEVER modify input data** — all intermediate files go to the output directory
- **ALWAYS validate results** — check assembly stats and annotation completeness before reporting success
- **ALWAYS prefer offline tools** — use local tools over web services for reproducibility

## Step 0: Determine Parameters

Ask the user (or infer from context):

| Parameter | Options | Default |
|-----------|---------|---------|
| `INPUT` | FASTQ file path(s) | **MUST ask** |
| `KINGDOM` | `animal` / `plant` | **MUST ask** |
| `PLATFORM` | `illumina` / `nanopore` | Auto-detect from input files |
| `OUTPUT_DIR` | Path | `./mito_forge_output/` |
| `THREADS` | Integer | `min(8, nproc)` |

Auto-detect platform: 2 paired FASTQ files → illumina; 1 file with long reads → nanopore.

## Step 1: Environment Check

```bash
cd /workspace && python -m mito_forge.cli.main doctor
```

If knowledge base is empty (0 chunks):
```bash
cd /workspace && python -m mito_forge.cli.main knowledge index
```

If critical tools missing, install them:
```bash
conda install -c bioconda spades flye pilon racon medaka blast bwa samtools minimap2 fastqc -y
```

## Step 2: Quality Control

```bash
mkdir -p ${OUTPUT_DIR}/qc
fastqc ${INPUT} -o ${OUTPUT_DIR}/qc/ -t ${THREADS}
```

For Illumina paired-end, trim adapters:
```bash
trimmomatic PE -threads ${THREADS} \
    ${INPUT_R1} ${INPUT_R2} \
    ${OUTPUT_DIR}/qc/trim_R1_paired.fq ${OUTPUT_DIR}/qc/trim_R1_unpaired.fq \
    ${OUTPUT_DIR}/qc/trim_R2_paired.fq ${OUTPUT_DIR}/qc/trim_R2_unpaired.fq \
    ILLUMINACLIP:TruSeq3-PE.fa:2:30:10 LEADING:3 TRAILING:3 SLIDINGWINDOW:4:20 MINLEN:50
```

## Step 3: Assembly

### Illumina (SPAdes)

```bash
mkdir -p ${OUTPUT_DIR}/assembly
spades.py -1 ${TRIMMED_R1} -2 ${TRIMMED_R2} \
    -o ${OUTPUT_DIR}/assembly/spades \
    -t ${THREADS} -m 32 --careful \
    -k 21,33,55,77
```

**If OOM** (`bad_alloc`): reduce `-t` by half, add `--memory 16`, reduce `-k 21,33,55`
**If low coverage**: add `--disable-corr`, reduce K-mers
**If SPAdes fails entirely**: try GetOrganelle (see below)

### Nanopore (Flye)

```bash
mkdir -p ${OUTPUT_DIR}/assembly
flye --nano-raw ${INPUT} \
    -o ${OUTPUT_DIR}/assembly/flye \
    --genome-size $( [ "$KINGDOM" = "animal" ] && echo "16k" || echo "400k" ) \
    -t ${THREADS} --no-chimera-detection
```

**If repeat resolution fails**: increase `--min-overlap 5000`
**If assembly too short**: check if reads are mitochondrial, adjust `--genome-size`

### Alternative: GetOrganelle (targeted assembly)

```bash
get_organelle.py -1 ${TRIMMED_R1} -2 ${TRIMMED_R2} \
    -t ${THREADS} \
    -F $( [ "$KINGDOM" = "animal" ] && echo "animal_mt" || echo "plant_mt" ) \
    -o ${OUTPUT_DIR}/assembly/getorganelle
```

### Validate Assembly

```python
from mito_forge.utils.assembly_stats import get_assembly_stats
import glob
fasta = glob.glob("${OUTPUT_DIR}/assembly/*/contigs.fasta") or glob.glob("${OUTPUT_DIR}/assembly/*/assembly.fasta")
if fasta:
    stats = get_assembly_stats(fasta[0])
    print(f"N50: {stats['n50']}, Length: {stats['total_length']}, Contigs: {stats['num_contigs']}")
    # Expected: animal 14-20kb, plant 200-800kb
```

## Step 4: Polishing

### Nanopore: Racon × 3 + Medaka

```bash
mkdir -p ${OUTPUT_DIR}/polishing
ASSEMBLY=$(ls ${OUTPUT_DIR}/assembly/flye/assembly.fasta 2>/dev/null || ls ${OUTPUT_DIR}/assembly/spades/contigs.fasta)
READS=${INPUT}

# Racon round 1
minimap2 -x map-ont -t ${THREADS} ${ASSEMBLY} ${READS} > ${OUTPUT_DIR}/polishing/align1.paf
racon -t ${THREADS} ${READS} ${OUTPUT_DIR}/polishing/align1.paf ${ASSEMBLY} > ${OUTPUT_DIR}/polishing/racon1.fasta

# Racon round 2
minimap2 -x map-ont -t ${THREADS} ${OUTPUT_DIR}/polishing/racon1.fasta ${READS} > ${OUTPUT_DIR}/polishing/align2.paf
racon -t ${THREADS} ${READS} ${OUTPUT_DIR}/polishing/align2.paf ${OUTPUT_DIR}/polishing/racon1.fasta > ${OUTPUT_DIR}/polishing/racon2.fasta

# Racon round 3
minimap2 -x map-ont -t ${THREADS} ${OUTPUT_DIR}/polishing/racon2.fasta ${READS} > ${OUTPUT_DIR}/polishing/align3.paf
racon -t ${THREADS} ${READS} ${OUTPUT_DIR}/polishing/align3.paf ${OUTPUT_DIR}/polishing/racon2.fasta > ${OUTPUT_DIR}/polishing/racon3.fasta

# Medaka
medaka_consensus -i ${READS} -d ${OUTPUT_DIR}/polishing/racon3.fasta \
    -o ${OUTPUT_DIR}/polishing/medaka -t ${THREADS} -m r941_min_high_g303

POLISHED=${OUTPUT_DIR}/polishing/medaka/consensus.fasta
```

**If Racon 0 overlaps**: check minimap2 preset (`-x map-ont` vs `-x map-pb`)
**If Medaka model not found**: run `medaka --list_models`, pick available model

### Illumina: Pilon

```bash
ASSEMBLY=$(ls ${OUTPUT_DIR}/assembly/spades/contigs.fasta)
bwa index ${ASSEMBLY}
bwa mem -t ${THREADS} ${ASSEMBLY} ${TRIMMED_R1} ${TRIMMED_R2} | \
    samtools sort -@ ${THREADS} -o ${OUTPUT_DIR}/polishing/aligned.bam
samtools index ${OUTPUT_DIR}/polishing/aligned.bam

java -Xmx32G -jar $(which pilon.jar) \
    --genome ${ASSEMBLY} --frags ${OUTPUT_DIR}/polishing/aligned.bam \
    --output ${OUTPUT_DIR}/polishing/pilon --threads ${THREADS} --fix all

POLISHED=${OUTPUT_DIR}/polishing/pilon.fasta
```

**If Java OOM**: increase `-Xmx` to 64G

## Step 5: Annotation

### Animal (MITOS2 → Prokka → ORF fallback)

```bash
mkdir -p ${OUTPUT_DIR}/annotation

# Try MITOS2
mitos2.py -i ${POLISHED} -o ${OUTPUT_DIR}/annotation/mitos2 --genetic_code 2
```

If MITOS2 fails, try Prokka:
```bash
prokka --kingdom Mitochondria --genetic_code 2 \
    --outdir ${OUTPUT_DIR}/annotation/prokka --prefix mito \
    --cpus ${THREADS} ${POLISHED}
```

If both fail, use ORF finder:
```python
from mito_forge.tools.orf_annotator import run_orf_annotation
from pathlib import Path
result = run_orf_annotation("${POLISHED}", Path("${OUTPUT_DIR}/annotation/orf"), "animal", genetic_code=2)
if result:
    print(f"ORF annotation: {result['total_genes']} genes found")
    for g in result.get("gene_details", []):
        print(f"  {g['gene_name']}: {g['start']}-{g['end']} (confidence={g['confidence']})")
else:
    print("No ORFs detected — assembly may not be mitochondrial")
```

### Plant (PMGA + MITOFY + BLAST+ merge → ORF fallback)

Run all three tools, then merge:

```python
from mito_forge.tools.pmga import run_pmga
from mito_forge.tools.mitofy import run_mitofy
from mito_forge.tools.blast_annotator import run_blast_annotation
from mito_forge.tools.orf_annotator import run_orf_annotation
from mito_forge.core.agents.annotation_agent import AnnotationAgent
from pathlib import Path

ann_dir = Path("${OUTPUT_DIR}/annotation")
results = []

# Try PMGA
r = run_pmga("${POLISHED}", ann_dir / "pmga", "plant")
if r: results.append(r); print(f"PMGA: {r.get('total_genes', 0)} genes")

# Try MITOFY
r = run_mitofy("${POLISHED}", ann_dir / "mitofy", "plant")
if r: results.append(r); print(f"MITOFY: {r.get('total_genes', 0)} genes")

# Try BLAST+
r = run_blast_annotation("${POLISHED}", ann_dir / "blast", "plant")
if r: results.append(r); print(f"BLAST+: {r.get('total_genes', 0)} genes")

if results:
    # Merge: base = highest gene count, supplement with others
    results.sort(key=lambda x: x.get("total_genes", 0), reverse=True)
    base = dict(results[0])
    base_genes = {g.get("gene_name", g.get("name", "")) for g in base.get("gene_details", [])}
    supplemented = 0
    for extra in results[1:]:
        for g in extra.get("gene_details", []):
            name = g.get("gene_name", g.get("name", ""))
            if name and name not in base_genes:
                base_genes.add(name)
                base.setdefault("gene_details", []).append(g)
                supplemented += 1
    base["total_genes"] = len(base.get("gene_details", []))
    print(f"Merged: {base['total_genes']} genes ({supplemented} supplemented from other tools)")
else:
    # ORF fallback
    result = run_orf_annotation("${POLISHED}", ann_dir / "orf", "plant", genetic_code=2)
    if result:
        print(f"ORF annotation: {result['total_genes']} genes found")
    else:
        print("No ORFs detected — assembly may not be mitochondrial")
```

## Step 6: Generate Report

```python
import json
from pathlib import Path
from mito_forge.utils.assembly_stats import get_assembly_stats

report = {
    "kingdom": "${KINGDOM}",
    "platform": "${PLATFORM}",
    "assembly_stats": get_assembly_stats("${POLISHED}"),
    "annotation_stats": {
        "total_genes": result.get("total_genes", 0) if 'result' in dir() else 0,
        "protein_genes": result.get("protein_genes", 0) if 'result' in dir() else 0,
        "annotator": result.get("annotator", "unknown") if 'result' in dir() else "unknown",
    },
    "output_files": {
        "assembly": "${POLISHED}",
        "annotation": str(ann_dir) if 'ann_dir' in dir() else "",
    }
}

report_path = Path("${OUTPUT_DIR}/report.json")
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
print(f"Report saved to {report_path}")
```

## Error Recovery

When any step fails:

1. **Check RAG knowledge base** for matching FAQ:
```bash
cd /workspace && python -m mito_forge.cli.main knowledge query "<error message>"
```

2. **Common fixes**:

| Error | Fix |
|-------|-----|
| SPAdes `bad_alloc` | Reduce threads, `--careful`, smaller K-mers, or switch to Flye/GetOrganelle |
| Flye repeat resolution failed | Increase `--min-overlap`, check coverage >30x |
| Pilon Java heap space | Increase `-Xmx` to 32G+ |
| Racon 0 overlaps | Check minimap2 preset (`-x map-ont` vs `-x map-pb`) |
| Medaka unknown model | Run `medaka --list_models`, use available model |
| PMGA unavailable | Use MITOFY/BLAST+ instead |
| Low gene count | Merge multiple tools, or try ORF finder |
| No ORFs detected | Assembly may not be mitochondrial — report failure honestly |

3. **Try alternative tool** for the failed step
4. **If all alternatives fail**: report failure to user with diagnostic information — **never fabricate data**

## Quick Reference

| Task | Command |
|------|---------|
| Full pipeline | `cd /workspace && python -m mito_forge.cli.main pipeline --input ${INPUT} --kingdom ${KINGDOM} --platform ${PLATFORM} --output ${OUTPUT_DIR}` |
| QC only | `cd /workspace && python -m mito_forge.cli.main qc --input ${INPUT} --output ${QC_DIR}` |
| Assembly only | `cd /workspace && python -m mito_forge.cli.main assembly --input ${QC_DIR} --output ${ASM_DIR} --kingdom ${KINGDOM}` |
| Annotation only | `cd /workspace && python -m mito_forge.cli.main annotate --input ${ASSEMBLY} --output ${ANN_DIR} --kingdom ${KINGDOM}` |
| Resume after crash | `cd /workspace && python -m mito_forge.cli.main resume ${TASK_ID}` |
| Query knowledge base | `cd /workspace && python -m mito_forge.cli.main knowledge query "<question>"` |
| Index knowledge base | `cd /workspace && python -m mito_forge.cli.main knowledge index` |
| Check environment | `cd /workspace && python -m mito_forge.cli.main doctor` |
