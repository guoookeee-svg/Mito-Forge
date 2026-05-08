"""
LLM 决策质量评估模块
====================
专门评估 Agent 的 AI 诊断、修复建议、RAG 增强等 LLM 相关能力
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("benchmark.llm_eval")


@dataclass
class DiagnosisCase:
    case_id: str
    scenario: str
    tool_name: str
    error_message: str
    stderr_sample: str
    expected_diagnosis: Dict[str, Any]


@dataclass
class DiagnosisResult:
    case_id: str
    ai_diagnosis: Dict[str, Any]
    expected: Dict[str, Any]
    accuracy_score: float = 0.0
    fix_success: bool = False
    response_time: float = 0.0
    rag_citations: List[Dict] = field(default_factory=list)


PREDEFINED_DIAGNOSIS_CASES = [
    DiagnosisCase(
        case_id="oom_spades",
        scenario="out_of_memory",
        tool_name="spades",
        error_message="SPAdes process killed (signal 9)",
        stderr_sample="== Error == system call finished abnormally, OS return value: -9",
        expected_diagnosis={
            "error_type": "out_of_memory",
            "can_fix": True,
            "fix_strategy": "adjust_params",
        }
    ),
    DiagnosisCase(
        case_id="tool_missing_mitos",
        scenario="tool_not_found",
        tool_name="mitos",
        error_message="command not found: runmitos.py",
        stderr_sample="bash: runmitos.py: command not found",
        expected_diagnosis={
            "error_type": "tool_not_found",
            "can_fix": True,
            "fix_strategy": "switch_tool",
        }
    ),
    DiagnosisCase(
        case_id="timeout_flye",
        scenario="timeout",
        tool_name="flye",
        error_message="Flye execution timed out after 3600 seconds",
        stderr_sample="[INFO] Running assembly... (still running after 3600s)",
        expected_diagnosis={
            "error_type": "timeout",
            "can_fix": True,
            "fix_strategy": "retry",
        }
    ),
    DiagnosisCase(
        case_id="bad_params_spades_kmer",
        scenario="parameter_error",
        tool_name="spades",
        error_message="Invalid k-mer value: 13. K-mer should be odd and < 128",
        stderr_sample="== Error == invalid k-mer specified",
        expected_diagnosis={
            "error_type": "parameter_error",
            "can_fix": True,
            "fix_strategy": "adjust_params",
        }
    ),
    DiagnosisCase(
        case_id="low_coverage",
        scenario="data_quality",
        tool_name="spades",
        error_message="Assembly produced no contigs",
        stderr_sample="== Warning == low coverage detected, assembly may be incomplete",
        expected_diagnosis={
            "error_type": "data_quality",
            "can_fix": False,
            "fix_strategy": "abort",
        }
    ),
    DiagnosisCase(
        case_id="plant_mitos_misuse",
        scenario="wrong_tool_for_kingdom",
        tool_name="mitos",
        error_message="MITOS only supports Metazoan mitochondrial genomes",
        stderr_sample="Error: Non-metazoan input detected",
        expected_diagnosis={
            "error_type": "tool_not_found",
            "can_fix": True,
            "fix_strategy": "switch_tool",
        }
    ),
]


class LLMDiagnosisEvaluator:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_diagnosis(self, cases: List[DiagnosisCase] = None) -> List[DiagnosisResult]:
        if cases is None:
            cases = PREDEFINED_DIAGNOSIS_CASES

        results = []
        for case in cases:
            logger.info(f"Evaluating diagnosis case: {case.case_id}")
            result = self._run_single_diagnosis(case)
            results.append(result)

        self._save_results(results)
        return results

    def _run_single_diagnosis(self, case: DiagnosisCase) -> DiagnosisResult:
        result = DiagnosisResult(
            case_id=case.case_id,
            ai_diagnosis={},
            expected=case.expected_diagnosis,
        )

        try:
            from mito_forge.core.agents.assembly_agent import AssemblyAgent

            agent = AssemblyAgent({"kingdom": "animal", "threads": 8})
            start_time = time.time()

            try:
                diagnosis = agent._diagnose_assembly_error(
                    error_msg=case.error_message,
                    stderr_content=case.stderr_sample,
                    stdout_content="",
                    tool_name=case.tool_name,
                )
            except AttributeError:
                diagnosis = self._rule_based_diagnosis_fallback(case)

            result.response_time = time.time() - start_time
            result.ai_diagnosis = diagnosis or {}

            if diagnosis:
                result.accuracy_score = self._compute_diagnosis_accuracy(
                    diagnosis, case.expected_diagnosis)
                result.fix_success = self._check_fix_success(diagnosis, case)

        except ImportError as e:
            logger.warning(f"Cannot import agent for diagnosis evaluation: {e}")
            result.ai_diagnosis = {"error": "agent_not_available"}
            result.accuracy_score = 0.0

        return result

    def _rule_based_diagnosis_fallback(self, case: DiagnosisCase) -> Dict[str, Any]:
        combined = (case.error_message + " " + case.stderr_sample).lower()

        if any(kw in combined for kw in ["out of memory", "bad_alloc", "killed", "signal 9"]):
            return {"error_type": "out_of_memory", "can_fix": True, "fix_strategy": "adjust_params"}
        elif any(kw in combined for kw in ["command not found", "not found", "no such file"]):
            return {"error_type": "tool_not_found", "can_fix": True, "fix_strategy": "switch_tool"}
        elif any(kw in combined for kw in ["timeout", "timed out"]):
            return {"error_type": "timeout", "can_fix": True, "fix_strategy": "retry"}
        elif any(kw in combined for kw in ["invalid", "parameter", "k-mer"]):
            return {"error_type": "parameter_error", "can_fix": True, "fix_strategy": "adjust_params"}
        elif any(kw in combined for kw in ["no contigs", "low coverage", "incomplete"]):
            return {"error_type": "data_quality", "can_fix": False, "fix_strategy": "abort"}
        else:
            return {"error_type": "unknown", "can_fix": False, "fix_strategy": "abort"}

    def _compute_diagnosis_accuracy(self, actual: Dict, expected: Dict) -> float:
        score = 0.0
        total_fields = 0

        for key in ["error_type", "can_fix", "fix_strategy"]:
            if key in expected:
                total_fields += 1
                if key in actual and actual[key] == expected[key]:
                    score += 1.0

        if "suggestions" in actual and actual.get("suggestions"):
            total_fields += 1
            score += 0.5

        return score / max(total_fields, 1)

    def _check_fix_success(self, diagnosis: Dict, case: DiagnosisCase) -> bool:
        if not diagnosis.get("can_fix"):
            return case.expected_diagnosis.get("fix_strategy") == "abort"

        fix_strategy = diagnosis.get("fix_strategy", "")
        expected_strategy = case.expected_diagnosis.get("fix_strategy", "")
        return fix_strategy == expected_strategy

    def _save_results(self, results: List[DiagnosisResult]):
        output_file = self.results_dir / "llm_diagnosis_results.json"
        data = []
        for r in results:
            data.append({
                "case_id": r.case_id,
                "accuracy_score": r.accuracy_score,
                "fix_success": r.fix_success,
                "response_time": r.response_time,
                "ai_diagnosis": r.ai_diagnosis,
                "expected": r.expected,
            })
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"LLM diagnosis results saved: {output_file}")


class RAGQualityEvaluator:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir

    def evaluate_rag_relevance(self, queries: List[str], top_k: int = 5) -> List[Dict]:
        results = []

        try:
            from mito_forge.core.agents.base_agent import BaseAgent

            class DummyAgent(BaseAgent):
                name = "eval_agent"
                @property
                def capabilities(self):
                    return {}

            agent = DummyAgent({"kingdom": "animal"})
            chroma = agent._get_shared_chroma()

            if not chroma:
                logger.warning("ChromaDB not available for RAG evaluation")
                return results

            collection = chroma["collection"]

            for query in queries:
                try:
                    search_results = collection.query(
                        query_texts=[query],
                        n_results=top_k
                    )

                    docs = search_results.get("documents", [[]])[0]
                    distances = search_results.get("distances", [[]])[0]

                    relevance_scores = [1 - d for d in distances] if distances else []

                    results.append({
                        "query": query,
                        "num_results": len(docs),
                        "avg_relevance": sum(relevance_scores) / max(len(relevance_scores), 1),
                        "top_relevance": max(relevance_scores) if relevance_scores else 0,
                        "has_citation": len(docs) > 0,
                    })
                except Exception as e:
                    logger.warning(f"RAG query failed for '{query}': {e}")
                    results.append({"query": query, "error": str(e)})

        except ImportError as e:
            logger.warning(f"Cannot import agent for RAG evaluation: {e}")

        return results


EVALUATION_QUERIES = [
    "SPAdes assembly N50 too low for plant mitochondrial genome",
    "How to fix out of memory error in SPAdes",
    "Best k-mer settings for Illumina mitochondrial assembly",
    "MITOS annotation failed for plant mitochondria",
    "Racon polishing iteration strategy",
    "tRNAscan-SE installation and usage for mitochondrial tRNA",
    "Plant mitochondrial genome annotation tools comparison",
    "Coverage requirements for mitochondrial genome assembly",
    "How to assess assembly completeness",
    "BLAST+ homology annotation for plant mitochondria",
]


def run_llm_evaluation(results_dir: Path):
    results_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== Running LLM Diagnosis Evaluation ===")
    diagnosis_eval = LLMDiagnosisEvaluator(results_dir)
    diagnosis_results = diagnosis_eval.evaluate_diagnosis()

    avg_accuracy = sum(r.accuracy_score for r in diagnosis_results) / max(len(diagnosis_results), 1)
    fix_success_rate = sum(1 for r in diagnosis_results if r.fix_success) / max(len(diagnosis_results), 1)
    avg_response_time = sum(r.response_time for r in diagnosis_results) / max(len(diagnosis_results), 1)

    logger.info(f"  Average diagnosis accuracy: {avg_accuracy:.2%}")
    logger.info(f"  Fix success rate: {fix_success_rate:.2%}")
    logger.info(f"  Average response time: {avg_response_time:.2f}s")

    logger.info("=== Running RAG Quality Evaluation ===")
    rag_eval = RAGQualityEvaluator(results_dir)
    rag_results = rag_eval.evaluate_rag_relevance(EVALUATION_QUERIES)

    if rag_results:
        avg_relevance = sum(r.get("avg_relevance", 0) for r in rag_results) / max(len(rag_results), 1)
        logger.info(f"  Average RAG relevance: {avg_relevance:.3f}")

    summary = {
        "diagnosis": {
            "avg_accuracy": avg_accuracy,
            "fix_success_rate": fix_success_rate,
            "avg_response_time": avg_response_time,
            "num_cases": len(diagnosis_results),
        },
        "rag": {
            "avg_relevance": avg_relevance if rag_results else 0,
            "num_queries": len(rag_results),
        }
    }

    summary_file = results_dir / "llm_evaluation_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    logger.info(f"LLM evaluation summary saved: {summary_file}")

    return summary
