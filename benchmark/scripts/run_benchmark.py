"""
Mito-Forge Benchmark Framework
===============================
自动化实验框架：数据集管理、工具运行、结果收集、评估分析

Usage:
    # 下载所有数据集
    python -m benchmark.scripts.run_benchmark download --config configs/experiment_config.yaml

    # 运行指定实验
    python -m benchmark.scripts.run_benchmark run --experiment exp1_end_to_end

    # 运行所有实验
    python -m benchmark.scripts.run_benchmark run --all

    # 生成报告
    python -m benchmark.scripts.run_benchmark report --output results/report.html
"""

import os
import sys
import json
import time
import yaml
import argparse
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark")

BENCHMARK_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BENCHMARK_DIR.parent


@dataclass
class DatasetSpec:
    name: str
    sra: str
    kingdom: str
    platform: str
    ref_genome: str
    ref_length: int
    description: str = ""


@dataclass
class ExperimentResult:
    experiment_id: str
    dataset_name: str
    tool_name: str
    variant: str
    repetition: int
    metrics: Dict[str, Any] = field(default_factory=dict)
    wall_time: float = 0.0
    status: str = "pending"
    error_message: str = ""
    timestamp: str = ""
    output_dir: str = ""


class DatasetManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def download(self, spec: DatasetSpec) -> Path:
        dataset_dir = self.data_dir / spec.name
        dataset_dir.mkdir(parents=True, exist_ok=True)

        reads_file = dataset_dir / "reads.fastq.gz"
        ref_file = dataset_dir / "reference.fasta"

        if reads_file.exists() and ref_file.exists():
            logger.info(f"Dataset {spec.name} already exists, skipping download")
            return dataset_dir

        if not reads_file.exists():
            logger.info(f"Downloading SRA {spec.sra} for {spec.name}...")
            cmd = ["fasterq-dump", "--split-files", "--gzip", "--outdir", str(dataset_dir), spec.sra]
            try:
                subprocess.run(cmd, check=True, timeout=3600)
                downloaded = list(dataset_dir.glob("*.fastq.gz"))
                if downloaded:
                    if len(downloaded) == 1:
                        shutil.move(str(downloaded[0]), str(reads_file))
                    elif len(downloaded) >= 2:
                        r1 = dataset_dir / "reads_R1.fastq.gz"
                        r2 = dataset_dir / "reads_R2.fastq.gz"
                        shutil.move(str(downloaded[0]), str(r1))
                        shutil.move(str(downloaded[1]), str(r2))
            except FileNotFoundError:
                logger.warning("fasterq-dump not found, trying prefetch + fastq-dump")
                self._download_with_prefetch(spec, dataset_dir, reads_file)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to download {spec.sra}: {e}")
                self._create_synthetic_dataset(spec, dataset_dir, reads_file)

        if not ref_file.exists():
            self._download_reference(spec, ref_file)

        return dataset_dir

    def _download_with_prefetch(self, spec: DatasetSpec, dataset_dir: Path, reads_file: Path):
        try:
            subprocess.run(["prefetch", spec.sra, "-o", str(dataset_dir / "sra")], check=True, timeout=1800)
            subprocess.run(
                ["fastq-dump", "--gzip", "--split-files", "--outdir", str(dataset_dir),
                 str(dataset_dir / "sra" / f"{spec.sra}.sra")],
                check=True, timeout=1800
            )
        except Exception as e:
            logger.warning(f"prefetch also failed: {e}, creating synthetic dataset")
            self._create_synthetic_dataset(spec, dataset_dir, reads_file)

    def _download_reference(self, spec: DatasetSpec, ref_file: Path):
        logger.info(f"Downloading reference {spec.ref_genome} for {spec.name}...")
        cmd = [
            "efetch", "-db", "nucleotide", "-id", spec.ref_genome,
            "-format", "fasta"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
            ref_file.write_text(result.stdout)
        except Exception as e:
            logger.warning(f"Failed to download reference: {e}")
            self._create_synthetic_reference(spec, ref_file)

    def _create_synthetic_dataset(self, spec: DatasetSpec, dataset_dir: Path, reads_file: Path):
        logger.info(f"Creating synthetic dataset for {spec.name}...")
        try:
            from Bio import SeqIO, Seq
            from Bio.SeqRecord import SeqRecord
            import random

            seq = Seq.Seq("ATGC" * (spec.ref_length // 4))
            record = SeqRecord(seq, id="synthetic_mito", description=f"Synthetic {spec.description}")

            fasta_file = dataset_dir / "assembly.fasta"
            SeqIO.write([record], str(fasta_file), "fasta")

            with open(reads_file, 'w') as f:
                f.write(f"@synthetic_read_{spec.name}\n")
                f.write(str(seq[:150]) + "\n")
                f.write("+\n")
                f.write("I" * 150 + "\n")

            logger.info(f"Synthetic dataset created: {reads_file}")
        except ImportError:
            logger.error("BioPython not available for synthetic data generation")
            raise

    def _create_synthetic_reference(self, spec: DatasetSpec, ref_file: Path):
        try:
            from Bio import SeqIO, Seq
            from Bio.SeqRecord import SeqRecord

            seq = Seq.Seq("ATGC" * (spec.ref_length // 4))
            record = SeqRecord(seq, id=spec.ref_genome, description=spec.description)
            SeqIO.write([record], str(ref_file), "fasta")
        except ImportError:
            ref_file.write_text(f">{spec.ref_genome} {spec.description}\nATGC\n")

    def get_dataset_path(self, name: str) -> Optional[Path]:
        p = self.data_dir / name
        return p if p.exists() else None


class AssemblyEvaluator:
    @staticmethod
    def evaluate_assembly(assembly_fasta: Path, ref_fasta: Path) -> Dict[str, Any]:
        metrics = {}

        try:
            from Bio import SeqIO
            sequences = list(SeqIO.parse(str(assembly_fasta), "fasta"))
            lengths = [len(s) for s in sequences]

            if not lengths:
                return {"error": "No sequences in assembly"}

            total_length = sum(lengths)
            lengths_sorted = sorted(lengths, reverse=True)
            cumsum = 0
            n50 = 0
            for l in lengths_sorted:
                cumsum += l
                if cumsum >= total_length / 2:
                    n50 = l
                    break

            metrics["n50"] = n50
            metrics["total_length"] = total_length
            metrics["num_contigs"] = len(lengths)
            metrics["max_contig_length"] = max(lengths)
            metrics["min_contig_length"] = min(lengths)
        except Exception as e:
            logger.warning(f"Failed to compute assembly stats: {e}")

        if ref_fasta and ref_fasta.exists():
            metrics.update(AssemblyEvaluator._compare_with_ref(assembly_fasta, ref_fasta))

        return metrics

    @staticmethod
    def _compare_with_ref(assembly_fasta: Path, ref_fasta: Path) -> Dict[str, Any]:
        metrics = {}
        minimap2 = shutil.which("minimap2")
        if not minimap2:
            logger.warning("minimap2 not found, skipping reference comparison")
            return metrics

        paf_file = assembly_fasta.parent / "alignment.paf"
        try:
            subprocess.run(
                [minimap2, "-cx", "asm5", str(ref_fasta), str(assembly_fasta),
                 "-o", str(paf_file)],
                check=True, timeout=600, capture_output=True
            )

            total_aligned = 0
            total_ref_len = 0
            total_identity = 0
            alignment_count = 0

            with open(paf_file) as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) >= 12:
                        aligned_bases = int(parts[10])
                        total_bases = int(parts[11])
                        if total_bases > 0:
                            total_aligned += aligned_bases
                            total_identity += aligned_bases / total_bases
                            alignment_count += 1

            try:
                from Bio import SeqIO
                for rec in SeqIO.parse(str(ref_fasta), "fasta"):
                    total_ref_len += len(rec.seq)
            except Exception:
                pass

            if total_ref_len > 0:
                metrics["coverage_vs_ref"] = round(min(100.0, total_aligned / total_ref_len * 100), 2)
            if alignment_count > 0:
                metrics["identity_vs_ref"] = round(total_identity / alignment_count * 100, 2)

        except Exception as e:
            logger.warning(f"Reference comparison failed: {e}")

        return metrics


class AnnotationEvaluator:
    MITOCHONDRIAL_GENE_SETS = {
        "animal": {
            "protein": ["nad1","nad2","nad3","nad4","nad4L","nad5","nad6",
                        "cox1","cox2","cox3","atp6","atp8","cytb"],
            "trna": 22,
            "rrna": 2,
        },
        "plant": {
            "protein": ["nad1","nad2","nad3","nad4","nad4L","nad5","nad6","nad7","nad9",
                        "cox1","cox2","cox3","atp1","atp4","atp6","atp8","atp9",
                        "ccmB","ccmC","ccmFC","ccmFN","matR","mttB"],
            "trna": 22,
            "rrna": 3,
        }
    }

    @staticmethod
    def evaluate_annotation(gff_file: Path, kingdom: str, ref_gff: Optional[Path] = None) -> Dict[str, Any]:
        metrics = {}

        predicted_genes = AnnotationEvaluator._parse_gff(gff_file)
        metrics["total_genes"] = len(predicted_genes)
        metrics["protein_genes"] = sum(1 for g in predicted_genes if g["type"] == "CDS")
        metrics["trna_genes"] = sum(1 for g in predicted_genes if g["type"] == "tRNA")
        metrics["rrna_genes"] = sum(1 for g in predicted_genes if g["type"] == "rRNA")

        gene_set = AnnotationEvaluator.MITOCHONDRIAL_GENE_SETS.get(kingdom,
                     AnnotationEvaluator.MITOCHONDRIAL_GENE_SETS["animal"])

        found_protein_names = set()
        for g in predicted_genes:
            if g["type"] == "CDS":
                name = g.get("name", "").lower()
                for expected in gene_set["protein"]:
                    if expected.lower() in name or name in expected.lower():
                        found_protein_names.add(expected)
                        break

        expected_protein = set(gene_set["protein"])
        if expected_protein:
            precision = len(found_protein_names & expected_protein) / max(len(found_protein_names), 1)
            recall = len(found_protein_names & expected_protein) / len(expected_protein)
            f1 = 2 * precision * recall / max(precision + recall, 1e-10)
            metrics["gene_precision"] = round(precision * 100, 2)
            metrics["gene_recall"] = round(recall * 100, 2)
            metrics["gene_f1"] = round(f1 * 100, 2)
            metrics["completeness"] = round(recall * 100, 2)

        if ref_gff and ref_gff.exists():
            metrics.update(AnnotationEvaluator._compare_with_ref_gff(predicted_genes, ref_gff))

        return metrics

    @staticmethod
    def _parse_gff(gff_file: Path) -> List[Dict]:
        genes = []
        if not gff_file.exists():
            return genes
        with open(gff_file) as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split('\t')
                if len(parts) < 5:
                    continue
                gene_info = {
                    "seqid": parts[0],
                    "source": parts[1],
                    "type": parts[2],
                    "start": int(parts[3]),
                    "end": int(parts[4]),
                }
                if len(parts) >= 9:
                    attrs = parts[8]
                    for attr in attrs.split(';'):
                        if '=' in attr:
                            k, v = attr.split('=', 1)
                            if k.lower() == 'name':
                                gene_info["name"] = v
                genes.append(gene_info)
        return genes

    @staticmethod
    def _compare_with_ref_gff(predicted: List[Dict], ref_gff: Path) -> Dict[str, Any]:
        ref_genes = AnnotationEvaluator._parse_gff(ref_gff)
        if not ref_genes:
            return {}

        boundary_matches = 0
        for pred in predicted:
            for ref in ref_genes:
                if pred.get("name", "").lower() == ref.get("name", "").lower():
                    if abs(pred["start"] - ref["start"]) <= 10 and abs(pred["end"] - ref["end"]) <= 10:
                        boundary_matches += 1
                    break

        total = max(len(predicted), 1)
        return {"boundary_accuracy": round(boundary_matches / total * 100, 2)}


class ToolRunner:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def run_mito_forge(self, dataset_dir: Path, dataset_spec: DatasetSpec,
                       output_dir: Path, config_overrides: Dict = None) -> ExperimentResult:
        result = ExperimentResult(
            experiment_id=f"mito_forge_{dataset_spec.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            dataset_name=dataset_spec.name,
            tool_name="mito_forge",
            variant="default",
            repetition=1,
            timestamp=datetime.now().isoformat(),
            output_dir=str(output_dir)
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        reads = self._find_reads(dataset_dir)
        cmd = [
            sys.executable, "-m", "mito_forge",
            "pipeline",
            "--reads", str(reads),
            "--output", str(output_dir),
            "--kingdom", dataset_spec.kingdom,
            "--threads", "8",
        ]

        env = os.environ.copy()
        env["MITO_LANG"] = "en"
        env["MITO_DRY_RUN"] = ""

        if config_overrides:
            if config_overrides.get("disable_llm"):
                env["MITO_DISABLE_LLM"] = "1"
            if config_overrides.get("disable_rag"):
                env["MITO_DISABLE_RAG"] = "1"
            if config_overrides.get("disable_mem0"):
                env["MITO_DISABLE_MEM0"] = "1"
            if config_overrides.get("annotation_tool"):
                cmd.extend(["--annotation-tool", config_overrides["annotation_tool"]])

        logger.info(f"Running Mito-Forge: {' '.join(cmd)}")
        start_time = time.time()

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=7200, env=env, cwd=str(PROJECT_ROOT)
            )
            result.wall_time = time.time() - start_time
            result.status = "success" if proc.returncode == 0 else "failed"
            if proc.returncode != 0:
                result.error_message = proc.stderr[-2000:] if proc.stderr else "Unknown error"
        except subprocess.TimeoutExpired:
            result.wall_time = time.time() - start_time
            result.status = "timeout"
            result.error_message = "Pipeline timed out after 2 hours"
        except Exception as e:
            result.wall_time = time.time() - start_time
            result.status = "error"
            result.error_message = str(e)

        result.metrics = self._collect_mito_forge_metrics(output_dir, dataset_dir, dataset_spec)
        result.metrics["total_time"] = result.wall_time

        self._save_result(result)
        return result

    def run_comparison_tool(self, tool_name: str, dataset_dir: Path,
                            dataset_spec: DatasetSpec, output_dir: Path) -> ExperimentResult:
        result = ExperimentResult(
            experiment_id=f"{tool_name}_{dataset_spec.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            dataset_name=dataset_spec.name,
            tool_name=tool_name,
            variant="default",
            repetition=1,
            timestamp=datetime.now().isoformat(),
            output_dir=str(output_dir)
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = self._build_comparison_command(tool_name, dataset_dir, dataset_spec, output_dir)
        if not cmd:
            result.status = "skipped"
            result.error_message = f"Tool {tool_name} not available"
            self._save_result(result)
            return result

        logger.info(f"Running {tool_name}: {' '.join(cmd)}")
        start_time = time.time()

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            result.wall_time = time.time() - start_time
            result.status = "success" if proc.returncode == 0 else "failed"
            if proc.returncode != 0:
                result.error_message = proc.stderr[-2000:] if proc.stderr else ""
        except subprocess.TimeoutExpired:
            result.wall_time = time.time() - start_time
            result.status = "timeout"
        except Exception as e:
            result.wall_time = time.time() - start_time
            result.status = "error"
            result.error_message = str(e)

        result.metrics = self._collect_comparison_metrics(tool_name, output_dir, dataset_dir, dataset_spec)
        self._save_result(result)
        return result

    def _find_reads(self, dataset_dir: Path) -> Path:
        for name in ["reads.fastq.gz", "reads_R1.fastq.gz"]:
            p = dataset_dir / name
            if p.exists():
                return p
        for p in dataset_dir.glob("*.fastq.gz"):
            return p
        for p in dataset_dir.glob("*.fastq"):
            return p
        raise FileNotFoundError(f"No reads found in {dataset_dir}")

    def _build_comparison_command(self, tool_name: str, dataset_dir: Path,
                                   spec: DatasetSpec, output_dir: Path) -> Optional[List[str]]:
        reads = self._find_reads(dataset_dir)

        if tool_name == "mitoz":
            exe = shutil.which("mitoz")
            if not exe:
                return None
            r1 = str(reads)
            r2 = ""
            r2_path = dataset_dir / "reads_R2.fastq.gz"
            if r2_path.exists():
                r2 = str(r2_path)
            cmd = [exe, "--fastq1", r1]
            if r2:
                cmd.extend(["--fastq2", r2])
            cmd.extend(["--output", str(output_dir), "--thread", "8",
                        "--kingdom", "animal" if spec.kingdom == "animal" else "plant"])
            return cmd

        elif tool_name == "getorganelle":
            exe = shutil.which("get_organelle_reads.py")
            if not exe:
                return None
            mode = "animal_mt" if spec.kingdom == "animal" else "plant_mt"
            return [exe, "-i", str(reads), "-o", str(output_dir), "-t", "8", "-F", mode]

        elif tool_name == "novoplasty":
            exe = shutil.which("NOVOPlasty.pl")
            if not exe:
                return None
            config_file = output_dir / "config.txt"
            self._write_novoplasty_config(config_file, reads, output_dir)
            return [exe, "-c", str(config_file)]

        elif tool_name == "mitos2":
            exe = shutil.which("runmitos.py")
            if not exe:
                return None
            assembly = dataset_dir / "assembly.fasta"
            if not assembly.exists():
                return None
            return [exe, "--input", str(assembly), "--code", "2", "--outdir", str(output_dir)]

        elif tool_name == "pmga_standalone":
            exe = shutil.which("pmga")
            if not exe:
                return None
            assembly = dataset_dir / "assembly.fasta"
            if not assembly.exists():
                return None
            return [exe, "-i", str(assembly), "-o", str(output_dir), "-t", "8"]

        return None

    def _write_novoplasty_config(self, config_file: Path, reads: Path, output_dir: Path):
        config_content = f"""Project Name          benchmark
Type                  mito
Genome Range          12000-20000
K-mer                 39
Max Extensions        3
Minimum Contig Length  500
Save Assembled Reads  no
Seed Input            
Reference Input       
Extend from References no
Reference Folder      
Read Length           150
Insert Size           300
Coverage              100
Forward Reads         {reads}
Reverse Reads         
Single Reads          
Merge Overlap         
Trim Reads            no
Quality Score         30
Output Directory      {output_dir}
"""
        config_file.write_text(config_content)

    def _collect_mito_forge_metrics(self, output_dir: Path, dataset_dir: Path,
                                     spec: DatasetSpec) -> Dict[str, Any]:
        metrics = {}

        work_dir = output_dir / "work"
        if not work_dir.exists():
            work_dir = output_dir

        assembly_fasta = self._find_file(work_dir, ["assembly.fasta", "final_assembly.fasta",
                                                      "03_assembly/assembly.fasta"])
        if assembly_fasta:
            ref_fasta = dataset_dir / "reference.fasta"
            metrics.update(AssemblyEvaluator.evaluate_assembly(assembly_fasta, ref_fasta))

        annotation_gff = self._find_file(work_dir, ["annotation.gff", "03_annotation/annotation.gff"])
        if annotation_gff:
            metrics.update(AnnotationEvaluator.evaluate_annotation(annotation_gff, spec.kingdom))

        checkpoint_file = self._find_file(work_dir, ["checkpoint.json"])
        if checkpoint_file:
            try:
                with open(checkpoint_file) as f:
                    cp = json.load(f)
                stage_outputs = cp.get("stage_outputs", {})
                for stage, data in stage_outputs.items():
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if k in ("metrics", "files", "metadata"):
                                continue
                            metrics[f"{stage}_{k}"] = v
            except Exception:
                pass

        return metrics

    def _collect_comparison_metrics(self, tool_name: str, output_dir: Path,
                                     dataset_dir: Path, spec: DatasetSpec) -> Dict[str, Any]:
        metrics = {}

        assembly_fasta = self._find_file(output_dir, ["assembly.fasta", "contigs.fasta",
                                                       "circularized_assembly.fasta"])
        if assembly_fasta:
            ref_fasta = dataset_dir / "reference.fasta"
            metrics.update(AssemblyEvaluator.evaluate_assembly(assembly_fasta, ref_fasta))

        annotation_gff = self._find_file(output_dir, ["annotation.gff", "result.gff"])
        if annotation_gff:
            metrics.update(AnnotationEvaluator.evaluate_annotation(annotation_gff, spec.kingdom))

        return metrics

    def _find_file(self, base_dir: Path, candidates: List[str]) -> Optional[Path]:
        for name in candidates:
            p = base_dir / name
            if p.exists():
                return p
        for name in candidates:
            matches = list(base_dir.rglob(name))
            if matches:
                return matches[0]
        return None

    def _save_result(self, result: ExperimentResult):
        result_file = self.results_dir / f"{result.experiment_id}.json"
        with open(result_file, 'w') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        logger.info(f"Result saved: {result_file}")


class BenchmarkRunner:
    def __init__(self, config_path: Path):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.dataset_manager = DatasetManager(BENCHMARK_DIR / "datasets")
        self.tool_runner = ToolRunner(BENCHMARK_DIR / "results")

    def download_datasets(self, groups: List[str] = None):
        all_datasets = self.config.get("datasets", {})
        if groups:
            selected = {k: v for k, v in all_datasets.items() if k in groups}
        else:
            selected = all_datasets

        for group_name, dataset_list in selected.items():
            logger.info(f"=== Downloading dataset group: {group_name} ===")
            for ds in dataset_list:
                spec = DatasetSpec(**ds)
                logger.info(f"  Downloading {spec.name} ({spec.sra})...")
                self.dataset_manager.download(spec)

    def run_experiment(self, experiment_name: str):
        exp = self.config["experiments"].get(experiment_name)
        if not exp:
            logger.error(f"Experiment {experiment_name} not found in config")
            return

        logger.info(f"=== Running experiment: {exp['title']} ===")

        dataset_groups = exp.get("datasets", [])
        tool_names = exp.get("tools", [])
        metrics_categories = exp.get("metrics", [])
        repetitions = exp.get("repetitions", 1)
        variants = exp.get("variants", [])

        all_specs = self._resolve_dataset_specs(dataset_groups)

        for rep in range(1, repetitions + 1):
            logger.info(f"  Repetition {rep}/{repetitions}")

            for spec in all_specs:
                dataset_dir = self.dataset_manager.get_dataset_path(spec.name)
                if not dataset_dir:
                    logger.warning(f"  Dataset {spec.name} not found, skipping")
                    continue

                for tool_name in tool_names:
                    if variants:
                        for variant in variants:
                            variant_name = variant["name"]
                            config_overrides = variant.get("config", {})
                            output_dir = (BENCHMARK_DIR / "results" / experiment_name /
                                         spec.name / tool_name / variant_name / f"rep{rep}")
                            logger.info(f"    {tool_name}/{variant_name} on {spec.name} (rep {rep})")

                            if tool_name == "mito_forge":
                                result = self.tool_runner.run_mito_forge(
                                    dataset_dir, spec, output_dir, config_overrides)
                                result.variant = variant_name
                                result.repetition = rep
                            else:
                                result = self.tool_runner.run_comparison_tool(
                                    tool_name, dataset_dir, spec, output_dir)
                                result.variant = variant_name
                                result.repetition = rep
                    else:
                        output_dir = (BENCHMARK_DIR / "results" / experiment_name /
                                     spec.name / tool_name / f"rep{rep}")
                        logger.info(f"    {tool_name} on {spec.name} (rep {rep})")

                        if tool_name == "mito_forge":
                            self.tool_runner.run_mito_forge(dataset_dir, spec, output_dir)
                        else:
                            self.tool_runner.run_comparison_tool(
                                tool_name, dataset_dir, spec, output_dir)

    def run_all_experiments(self):
        for exp_name in self.config.get("experiments", {}):
            self.run_experiment(exp_name)

    def _resolve_dataset_specs(self, groups: List[str]) -> List[DatasetSpec]:
        specs = []
        all_datasets = self.config.get("datasets", {})
        for group in groups:
            for ds in all_datasets.get(group, []):
                specs.append(DatasetSpec(**ds))
        return specs

    def generate_report(self, output_path: Path):
        results = []
        results_dir = BENCHMARK_DIR / "results"
        for result_file in results_dir.rglob("*.json"):
            try:
                with open(result_file) as f:
                    results.append(json.load(f))
            except Exception:
                pass

        if not results:
            logger.warning("No results found")
            return

        html = self._build_report_html(results)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"Report generated: {output_path}")

    def _build_report_html(self, results: List[Dict]) -> str:
        import pandas as pd

        df = pd.DataFrame(results)

        html_parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>Mito-Forge Benchmark Report</title>",
            "<style>",
            "body { font-family: -apple-system, sans-serif; margin: 40px; background: #f5f5f5; }",
            "h1 { color: #2c3e50; } h2 { color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 8px; }",
            "table { border-collapse: collapse; width: 100%; margin: 20px 0; background: white; }",
            "th, td { border: 1px solid #ddd; padding: 10px 14px; text-align: left; }",
            "th { background: #3498db; color: white; }",
            "tr:nth-child(even) { background: #f9f9f9; }",
            ".success { color: #27ae60; } .failed { color: #e74c3c; } .timeout { color: #f39c12; }",
            ".summary-card { background: white; border-radius: 8px; padding: 20px; margin: 10px; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            ".summary-card h3 { margin: 0; color: #7f8c8d; font-size: 14px; }",
            ".summary-card .value { font-size: 28px; font-weight: bold; color: #2c3e50; }",
            "</style></head><body>",
            "<h1>Mito-Forge Benchmark Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        ]

        total = len(results)
        success = sum(1 for r in results if r.get("status") == "success")
        failed = sum(1 for r in results if r.get("status") == "failed")
        avg_time = sum(r.get("wall_time", 0) for r in results) / max(total, 1)

        html_parts.extend([
            "<div class='summary-cards'>",
            f"<div class='summary-card'><h3>Total Runs</h3><div class='value'>{total}</div></div>",
            f"<div class='summary-card'><h3>Success Rate</h3><div class='value'>{success/total*100:.1f}%</div></div>",
            f"<div class='summary-card'><h3>Failed</h3><div class='value'>{failed}</div></div>",
            f"<div class='summary-card'><h3>Avg Time</h3><div class='value'>{avg_time:.1f}s</div></div>",
            "</div>",
        ])

        for tool_name in df["tool_name"].unique():
            tool_df = df[df["tool_name"] == tool_name]
            html_parts.append(f"<h2>{tool_name}</h2>")
            html_parts.append("<table><tr><th>Dataset</th><th>Variant</th><th>Status</th>"
                            "<th>Time(s)</th><th>N50</th><th>Contigs</th>"
                            "<th>Gene F1</th><th>Completeness</th></tr>")
            for _, row in tool_df.iterrows():
                m = row.get("metrics", {})
                html_parts.append(
                    f"<tr><td>{row.get('dataset_name','')}</td>"
                    f"<td>{row.get('variant','')}</td>"
                    f"<td class='{row.get('status','')}' >{row.get('status','')}</td>"
                    f"<td>{row.get('wall_time',0):.1f}</td>"
                    f"<td>{m.get('n50','N/A')}</td>"
                    f"<td>{m.get('num_contigs','N/A')}</td>"
                    f"<td>{m.get('gene_f1','N/A')}</td>"
                    f"<td>{m.get('completeness','N/A')}</td></tr>"
                )
            html_parts.append("</table>")

        html_parts.append("</body></html>")
        return "\n".join(html_parts)


def main():
    parser = argparse.ArgumentParser(description="Mito-Forge Benchmark Framework")
    parser.add_argument("--config", type=str, default=str(BENCHMARK_DIR / "configs" / "experiment_config.yaml"))
    subparsers = parser.add_subparsers(dest="command")

    dl_parser = subparsers.add_parser("download", help="Download datasets")
    dl_parser.add_argument("--groups", nargs="+", help="Dataset groups to download")

    run_parser = subparsers.add_parser("run", help="Run experiments")
    run_parser.add_argument("--experiment", type=str, help="Experiment name to run")
    run_parser.add_argument("--all", action="store_true", help="Run all experiments")

    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("--output", type=str, default=str(BENCHMARK_DIR / "results" / "report.html"))

    args = parser.parse_args()
    runner = BenchmarkRunner(Path(args.config))

    if args.command == "download":
        runner.download_datasets(args.groups)
    elif args.command == "run":
        if args.all:
            runner.run_all_experiments()
        elif args.experiment:
            runner.run_experiment(args.experiment)
        else:
            logger.error("Specify --experiment or --all")
    elif args.command == "report":
        runner.generate_report(Path(args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
