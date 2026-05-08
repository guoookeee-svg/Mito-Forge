"""
集中判定与工具计划选择（可供 pipeline 与 nodes/supervisor 复用）
"""
from typing import List, Union, Dict, Any

def detect_seq_type(reads_paths: Union[str, List[str]]) -> str:
    if not reads_paths:
        return "illumina"
    paths = [str(p).lower() for p in (reads_paths if isinstance(reads_paths, (list, tuple)) else [reads_paths])]
    sigs = set()
    for p in paths:
        if ("r1" in p or "r2" in p or "_1" in p or "_2" in p):
            sigs.add("illumina")
        if ("ont" in p or "nanopore" in p):
            sigs.add("ont")
        if ("hifi" in p or "ccs" in p):
            sigs.add("pacbio-hifi")
        if ("clr" in p):
            sigs.add("pacbio-clr")
    if len(sigs) > 1:
        return "hybrid"
    if sigs:
        return next(iter(sigs))
    return "illumina"

def detect_input_types(reads: Union[str, List[str]]) -> List[str]:
    items = reads if isinstance(reads, (list, tuple)) else [reads]
    types = set()
    for it in items:
        s = str(it).lower()
        if s.endswith((".fastq", ".fq")):
            types.add("FASTQ")
        elif s.endswith((".fasta", ".fa")):
            types.add("FASTA")
        elif s.endswith(".bam"):
            types.add("BAM")
        else:
            types.add("UNKNOWN")
    # 若混合，只保留已知优先类型（FASTQ/FASTA/BAM），UNKNOWN 仅在全未知时出现
    known = [t for t in ["FASTQ","FASTA","BAM"] if t in types]
    return known if known else ["UNKNOWN"]

def select_tool_plan(seq_type: str, kingdom: str = None, input_types: List[str] = None) -> Dict[str, Any]:
    st = (seq_type or "illumina").lower()
    kg = (kingdom or "").lower() if kingdom else None
    itypes = [s.upper() for s in (input_types or [])]

    if kg == "plant":
        annotator_candidates = ["PMGA", "MITOFY", "BLAST+", "GeSeq", "Basic"]
        default_annotator = "pmga"
    else:
        annotator_candidates = ["MITOS", "Prokka", "Basic"]
        default_annotator = "mitos"

    if st == "illumina":
        plan = {
            "qc": ["fastp", "fastqc"],
            "assembler": {"name": "spades", "params": {"mode": "isolate"}},
            "polishers": ["pilon"],
        }
        candidates_asm = ["SPAdes"]
        if kg == "animal":
            candidates_asm = ["MitoZ", "GetOrganelle", "NOVOPlasty", "SPAdes"]
        elif kg == "plant":
            candidates_asm = ["GetOrganelle", "NOVOPlasty", "SPAdes"]
        elif kg == "fungi":
            candidates_asm = ["Norgal", "NOVOPlasty", "SPAdes"]
        plan["candidates"] = {
            "assembler": candidates_asm,
            "qc": ["fastp", "fastqc"],
            "polishers": ["pilon"],
        }
        plan["extras"] = {
            "mappers": ["minimap2"] if "FASTA" in itypes else [],
            "baiting_tools": (["MITObim", "ARC"] if "BAM" in itypes else []),
        }
        plan["annotator"] = default_annotator
        plan["candidates"]["annotator"] = annotator_candidates
        plan["hints"] = {"kingdom": kingdom, "input_types": itypes}
        return plan

    if st == "ont":
        plan = {
            "qc": [],  # ONT数据直接组装,不需要QC
            "assembler": {"name": "flye", "params": {"mode": "ont"}},
            "polishers": ["racon", "medaka"],
        }
        plan["candidates"] = {
            "assembler": ["Flye", "Canu"],
            "qc": [],  # ONT数据直接组装,不需要QC
            "polishers": ["Racon", "Medaka"],
        }
        plan["extras"] = {"mappers": ["minimap2"], "baiting_tools": []}
        plan["annotator"] = default_annotator
        plan["candidates"]["annotator"] = annotator_candidates
        plan["hints"] = {"kingdom": kingdom, "input_types": itypes}
        return plan

    if st == "pacbio-hifi":
        plan = {
            "qc": [],  # HiFi数据质量高,不需要QC
            "assembler": {"name": "hifiasm", "params": {}},
            "polishers": [],
        }
        plan["candidates"] = {
            "assembler": (["MitoHiFi", "hifiasm", "Flye"] if kg == "animal" else ["hifiasm", "Flye"]),
            "qc": [],  # HiFi数据质量高,不需要QC
            "polishers": [],
        }
        plan["extras"] = {"mappers": ["minimap2"], "baiting_tools": []}
        plan["annotator"] = default_annotator
        plan["candidates"]["annotator"] = annotator_candidates
        plan["hints"] = {"kingdom": kingdom, "input_types": itypes}
        return plan

    if st == "pacbio-clr":
        plan = {
            "qc": [],  # 三代测序直接组装,不需要QC
            "assembler": {"name": "flye", "params": {"mode": "pacbio-raw"}},
            "polishers": ["racon", "racon"],
        }
        plan["candidates"] = {
            "assembler": ["Flye", "Canu"],
            "qc": [],  # 三代测序直接组装,不需要QC
            "polishers": ["Racon", "Racon"],
        }
        plan["extras"] = {"mappers": ["minimap2"], "baiting_tools": []}
        plan["annotator"] = default_annotator
        plan["candidates"]["annotator"] = annotator_candidates
        plan["hints"] = {"kingdom": kingdom, "input_types": itypes}
        return plan

    if st == "hybrid":
        plan = {
            "qc": ["fastp", "longread_stats"],
            "assembler": {"name": "unicycler", "params": {}},
            "polishers": ["racon", "pilon"],
        }
        plan["candidates"] = {
            "assembler": ["Unicycler", "SPAdes"],
            "qc": ["fastp", "longread_stats"],
            "polishers": ["Racon", "Pilon"],
        }
        plan["extras"] = {"mappers": ["minimap2"], "baiting_tools": []}
        plan["annotator"] = default_annotator
        plan["candidates"]["annotator"] = annotator_candidates
        plan["hints"] = {"kingdom": kingdom, "input_types": itypes}
        return plan

    plan = {
        "qc": ["fastp"],
        "assembler": {"name": "spades", "params": {}},
        "polishers": [],
    }
    plan["candidates"] = {"assembler": ["SPAdes"], "qc": ["fastp"], "polishers": []}
    plan["extras"] = {"mappers": [], "baiting_tools": (["MITObim", "ARC"] if "BAM" in itypes else [])}
    plan["annotator"] = default_annotator
    plan["candidates"]["annotator"] = annotator_candidates
    plan["hints"] = {"kingdom": kingdom, "input_types": itypes}
    return plan

def build_tool_plan(seq_type: str, kingdom: str, reads: Union[str, List[str]]) -> Dict[str, Any]:
    # 统一入口：基于 reads 推断 input_types，并生成 plan
    input_types = detect_input_types(reads)
    return select_tool_plan(seq_type, kingdom=kingdom, input_types=input_types)