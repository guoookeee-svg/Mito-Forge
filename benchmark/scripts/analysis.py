"""
结果分析和可视化模块
====================
读取所有 benchmark 结果，生成论文级别的图表和统计
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger("benchmark.analysis")

try:
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    HAS_VIS = True
except ImportError:
    HAS_VIS = False
    logger.warning("pandas/matplotlib not available, visualization disabled")


class BenchmarkAnalyzer:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results = self._load_all_results()

    def _load_all_results(self) -> List[Dict]:
        results = []
        for result_file in self.results_dir.rglob("*.json"):
            try:
                with open(result_file) as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "dataset_name" in data:
                        results.append(data)
                    elif isinstance(data, list):
                        results.extend(data)
            except Exception:
                pass
        return results

    def generate_all_figures(self, output_dir: Path):
        if not HAS_VIS:
            logger.error("pandas/matplotlib required for figure generation")
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        self._fig_assembly_comparison(output_dir)
        self._fig_annotation_comparison(output_dir)
        self._fig_pipeline_time(output_dir)
        self._fig_ablation_study(output_dir)
        self._fig_recovery_rate(output_dir)
        self._fig_plant_fallback(output_dir)
        self._fig_llm_diagnosis(output_dir)

        logger.info(f"All figures saved to {output_dir}")

    def _fig_assembly_comparison(self, output_dir: Path):
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        tools = defaultdict(lambda: {"n50": [], "coverage": [], "time": []})

        for r in self.results:
            tool = r.get("tool_name", "")
            m = r.get("metrics", {})
            if "n50" in m:
                tools[tool]["n50"].append(m["n50"])
            if "coverage_vs_ref" in m:
                tools[tool]["coverage"].append(m["coverage_vs_ref"])
            if "total_time" in m:
                tools[tool]["time"].append(m["total_time"])

        tool_names = sorted(tools.keys())
        if not tool_names:
            return

        colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]

        ax = axes[0]
        data = [tools[t]["n50"] for t in tool_names]
        bp = ax.boxplot(data, labels=tool_names, patch_artist=True)
        for patch, color in zip(bp["boxes"], colors[:len(tool_names)]):
            patch.set_facecolor(color)
        ax.set_title("Assembly N50 Comparison")
        ax.set_ylabel("N50 (bp)")
        ax.tick_params(axis="x", rotation=45)

        ax = axes[1]
        data = [tools[t]["coverage"] for t in tool_names]
        bp = ax.boxplot(data, labels=tool_names, patch_artist=True)
        for patch, color in zip(bp["boxes"], colors[:len(tool_names)]):
            patch.set_facecolor(color)
        ax.set_title("Coverage vs Reference")
        ax.set_ylabel("Coverage (%)")
        ax.tick_params(axis="x", rotation=45)

        ax = axes[2]
        data = [tools[t]["time"] for t in tool_names]
        bp = ax.boxplot(data, labels=tool_names, patch_artist=True)
        for patch, color in zip(bp["boxes"], colors[:len(tool_names)]):
            patch.set_facecolor(color)
        ax.set_title("Execution Time")
        ax.set_ylabel("Time (seconds)")
        ax.tick_params(axis="x", rotation=45)

        plt.tight_layout()
        plt.savefig(output_dir / "fig1_assembly_comparison.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(output_dir / "fig1_assembly_comparison.png", dpi=300, bbox_inches="tight")
        plt.close()

    def _fig_annotation_comparison(self, output_dir: Path):
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        tools = defaultdict(lambda: {"precision": [], "recall": [], "f1": []})

        for r in self.results:
            tool = r.get("tool_name", "")
            m = r.get("metrics", {})
            if "gene_precision" in m:
                tools[tool]["precision"].append(m["gene_precision"])
            if "gene_recall" in m:
                tools[tool]["recall"].append(m["gene_recall"])
            if "gene_f1" in m:
                tools[tool]["f1"].append(m["gene_f1"])

        tool_names = sorted(tools.keys())
        if not tool_names:
            return

        colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12"]

        for i, (metric, title) in enumerate([
            ("precision", "Gene Annotation Precision"),
            ("recall", "Gene Annotation Recall"),
            ("f1", "Gene Annotation F1 Score"),
        ]):
            ax = axes[i]
            data = [tools[t][metric] for t in tool_names]
            bp = ax.boxplot(data, labels=tool_names, patch_artist=True)
            for patch, color in zip(bp["boxes"], colors[:len(tool_names)]):
                patch.set_facecolor(color)
            ax.set_title(title)
            ax.set_ylabel(f"{metric.capitalize()} (%)")
            ax.tick_params(axis="x", rotation=45)

        plt.tight_layout()
        plt.savefig(output_dir / "fig2_annotation_comparison.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(output_dir / "fig2_annotation_comparison.png", dpi=300, bbox_inches="tight")
        plt.close()

    def _fig_pipeline_time(self, output_dir: Path):
        fig, ax = plt.subplots(figsize=(10, 6))

        stage_times = defaultdict(list)

        for r in self.results:
            if r.get("tool_name") == "mito_forge":
                m = r.get("metrics", {})
                for stage in ["qc_time", "assembly_time", "annotation_time", "polish_time", "report_time"]:
                    if stage in m:
                        stage_times[stage.replace("_time", "")].append(m[stage])

        if not stage_times:
            return

        stages = list(stage_times.keys())
        means = [sum(stage_times[s]) / max(len(stage_times[s]), 1) for s in stages]
        stds = [(sum((x - m) ** 2 for x in stage_times[s]) / max(len(stage_times[s]), 1)) ** 0.5
                for s, m in zip(stages, means)]

        colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]
        bars = ax.bar(stages, means, yerr=stds, color=colors[:len(stages)], capsize=5)

        ax.set_title("Mito-Forge Pipeline Stage Time Breakdown")
        ax.set_ylabel("Time (seconds)")
        ax.set_xlabel("Pipeline Stage")

        for bar, mean in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 5,
                   f'{mean:.1f}s', ha='center', va='bottom', fontsize=9)

        plt.tight_layout()
        plt.savefig(output_dir / "fig3_pipeline_time.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(output_dir / "fig3_pipeline_time.png", dpi=300, bbox_inches="tight")
        plt.close()

    def _fig_ablation_study(self, output_dir: Path):
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        variants = defaultdict(lambda: {"f1": [], "time": [], "recovery_rate": []})

        for r in self.results:
            variant = r.get("variant", "full")
            m = r.get("metrics", {})
            if "gene_f1" in m:
                variants[variant]["f1"].append(m["gene_f1"])
            if "total_time" in m:
                variants[variant]["time"].append(m["total_time"])
            if "auto_recovery_rate" in m:
                variants[variant]["recovery_rate"].append(m["auto_recovery_rate"])

        variant_names = ["full", "no_rag", "no_mem0", "no_auto_recovery", "no_llm", "no_rag_no_mem0"]
        variant_labels = ["Full System", "-RAG", "-Mem0", "-AutoRecovery", "-LLM", "-RAG-Mem0"]
        present_variants = [v for v in variant_names if v in variants]

        if not present_variants:
            return

        labels = [variant_labels[variant_names.index(v)] for v in present_variants]

        ax = axes[0]
        f1_means = [sum(variants[v]["f1"]) / max(len(variants[v]["f1"]), 1) for v in present_variants]
        colors = ["#2ecc71"] + ["#e74c3c"] * (len(present_variants) - 1)
        bars = ax.bar(labels, f1_means, color=colors[:len(present_variants)])
        ax.set_title("Ablation: Annotation F1 Score")
        ax.set_ylabel("F1 Score (%)")
        ax.tick_params(axis="x", rotation=45)

        ax = axes[1]
        time_means = [sum(variants[v]["time"]) / max(len(variants[v]["time"]), 1) for v in present_variants]
        bars = ax.bar(labels, time_means, color=colors[:len(present_variants)])
        ax.set_title("Ablation: Total Pipeline Time")
        ax.set_ylabel("Time (seconds)")
        ax.tick_params(axis="x", rotation=45)

        plt.tight_layout()
        plt.savefig(output_dir / "fig4_ablation_study.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(output_dir / "fig4_ablation_study.png", dpi=300, bbox_inches="tight")
        plt.close()

    def _fig_recovery_rate(self, output_dir: Path):
        recovery_file = self.results_dir / "recovery_evaluation_results.json"
        if not recovery_file.exists():
            return

        with open(recovery_file) as f:
            recovery_data = json.load(f)

        if not recovery_data:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        scenarios = [r["scenario"] for r in recovery_data]
        recovered = [1 if r.get("recovered") else 0 for r in recovery_data]
        methods = [r.get("recovery_method", "none") for r in recovery_data]

        ax = axes[0]
        colors = ["#2ecc71" if r else "#e74c3c" for r in recovered]
        ax.barh(scenarios, recovered, color=colors)
        ax.set_title("Auto-Recovery Success by Scenario")
        ax.set_xlabel("Recovered (1=Yes, 0=No)")
        ax.set_xlim(0, 1.2)

        ax = axes[1]
        method_counts = defaultdict(int)
        for m in methods:
            method_counts[m or "none"] += 1
        ax.pie(method_counts.values(), labels=method_counts.keys(), autopct="%1.0f%%",
               colors=["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"])
        ax.set_title("Recovery Method Distribution")

        plt.tight_layout()
        plt.savefig(output_dir / "fig5_recovery_rate.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(output_dir / "fig5_recovery_rate.png", dpi=300, bbox_inches="tight")
        plt.close()

    def _fig_plant_fallback(self, output_dir: Path):
        variants = defaultdict(lambda: {"precision": [], "recall": [], "f1": [], "total_genes": []})

        for r in self.results:
            variant = r.get("variant", "")
            if variant in ("pmga_only", "mitofy_only", "blast_only", "basic_only", "auto_fallback"):
                m = r.get("metrics", {})
                for metric in ["gene_precision", "gene_recall", "gene_f1", "total_genes"]:
                    key = metric.replace("gene_", "") if metric != "total_genes" else "total_genes"
                    if metric in m:
                        variants[variant][key].append(m[metric])

        if not variants:
            return

        fig, ax = plt.subplots(figsize=(10, 6))

        labels_map = {
            "pmga_only": "PMGA",
            "mitofy_only": "MITOFY",
            "blast_only": "BLAST+",
            "basic_only": "Basic",
            "auto_fallback": "Auto Fallback",
        }
        names = [labels_map.get(v, v) for v in variants.keys()]

        x = range(len(names))
        width = 0.25

        precision_means = [sum(variants[v]["precision"]) / max(len(variants[v]["precision"]), 1) for v in variants]
        recall_means = [sum(variants[v]["recall"]) / max(len(variants[v]["recall"]), 1) for v in variants]
        f1_means = [sum(variants[v]["f1"]) / max(len(variants[v]["f1"]), 1) for v in variants]

        ax.bar([i - width for i in x], precision_means, width, label="Precision", color="#3498db")
        ax.bar(x, recall_means, width, label="Recall", color="#2ecc71")
        ax.bar([i + width for i in x], f1_means, width, label="F1", color="#e74c3c")

        ax.set_title("Plant Annotation: Fallback Chain Evaluation")
        ax.set_ylabel("Score (%)")
        ax.set_xticks(x)
        ax.set_xticklabels(names)
        ax.legend()

        plt.tight_layout()
        plt.savefig(output_dir / "fig6_plant_fallback.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(output_dir / "fig6_plant_fallback.png", dpi=300, bbox_inches="tight")
        plt.close()

    def _fig_llm_diagnosis(self, output_dir: Path):
        diagnosis_file = self.results_dir / "llm_diagnosis_results.json"
        if not diagnosis_file.exists():
            return

        with open(diagnosis_file) as f:
            diagnosis_data = json.load(f)

        if not diagnosis_data:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        cases = [d["case_id"] for d in diagnosis_data]
        scores = [d["accuracy_score"] for d in diagnosis_data]
        fix_success = [1 if d.get("fix_success") else 0 for d in diagnosis_data]

        ax = axes[0]
        colors = ["#2ecc71" if s >= 0.8 else "#f39c12" if s >= 0.5 else "#e74c3c" for s in scores]
        ax.barh(cases, scores, color=colors)
        ax.set_title("AI Diagnosis Accuracy by Scenario")
        ax.set_xlabel("Accuracy Score")
        ax.set_xlim(0, 1.1)

        ax = axes[1]
        ax.barh(cases, fix_success, color=["#2ecc71" if f else "#e74c3c" for f in fix_success])
        ax.set_title("Fix Strategy Correctness")
        ax.set_xlabel("Correct (1=Yes, 0=No)")
        ax.set_xlim(0, 1.2)

        plt.tight_layout()
        plt.savefig(output_dir / "fig7_llm_diagnosis.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(output_dir / "fig7_llm_diagnosis.png", dpi=300, bbox_inches="tight")
        plt.close()

    def generate_latex_tables(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)

        self._latex_table_assembly(output_dir)
        self._latex_table_annotation(output_dir)
        self._latex_table_ablation(output_dir)

    def _latex_table_assembly(self, output_dir: Path):
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Assembly quality comparison across different tools}",
            r"\label{tab:assembly_comparison}",
            r"\begin{tabular}{lcccc}",
            r"\toprule",
            r"Tool & N50 (bp) & Total Length (bp) & Contigs & Coverage (\%) \\",
            r"\midrule",
        ]

        tool_metrics = defaultdict(lambda: {"n50": [], "total_length": [], "num_contigs": [], "coverage": []})
        for r in self.results:
            tool = r.get("tool_name", "")
            m = r.get("metrics", {})
            if "n50" in m:
                tool_metrics[tool]["n50"].append(m["n50"])
            if "total_length" in m:
                tool_metrics[tool]["total_length"].append(m["total_length"])
            if "num_contigs" in m:
                tool_metrics[tool]["num_contigs"].append(m["num_contigs"])
            if "coverage_vs_ref" in m:
                tool_metrics[tool]["coverage"].append(m["coverage_vs_ref"])

        for tool in sorted(tool_metrics.keys()):
            d = tool_metrics[tool]
            n50 = f"{sum(d['n50'])/max(len(d['n50']),1):.0f}"
            tl = f"{sum(d['total_length'])/max(len(d['total_length']),1):.0f}"
            ct = f"{sum(d['num_contigs'])/max(len(d['num_contigs']),1):.1f}"
            cov = f"{sum(d['coverage'])/max(len(d['coverage']),1):.1f}"
            lines.append(f"{tool} & {n50} & {tl} & {ct} & {cov} \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ])

        (output_dir / "table_assembly.tex").write_text("\n".join(lines))

    def _latex_table_annotation(self, output_dir: Path):
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Annotation quality comparison}",
            r"\label{tab:annotation_comparison}",
            r"\begin{tabular}{lccccc}",
            r"\toprule",
            r"Tool & Protein Genes & tRNA & rRNA & Precision (\%) & F1 (\%) \\",
            r"\midrule",
        ]

        tool_metrics = defaultdict(lambda: {"protein": [], "trna": [], "rrna": [], "precision": [], "f1": []})
        for r in self.results:
            tool = r.get("tool_name", "")
            m = r.get("metrics", {})
            if "protein_genes" in m:
                tool_metrics[tool]["protein"].append(m["protein_genes"])
            if "trna_genes" in m:
                tool_metrics[tool]["trna"].append(m["trna_genes"])
            if "rrna_genes" in m:
                tool_metrics[tool]["rrna"].append(m["rrna_genes"])
            if "gene_precision" in m:
                tool_metrics[tool]["precision"].append(m["gene_precision"])
            if "gene_f1" in m:
                tool_metrics[tool]["f1"].append(m["gene_f1"])

        for tool in sorted(tool_metrics.keys()):
            d = tool_metrics[tool]
            prot = f"{sum(d['protein'])/max(len(d['protein']),1):.1f}"
            trna = f"{sum(d['trna'])/max(len(d['trna']),1):.1f}"
            rrna = f"{sum(d['rrna'])/max(len(d['rrna']),1):.1f}"
            prec = f"{sum(d['precision'])/max(len(d['precision']),1):.1f}" if d['precision'] else "N/A"
            f1 = f"{sum(d['f1'])/max(len(d['f1']),1):.1f}" if d['f1'] else "N/A"
            lines.append(f"{tool} & {prot} & {trna} & {rrna} & {prec} & {f1} \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ])

        (output_dir / "table_annotation.tex").write_text("\n".join(lines))

    def _latex_table_ablation(self, output_dir: Path):
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Ablation study results}",
            r"\label{tab:ablation}",
            r"\begin{tabular}{lccc}",
            r"\toprule",
            r"Configuration & F1 (\%) & Time (s) & Recovery Rate (\%) \\",
            r"\midrule",
        ]

        variant_metrics = defaultdict(lambda: {"f1": [], "time": [], "recovery": []})
        for r in self.results:
            variant = r.get("variant", "")
            m = r.get("metrics", {})
            if "gene_f1" in m:
                variant_metrics[variant]["f1"].append(m["gene_f1"])
            if "total_time" in m:
                variant_metrics[variant]["time"].append(m["total_time"])
            if "auto_recovery_rate" in m:
                variant_metrics[variant]["recovery"].append(m["auto_recovery_rate"])

        label_map = {
            "full": "Full System", "no_rag": "-RAG", "no_mem0": "-Mem0",
            "no_auto_recovery": "-AutoRecovery", "no_llm": "-LLM", "no_rag_no_mem0": "-RAG-Mem0",
        }

        for variant in ["full", "no_rag", "no_mem0", "no_auto_recovery", "no_llm", "no_rag_no_mem0"]:
            if variant not in variant_metrics:
                continue
            d = variant_metrics[variant]
            f1 = f"{sum(d['f1'])/max(len(d['f1']),1):.1f}" if d['f1'] else "N/A"
            time_s = f"{sum(d['time'])/max(len(d['time']),1):.1f}" if d['time'] else "N/A"
            rec = f"{sum(d['recovery'])/max(len(d['recovery']),1):.1f}" if d['recovery'] else "N/A"
            label = label_map.get(variant, variant)
            lines.append(f"{label} & {f1} & {time_s} & {rec} \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ])

        (output_dir / "table_ablation.tex").write_text("\n".join(lines))
