"""
自动恢复能力评估模块
====================
故意注入错误场景，测试 Agent 的自动诊断和修复能力
"""

import os
import json
import time
import shutil
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("benchmark.recovery_eval")


@dataclass
class RecoveryScenario:
    name: str
    description: str
    inject_method: str
    inject_params: Dict[str, Any]
    expected_behavior: str
    max_recovery_time: int = 300


RECOVERY_SCENARIOS = [
    RecoveryScenario(
        name="tool_missing_spades",
        description="SPAdes 工具路径被隐藏，Agent 应切换到备选组装器",
        inject_method="hide_tool",
        inject_params={"tool": "spades"},
        expected_behavior="switch_tool",
        max_recovery_time=600,
    ),
    RecoveryScenario(
        name="tool_missing_fastqc",
        description="FastQC 不可用，Agent 应跳过 QC 或使用备选",
        inject_method="hide_tool",
        inject_params={"tool": "fastqc"},
        expected_behavior="skip_or_fallback",
        max_recovery_time=300,
    ),
    RecoveryScenario(
        name="low_memory",
        description="限制内存导致 OOM，Agent 应减少线程数",
        inject_method="limit_memory",
        inject_params={"memory": "2g"},
        expected_behavior="adjust_params",
        max_recovery_time=600,
    ),
    RecoveryScenario(
        name="timeout_short",
        description="设置极短超时，Agent 应增加超时时间",
        inject_method="set_timeout",
        inject_params={"timeout": 30},
        expected_behavior="increase_timeout",
        max_recovery_time=300,
    ),
    RecoveryScenario(
        name="plant_with_mitos",
        description="植物数据使用 MITOS，Agent 应切换到植物注释工具",
        inject_method="wrong_annotator",
        inject_params={"kingdom": "plant", "annotator": "mitos"},
        expected_behavior="switch_tool",
        max_recovery_time=600,
    ),
    RecoveryScenario(
        name="corrupt_assembly",
        description="组装输出文件损坏，Agent 应检测并重试",
        inject_method="corrupt_file",
        inject_params={"file_pattern": "assembly.fasta"},
        expected_behavior="retry",
        max_recovery_time=600,
    ),
]


class RecoveryEvaluator:
    def __init__(self, results_dir: Path, project_root: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = project_root

    def evaluate_all(self, test_reads: Path, scenarios: List[RecoveryScenario] = None) -> List[Dict]:
        if scenarios is None:
            scenarios = RECOVERY_SCENARIOS

        results = []
        for scenario in scenarios:
            logger.info(f"=== Evaluating recovery scenario: {scenario.name} ===")
            result = self._evaluate_single(scenario, test_reads)
            results.append(result)

        self._save_results(results)
        self._print_summary(results)
        return results

    def _evaluate_single(self, scenario: RecoveryScenario, test_reads: Path) -> Dict:
        result = {
            "scenario": scenario.name,
            "description": scenario.description,
            "expected_behavior": scenario.expected_behavior,
            "status": "pending",
            "recovered": False,
            "recovery_method": None,
            "recovery_time": 0.0,
            "total_time": 0.0,
            "error_details": "",
            "agent_log": "",
        }

        output_dir = self.results_dir / scenario.name
        output_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["MITO_LANG"] = "en"

        if scenario.inject_method == "hide_tool":
            tool = scenario.inject_params["tool"]
            original_path = shutil.which(tool)
            if original_path:
                backup_dir = self.results_dir / "_tool_backups"
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / f"{tool}.bak"
                env["PATH"] = self._remove_tool_from_path(tool, env.get("PATH", ""))
                result["_backup_original"] = original_path
                result["_backup_path"] = str(backup_path)

        elif scenario.inject_method == "limit_memory":
            env["MITO_MEMORY_LIMIT"] = scenario.inject_params["memory"]

        elif scenario.inject_method == "set_timeout":
            env["MITO_TOOL_TIMEOUT"] = str(scenario.inject_params["timeout"])

        elif scenario.inject_method == "wrong_annotator":
            pass

        kingdom = "animal"
        if scenario.inject_method == "wrong_annotator":
            kingdom = scenario.inject_params.get("kingdom", "animal")

        cmd = [
            "python", "-m", "mito_forge",
            "pipeline",
            "--reads", str(test_reads),
            "--output", str(output_dir),
            "--kingdom", kingdom,
            "--threads", "4",
        ]

        if scenario.inject_method == "wrong_annotator":
            cmd.extend(["--annotation-tool", scenario.inject_params.get("annotator", "mitos")])

        start_time = time.time()

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=scenario.max_recovery_time,
                env=env,
                cwd=str(self.project_root),
            )
            result["total_time"] = time.time() - start_time
            result["status"] = "completed" if proc.returncode == 0 else "failed"

            combined_output = (proc.stdout or "") + (proc.stderr or "")
            result["agent_log"] = combined_output[-5000:]

            result["recovered"] = self._check_recovery(scenario, combined_output, output_dir)
            if result["recovered"]:
                result["recovery_method"] = self._detect_recovery_method(combined_output)
                result["recovery_time"] = self._estimate_recovery_time(combined_output)

        except subprocess.TimeoutExpired:
            result["total_time"] = time.time() - start_time
            result["status"] = "timeout"
        except Exception as e:
            result["total_time"] = time.time() - start_time
            result["status"] = "error"
            result["error_details"] = str(e)

        return result

    def _remove_tool_from_path(self, tool: str, path_env: str) -> str:
        new_paths = []
        for p in path_env.split(os.pathsep):
            tool_path = Path(p) / tool
            if not tool_path.exists():
                new_paths.append(p)
        return os.pathsep.join(new_paths)

    def _check_recovery(self, scenario: RecoveryScenario, output: str, output_dir: Path) -> bool:
        output_lower = output.lower()

        if scenario.expected_behavior == "switch_tool":
            switch_keywords = ["switch", "fallback", "alternative", "trying", "using"]
            return any(kw in output_lower for kw in switch_keywords)

        elif scenario.expected_behavior == "adjust_params":
            adjust_keywords = ["adjust", "reduce", "decrease", "retry with", "parameter"]
            return any(kw in output_lower for kw in adjust_keywords)

        elif scenario.expected_behavior == "skip_or_fallback":
            skip_keywords = ["skip", "unavailable", "not found", "fallback"]
            return any(kw in output_lower for kw in skip_keywords)

        elif scenario.expected_behavior == "increase_timeout":
            timeout_keywords = ["timeout", "increase", "extend", "retry"]
            return any(kw in output_lower for kw in timeout_keywords)

        elif scenario.expected_behavior == "retry":
            retry_keywords = ["retry", "reattempt", "trying again", "second attempt"]
            return any(kw in output_lower for kw in retry_keywords)

        return False

    def _detect_recovery_method(self, output: str) -> Optional[str]:
        output_lower = output.lower()
        if any(kw in output_lower for kw in ["switch", "fallback", "alternative"]):
            return "switch_tool"
        elif any(kw in output_lower for kw in ["adjust", "reduce", "decrease"]):
            return "adjust_params"
        elif any(kw in output_lower for kw in ["retry", "reattempt"]):
            return "retry"
        elif any(kw in output_lower for kw in ["skip"]):
            return "skip_stage"
        return None

    def _estimate_recovery_time(self, output: str) -> float:
        return 0.0

    def _save_results(self, results: List[Dict]):
        output_file = self.results_dir / "recovery_evaluation_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"Recovery evaluation results saved: {output_file}")

    def _print_summary(self, results: List[Dict]):
        total = len(results)
        recovered = sum(1 for r in results if r.get("recovered"))
        logger.info(f"\n{'='*60}")
        logger.info(f"Auto-Recovery Evaluation Summary")
        logger.info(f"{'='*60}")
        logger.info(f"Total scenarios: {total}")
        logger.info(f"Recovered: {recovered}")
        logger.info(f"Recovery rate: {recovered/total*100:.1f}%")
        logger.info(f"{'='*60}")

        for r in results:
            status = "✅" if r.get("recovered") else "❌"
            logger.info(f"  {status} {r['scenario']}: {r.get('recovery_method', 'N/A')}")

        logger.info(f"{'='*60}")
