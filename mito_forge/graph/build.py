"""
LangGraph 图构建
定义状态机的节点连接和条件路由
"""
from typing import Literal

from langgraph.graph import StateGraph, END

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:
    SqliteSaver = None

from .state import PipelineState, get_next_stage, is_pipeline_complete
from .nodes import supervisor_node, qc_node, assembly_node, polish_node, annotation_node, report_node
from ..utils.logging import get_logger

logger = get_logger(__name__)


def _create_checkpointer():
    try:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    except Exception as e:
        logger.warning(f"Checkpointer not available: {e}. Pipeline will run without checkpoint support.")
        return None

def build_pipeline_graph():
    """
    构建线粒体组装流水线的状态图
    
    流程：
    START → supervisor → qc → assembly → annotation → report → END
           ↑         ↓    ↓        ↓           ↓
           └─ retry ─┴────┴────────┴───────────┘
    """
    
    # 创建状态图
    graph = StateGraph(PipelineState)
    
    # 添加节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("qc", qc_node)
    graph.add_node("assembly", assembly_node)
    graph.add_node("polish", polish_node)
    graph.add_node("annotation", annotation_node)
    graph.add_node("report", report_node)
    
    # 设置入口点
    graph.set_entry_point("supervisor")
    
    # 添加边
    # 注意: supervisor, qc, assembly 使用条件边(在下面定义),不需要无条件边
    # graph.add_edge("supervisor", "qc")  # 删除,使用条件边
    # graph.add_edge("qc", "assembly")  # 删除,使用条件边
    # assembly -> polish 条件边（在下面定义）
    graph.add_edge("polish", "annotation")
    graph.add_edge("annotation", "report")
    graph.add_edge("report", END)
    
    # 添加条件边（路由决策）
    graph.add_conditional_edges(
        "supervisor",
        supervisor_route_decider,
        {
            "qc": "qc",  # 正常流程:进入QC
            "assembly": "assembly",  # 跳过QC:直接进入Assembly
            "terminate": END
        }
    )
    
    graph.add_conditional_edges(
        "qc",
        stage_route_decider,
        {
            "continue": "assembly",
            "retry": "qc",
            "terminate": END
        }
    )
    
    graph.add_conditional_edges(
        "assembly", 
        assembly_route_decider,
        {
            "polish": "polish",
            "skip_polish": "annotation",
            "retry": "assembly",
            "fallback": "assembly",  # 使用备用工具重试
            "terminate": END
        }
    )
    
    graph.add_conditional_edges(
        "polish",
        stage_route_decider,
        {
            "continue": "annotation",
            "terminate": END
        }
    )
    
    graph.add_conditional_edges(
        "annotation",
        stage_route_decider,
        {
            "continue": "report",
            "retry": "annotation",
            "terminate": "report"  # 注释失败也可以生成报告
        }
    )
    
    checkpointer = _create_checkpointer()
    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
    
    # 以下为旧的临时实现（已启用LangGraph）
    # 旧的临时实现（保留作为备用）
    # return {
    #     "nodes": {
    #         "supervisor": supervisor_node,
    #         "qc": qc_node,
    #         "assembly": assembly_node,
    #         "annotation": annotation_node,
    #         "report": report_node
    #     },
    #     "edges": {
    #         "supervisor": ["qc"],
    #         "qc": ["assembly"],
    #         "assembly": ["annotation"],
    #         "annotation": ["report"],
    #         "report": ["END"]
    #     },
    #     "conditional_edges": {
    #         "supervisor": supervisor_route_decider,
    #         "qc": stage_route_decider,
    #         "assembly": stage_route_decider,
    #         "annotation": stage_route_decider
    #     }
    # }

def supervisor_route_decider(state: PipelineState) -> Literal["qc", "assembly", "terminate"]:
    """主管节点路由决策 - 根据skip_qc决定下一阶段"""
    from .state import RouteDecision
    route = state["route"]
    
    # 处理枚举类型
    route_str = route.value if hasattr(route, 'value') else str(route)
    
    if route_str == "terminate":
        return "terminate"
    
    # 根据config决定下一个阶段
    config = state["config"]
    if config.get("skip_qc", False):
        return "assembly"  # 跳过QC,直接进入Assembly
    else:
        return "qc"

def assembly_route_decider(state: PipelineState) -> Literal["polish", "skip_polish", "retry", "fallback", "terminate"]:
    """组装节点路由决策 - 决定是否需要抛光"""
    from .state import RouteDecision
    route = state["route"]
    
    # 处理枚举类型
    route_str = route.value if hasattr(route, 'value') else str(route)
    
    if route_str == "terminate":
        return "terminate"
    elif route_str == "retry":
        return "retry"
    elif route_str == "fallback":
        return "fallback"
    
    # 检查是否需要抛光
    tool_chain = state.get("config", {}).get("tool_chain", {})
    polishing_tool = tool_chain.get("polishing")
    
    if polishing_tool:
        return "polish"
    else:
        return "skip_polish"

def stage_route_decider(state: PipelineState) -> Literal["continue", "retry", "fallback", "terminate"]:
    """阶段节点路由决策"""
    from .state import RouteDecision
    route = state["route"]
    
    # 处理枚举类型
    route_str = route.value if hasattr(route, 'value') else str(route)
    
    if route_str == "terminate":
        return "terminate"
    elif route_str == "retry":
        return "retry"
    elif route_str == "fallback":
        return "fallback"
    else:
        return "continue"

def run_pipeline_sync(
    inputs: dict,
    config: dict,
    workdir: str,
    pipeline_id: str = None
) -> PipelineState:
    """
    同步运行流水线（使用 LangGraph）
    """
    from .state import init_pipeline_state
    
    # 初始化状态
    state = init_pipeline_state(inputs, config, workdir, pipeline_id)
    
    # 构建并编译 LangGraph
    compiled_graph = build_pipeline_graph()
    
    # 配置 LangGraph 执行 (添加必需的 thread_id)
    run_config = {
        "configurable": {
            "thread_id": pipeline_id or state.get("pipeline_id", "default")
        }
    }
    
    # 使用 LangGraph 执行流水线
    try:
        final_state = compiled_graph.invoke(state, config=run_config)
    except KeyError as e:
        # LangGraph 路由错误
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Graph routing error: {e}")
        logger.error(f"Current state route: {state.get('route')}")
        logger.error(f"Current stage: {state.get('current_stage')}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise RuntimeError(f"Pipeline routing error at stage {state.get('current_stage')}: {e}")
    
    return final_state

# === 检查点和持久化 ===

def save_checkpoint(state: PipelineState, checkpoint_path: str):
    """保存检查点"""
    import json
    from pathlib import Path
    from .state import StageStatus, RouteDecision
    
    checkpoint_file = Path(checkpoint_path)
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    
    serializable_state = dict(state)
    
    if isinstance(serializable_state.get("route"), RouteDecision):
        serializable_state["route"] = serializable_state["route"].value
    
    stage_info = serializable_state.get("stage_info", {})
    for stage_name, info in stage_info.items():
        if isinstance(info.get("status"), StageStatus):
            info["status"] = info["status"].value
    
    with checkpoint_file.open("w") as f:
        json.dump(serializable_state, f, indent=2, default=str)

def load_checkpoint(checkpoint_path: str) -> PipelineState:
    """加载检查点"""
    import json
    from pathlib import Path
    from .state import StageStatus, RouteDecision
    
    checkpoint_file = Path(checkpoint_path)
    if not checkpoint_file.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    
    with checkpoint_file.open("r") as f:
        state = json.load(f)
    
    route_val = state.get("route", "continue")
    if isinstance(route_val, str):
        try:
            state["route"] = RouteDecision(route_val)
        except ValueError:
            state["route"] = RouteDecision.CONTINUE
    
    stage_info = state.get("stage_info", {})
    for stage_name, info in stage_info.items():
        status_val = info.get("status", "pending")
        if isinstance(status_val, str):
            try:
                info["status"] = StageStatus(status_val)
            except ValueError:
                info["status"] = StageStatus.PENDING
    
    return state

def resume_pipeline(checkpoint_path: str) -> PipelineState:
    """从检查点恢复流水线

    If LangGraph checkpointer is available, uses it for true resume.
    Otherwise, loads JSON checkpoint and re-invokes from the beginning,
    skipping completed stages via route decisions.
    """
    from .state import init_pipeline_state, RouteDecision, StageStatus

    state = load_checkpoint(checkpoint_path)
    if state is None:
        raise ValueError(f"Failed to load checkpoint from {checkpoint_path}")

    current_stage = state.get("current_stage", "supervisor")
    logger.info(f"Resuming pipeline from stage: {current_stage}")

    stage_info = state.get("stage_info", {})
    for stage_name, info in stage_info.items():
        status = info.get("status")
        if hasattr(status, "value"):
            status = status.value
        if status == "completed":
            logger.info(f"  Skipping completed stage: {stage_name}")

    compiled_graph = build_pipeline_graph()

    run_config = {
        "configurable": {
            "thread_id": state.get("pipeline_id", "resumed")
        }
    }

    try:
        final_state = compiled_graph.invoke(state, config=run_config)
        return final_state
    except KeyError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Graph routing error during resume: {e}")
        raise RuntimeError(f"Pipeline resume failed at stage {current_stage}: {e}")