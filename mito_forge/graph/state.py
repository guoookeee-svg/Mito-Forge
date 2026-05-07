"""
LangGraph 状态定义
定义整个线粒体组装流水线的状态结构
"""
from typing import Dict, Any, List, Optional, TypedDict, Literal, Union
from pathlib import Path
import time
import json
from datetime import datetime
from enum import Enum

# === 枚举定义 ===

class StageStatus(str, Enum):
    """阶段状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"

class RouteDecision(str, Enum):
    """路由决策枚举"""
    CONTINUE = "continue"
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    TERMINATE = "terminate"

class DataType(str, Enum):
    """数据类型枚举"""
    NANOPORE = "nanopore"
    ILLUMINA = "illumina"
    PACBIO_HIFI = "pacbio_hifi"
    PACBIO_CLR = "pacbio_clr"

class Kingdom(str, Enum):
    """物种类型枚举"""
    ANIMAL = "animal"
    PLANT = "plant"
    FUNGI = "fungi"

# === 类型定义 ===

StageName = Literal["supervisor", "qc", "assembly", "polish", "annotation", "report"]

class InputData(TypedDict):
    """输入数据结构"""
    reads: Union[str, List[str]]        # 测序数据文件路径（R1 或单端）
    reads2: Optional[str]               # 第二个测序文件（双端测序 R2）
    read_type: DataType                 # 数据类型
    kingdom: Kingdom                    # 物种类型
    species: Optional[str]              # 物种名称
    reference: Optional[str]            # 参考序列（可选）

class PipelineConfig(TypedDict):
    """流水线配置"""
    # 计算资源
    threads: int                        # CPU 线程数
    memory: str                         # 内存限制，如 "16G"
    timeout: int                        # 超时时间（秒）
    
    # 工具配置
    tools: Dict[str, str]               # 工具路径映射
    tool_params: Dict[str, Dict[str, Any]]  # 工具参数配置
    
    # 流水线行为
    max_retries: int                    # 最大重试次数
    skip_qc: bool                       # 是否跳过质控
    skip_annotation: bool               # 是否跳过注释
    cleanup_temp: bool                  # 是否清理临时文件
    
    # 输出配置
    output_formats: List[str]           # 输出格式列表
    generate_report: bool               # 是否生成报告

class StageInfo(TypedDict):
    """阶段信息"""
    name: StageName                     # 阶段名称
    status: StageStatus                 # 执行状态
    start_time: Optional[float]         # 开始时间
    end_time: Optional[float]           # 结束时间
    duration: Optional[float]           # 执行时长（秒）
    tool_used: Optional[str]            # 使用的工具
    command: Optional[str]              # 执行的命令
    exit_code: Optional[int]            # 退出码
    retry_count: int                    # 重试次数

class ResourceUsage(TypedDict):
    """资源使用情况"""
    cpu_percent: Optional[float]        # CPU 使用率
    memory_mb: Optional[float]          # 内存使用量（MB）
    disk_mb: Optional[float]            # 磁盘使用量（MB）
    peak_memory_mb: Optional[float]     # 峰值内存使用量

class PipelineState(TypedDict):
    """流水线状态 - LangGraph 的核心状态对象"""
    
    # === 输入与配置 ===
    inputs: InputData                   # 标准化输入数据
    config: PipelineConfig              # 流水线配置
    workdir: str                        # 工作目录路径
    
    # === 执行状态 ===
    current_stage: StageName            # 当前执行阶段
    stage_info: Dict[str, StageInfo]    # 各阶段详细信息
    completed_stages: List[StageName]   # 已完成阶段列表
    failed_stages: List[StageName]      # 失败阶段列表
    
    # === 数据流 ===
    stage_outputs: Dict[str, "StageOutputs"]  # 各阶段输出
    global_metrics: Dict[str, Any]      # 全局统计指标
    logs: Dict[str, str]                # 日志文件路径映射
    
    # === 控制流 ===
    route: RouteDecision                # 当前路由决策
    retries: Dict[str, int]             # 各阶段重试计数
    errors: List[str]                   # 错误记录列表
    warnings: List[str]                 # 警告记录列表
    
    # === 资源监控 ===
    resource_usage: Dict[str, ResourceUsage]  # 各阶段资源使用情况
    
    # === 元数据 ===
    pipeline_id: str                    # 流水线唯一标识符
    version: str                        # 流水线版本
    start_time: float                   # 开始时间戳
    end_time: Optional[float]           # 结束时间戳
    checkpoint_path: Optional[str]      # 检查点文件路径
    done: bool                          # 是否完成标志

class FileInfo(TypedDict):
    """文件信息"""
    path: str                           # 文件路径
    size_bytes: Optional[int]           # 文件大小
    checksum: Optional[str]             # 文件校验和
    created_time: Optional[float]       # 创建时间

class StageOutputs(TypedDict):
    """阶段输出标准格式"""
    files: Dict[str, FileInfo]          # 输出文件信息
    metrics: Dict[str, Union[int, float, str]]  # 数值指标
    metadata: Dict[str, Any]            # 工具和版本等元数据
    summary: str                        # 阶段执行摘要
    success: bool                       # 是否成功完成

class QCOutputs(StageOutputs):
    """质控阶段输出"""
    files: Dict[Literal["clean_reads", "qc_report", "stats"], FileInfo]
    metrics: Dict[Literal["total_reads", "clean_reads", "qc_score", "avg_quality"], Union[int, float]]

class AssemblyOutputs(StageOutputs):
    """组装阶段输出"""
    files: Dict[Literal["contigs", "scaffolds", "assembly_graph"], FileInfo]
    metrics: Dict[Literal["n50", "total_length", "num_contigs", "largest_contig"], Union[int, float]]

class AnnotationOutputs(StageOutputs):
    """注释阶段输出"""
    files: Dict[Literal["gff", "genbank", "proteins", "features"], FileInfo]
    metrics: Dict[Literal["num_genes", "num_trnas", "num_rrnas", "completeness"], Union[int, float]]

class ReportOutputs(StageOutputs):
    """报告阶段输出"""
    files: Dict[Literal["html_report", "pdf_report", "summary_json"], FileInfo]
    metrics: Dict[Literal["total_runtime", "success_rate"], Union[int, float]]

# === 状态操作辅助函数 ===

def init_pipeline_state(
    inputs: InputData,
    config: PipelineConfig,
    workdir: str,
    pipeline_id: Optional[str] = None,
    version: str = "1.0.0"
) -> PipelineState:
    """初始化流水线状态"""
    import uuid
    
    # 初始化阶段信息
    stage_names: List[StageName] = ["supervisor", "qc", "assembly", "polish", "annotation", "report"]
    stage_info = {}
    for stage in stage_names:
        stage_info[stage] = StageInfo(
            name=stage,
            status=StageStatus.PENDING,
            start_time=None,
            end_time=None,
            duration=None,
            tool_used=None,
            command=None,
            exit_code=None,
            retry_count=0
        )
    
    return PipelineState(
        # 输入与配置
        inputs=inputs,
        config=config,
        workdir=workdir,
        
        # 执行状态
        current_stage="supervisor",
        stage_info=stage_info,
        completed_stages=[],
        failed_stages=[],
        
        # 数据流
        stage_outputs={},
        global_metrics={},
        logs={},
        
        # 控制流
        route=RouteDecision.CONTINUE,
        retries={},
        errors=[],
        warnings=[],
        
        # 资源监控
        resource_usage={},
        
        # 元数据
        pipeline_id=pipeline_id or str(uuid.uuid4()),
        version=version,
        start_time=time.time(),
        end_time=None,
        checkpoint_path=None,
        done=False
    )

def start_stage(state: PipelineState, stage: StageName) -> PipelineState:
    """开始执行阶段"""
    state["current_stage"] = stage
    state["stage_info"][stage]["status"] = StageStatus.RUNNING
    state["stage_info"][stage]["start_time"] = time.time()
    return state

def complete_stage(state: PipelineState, stage: StageName, outputs: StageOutputs) -> PipelineState:
    """完成阶段执行"""
    current_time = time.time()
    
    # 更新阶段信息
    stage_info = state["stage_info"][stage]
    stage_info["status"] = StageStatus.SUCCESS
    stage_info["end_time"] = current_time
    if stage_info["start_time"]:
        stage_info["duration"] = current_time - stage_info["start_time"]
    
    # 更新完成列表和输出
    if stage not in state["completed_stages"]:
        state["completed_stages"].append(stage)
    state["stage_outputs"][stage] = outputs
    
    # 合并指标
    state["global_metrics"].update(outputs.get("metrics", {}))
    
    return state

def fail_stage(state: PipelineState, stage: StageName, error: str, exit_code: Optional[int] = None) -> PipelineState:
    """标记阶段失败"""
    current_time = time.time()
    
    stage_info = state["stage_info"][stage]
    stage_info["status"] = StageStatus.FAILED
    stage_info["end_time"] = current_time
    stage_info["exit_code"] = exit_code
    if stage_info["start_time"]:
        stage_info["duration"] = current_time - stage_info["start_time"]
    
    if stage not in state["failed_stages"]:
        state["failed_stages"].append(stage)
    
    state["errors"].append(f"[{datetime.now().isoformat()}] {stage}: {error}")
    
    return state

def retry_stage(state: PipelineState, stage: StageName) -> PipelineState:
    """重试阶段"""
    stage_info = state["stage_info"][stage]
    stage_info["status"] = StageStatus.RETRYING
    stage_info["retry_count"] += 1
    state["retries"][stage] = state["retries"].get(stage, 0) + 1
    
    if stage in state["failed_stages"]:
        state["failed_stages"].remove(stage)
    
    state["route"] = RouteDecision.RETRY
    return state

def skip_stage(state: PipelineState, stage: StageName, reason: str) -> PipelineState:
    """跳过阶段"""
    stage_info = state["stage_info"][stage]
    stage_info["status"] = StageStatus.SKIPPED
    
    state["warnings"].append(f"[{datetime.now().isoformat()}] {stage} skipped: {reason}")
    
    # 添加到完成列表（跳过也算完成）
    if stage not in state["completed_stages"]:
        state["completed_stages"].append(stage)
    
    return state

def is_pipeline_complete(state: PipelineState) -> bool:
    """检查流水线是否完成"""
    required_stages: List[StageName] = ["qc", "assembly"]
    
    if not state["config"].get("skip_annotation", False):
        required_stages.append("annotation")
    
    if state["config"].get("generate_report", True):
        required_stages.append("report")
    
    completed = set(state["completed_stages"])
    return all(stage in completed for stage in required_stages)

def should_retry_stage(state: PipelineState, stage: StageName) -> bool:
    """判断是否应该重试阶段"""
    max_retries = state["config"]["max_retries"]
    current_retries = state["retries"].get(stage, 0)
    return current_retries < max_retries

def get_next_stage(state: PipelineState) -> Union[StageName, Literal["END"]]:
    """根据当前状态和配置决定下一个阶段"""
    completed = set(state["completed_stages"])
    config = state["config"]
    
    # 阶段依赖关系和配置检查
    if not config["skip_qc"] and "qc" not in completed:
        return "qc"
    elif "assembly" not in completed:
        return "assembly"
    elif not config["skip_annotation"] and "annotation" not in completed:
        return "annotation"
    elif config["generate_report"] and "report" not in completed:
        return "report"
    else:
        return "END"

def get_pipeline_progress(state: PipelineState) -> Dict[str, Any]:
    """获取流水线执行进度"""
    total_stages = len(state["stage_info"])
    completed_count = len(state["completed_stages"])
    failed_count = len(state["failed_stages"])
    
    # 计算总体进度百分比
    progress_percent = (completed_count / total_stages) * 100 if total_stages > 0 else 0
    
    # 计算总执行时间
    total_duration = 0.0
    for stage_info in state["stage_info"].values():
        if stage_info["duration"]:
            total_duration += stage_info["duration"]
    
    return {
        "total_stages": total_stages,
        "completed": completed_count,
        "failed": failed_count,
        "progress_percent": round(progress_percent, 2),
        "current_stage": state["current_stage"],
        "total_duration_sec": round(total_duration, 2),
        "pipeline_id": state["pipeline_id"],
        "is_complete": state["done"]
    }

def save_checkpoint(state: PipelineState, checkpoint_path: str) -> bool:
    """保存检查点"""
    try:
        checkpoint_data = {
            "state": dict(state),
            "timestamp": time.time(),
            "version": state["version"]
        }
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
        
        # 更新状态中的检查点路径
        state["checkpoint_path"] = checkpoint_path
        return True
    except Exception as e:
        state["warnings"].append(f"Failed to save checkpoint: {str(e)}")
        return False

def load_checkpoint(checkpoint_path: str) -> Optional[PipelineState]:
    """加载检查点"""
    try:
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            checkpoint_data = json.load(f)
        
        # 验证版本兼容性
        saved_version = checkpoint_data.get("version", "unknown")
        
        return PipelineState(checkpoint_data["state"])
    except Exception:
        return None

def finalize_pipeline(state: PipelineState) -> PipelineState:
    """完成流水线执行"""
    state["done"] = True
    state["end_time"] = time.time()
    
    # 计算总执行时间
    if state["start_time"]:
        total_duration = state["end_time"] - state["start_time"]
        state["global_metrics"]["total_runtime_sec"] = round(total_duration, 2)
    
    # 计算成功率
    total_stages = len(state["stage_info"])
    successful_stages = len(state["completed_stages"])
    success_rate = (successful_stages / total_stages) * 100 if total_stages > 0 else 0
    state["global_metrics"]["success_rate_percent"] = round(success_rate, 2)
    
    return state

def validate_state(state: PipelineState) -> List[str]:
    """验证状态完整性"""
    issues = []
    
    # 检查必需字段
    if not state.get("pipeline_id"):
        issues.append("Missing pipeline_id")
    
    if not state.get("workdir"):
        issues.append("Missing workdir")
    
    # 检查阶段一致性
    for stage in state["completed_stages"]:
        if stage not in state["stage_info"]:
            issues.append(f"Completed stage '{stage}' not found in stage_info")
    
    for stage in state["failed_stages"]:
        if stage not in state["stage_info"]:
            issues.append(f"Failed stage '{stage}' not found in stage_info")
    
    return issues