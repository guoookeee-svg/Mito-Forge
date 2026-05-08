"""
一键运行所有实验的入口脚本
==========================
Usage:
    # Step 1: 下载所有数据集
    python -m benchmark.scripts.run_all download

    # Step 2: 运行所有实验
    python -m benchmark.scripts.run_all experiments

    # Step 3: 生成所有图表和表格
    python -m benchmark.scripts.run_all figures

    # Step 4: 全部执行
    python -m benchmark.scripts.run_all all
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark.run_all")

BENCHMARK_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BENCHMARK_DIR.parent
CONFIG_PATH = BENCHMARK_DIR / "configs" / "experiment_config.yaml"


def download():
    logger.info("=" * 60)
    logger.info("STEP 1: Downloading datasets")
    logger.info("=" * 60)

    from .run_benchmark import BenchmarkRunner
    runner = BenchmarkRunner(CONFIG_PATH)
    runner.download_datasets()

    logger.info("Dataset download complete!")


def run_experiments():
    logger.info("=" * 60)
    logger.info("STEP 2: Running experiments")
    logger.info("=" * 60)

    from .run_benchmark import BenchmarkRunner
    runner = BenchmarkRunner(CONFIG_PATH)

    experiments = [
        "exp1_end_to_end",
        "exp2_assembly_comparison",
        "exp3_annotation_comparison",
        "exp5_ablation",
        "exp6_plant_fallback",
    ]

    for exp_name in experiments:
        logger.info(f"\n{'='*40}")
        logger.info(f"Running: {exp_name}")
        logger.info(f"{'='*40}")
        try:
            runner.run_experiment(exp_name)
        except Exception as e:
            logger.error(f"Experiment {exp_name} failed: {e}")
            continue

    logger.info("All experiments complete!")


def run_llm_eval():
    logger.info("=" * 60)
    logger.info("STEP 2b: Running LLM evaluation")
    logger.info("=" * 60)

    sys.path.insert(0, str(PROJECT_ROOT))
    from .llm_evaluation import run_llm_evaluation
    results_dir = BENCHMARK_DIR / "results" / "exp4_llm_decision"
    run_llm_evaluation(results_dir)


def run_recovery_eval():
    logger.info("=" * 60)
    logger.info("STEP 2c: Running recovery evaluation")
    logger.info("=" * 60)

    sys.path.insert(0, str(PROJECT_ROOT))
    from .recovery_evaluation import RecoveryEvaluator

    test_reads = BENCHMARK_DIR / "datasets" / "human_mt" / "reads.fastq.gz"
    if not test_reads.exists():
        logger.warning(f"Test reads not found at {test_reads}, skipping recovery eval")
        return

    evaluator = RecoveryEvaluator(
        results_dir=BENCHMARK_DIR / "results" / "exp7_auto_recovery",
        project_root=PROJECT_ROOT,
    )
    evaluator.evaluate_all(test_reads)


def generate_figures():
    logger.info("=" * 60)
    logger.info("STEP 3: Generating figures and tables")
    logger.info("=" * 60)

    from .analysis import BenchmarkAnalyzer

    analyzer = BenchmarkAnalyzer(BENCHMARK_DIR / "results")

    figures_dir = BENCHMARK_DIR / "results" / "figures"
    analyzer.generate_all_figures(figures_dir)

    tables_dir = BENCHMARK_DIR / "results" / "tables"
    analyzer.generate_latex_tables(tables_dir)

    report_path = BENCHMARK_DIR / "results" / "report.html"
    from .run_benchmark import BenchmarkRunner
    runner = BenchmarkRunner(CONFIG_PATH)
    runner.generate_report(report_path)

    logger.info(f"Figures: {figures_dir}")
    logger.info(f"Tables: {tables_dir}")
    logger.info(f"Report: {report_path}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "download":
        download()
    elif command == "experiments":
        run_experiments()
        run_llm_eval()
        run_recovery_eval()
    elif command == "figures":
        generate_figures()
    elif command == "all":
        download()
        run_experiments()
        run_llm_eval()
        run_recovery_eval()
        generate_figures()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
