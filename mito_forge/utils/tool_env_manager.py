"""
工具独立环境管理器
为每个生物信息学工具创建和管理独立的conda环境
"""
import re
import shlex
from pathlib import Path
import subprocess
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_safe_name(name: str, field: str = "name") -> None:
    if not _SAFE_NAME_RE.match(name):
        raise ValueError(f"Invalid {field}: {name!r} (only alphanumeric, dash, underscore allowed)")


class ToolEnvironmentManager:
    """管理工具的独立conda环境"""
    
    def __init__(self, tools_dir: Optional[Path] = None):
        if tools_dir is None:
            # 默认使用项目的tools目录
            tools_dir = Path(__file__).parent.parent / "tools"
        self.tools_dir = Path(tools_dir)
        self.envs_dir = self.tools_dir / "envs"
        self.bin_dir = self.tools_dir / "bin"
        
    def get_env_name(self, tool_name: str) -> str:
        """获取工具的环境名称"""
        return f"mito-forge-{tool_name}"
    
    def get_env_yaml(self, tool_name: str) -> Optional[Path]:
        """获取工具的环境配置文件路径"""
        yaml_file = self.envs_dir / f"{tool_name}_env.yaml"
        return yaml_file if yaml_file.exists() else None
    
    def env_exists(self, tool_name: str) -> bool:
        """检查工具的conda环境是否已存在"""
        env_name = self.get_env_name(tool_name)
        try:
            result = subprocess.run(
                ["conda", "env", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return env_name in result.stdout
        except Exception as e:
            logger.warning(f"Failed to check conda environment: {e}")
            return False
    
    def create_env(self, tool_name: str, force: bool = False, use_yaml: bool = True) -> bool:
        """
        创建工具的conda环境
        
        Args:
            tool_name: 工具名称
            force: 如果环境已存在,是否强制重建
            use_yaml: 是否使用YAML文件创建(False则直接用命令行)
            
        Returns:
            是否成功创建
        """
        env_name = self.get_env_name(tool_name)
        
        # 检查环境是否已存在
        if self.env_exists(tool_name):
            if not force:
                logger.info(f"Environment {env_name} already exists")
                return True
            else:
                logger.info(f"Removing existing environment {env_name}...")
                subprocess.run(["conda", "env", "remove", "-n", env_name, "-y"])
        
        logger.info(f"Creating conda environment for {tool_name}...")
        
        # 检查是否有mamba(更快的conda替代品)
        has_mamba = False
        try:
            result = subprocess.run(["which", "mamba"], capture_output=True, timeout=5)
            has_mamba = result.returncode == 0
            if has_mamba:
                logger.info("Detected mamba, will use it for faster environment creation")
        except Exception:
            pass
        
        # 方式1: 使用YAML文件
        if use_yaml:
            yaml_file = self.get_env_yaml(tool_name)
            if not yaml_file:
                logger.warning(f"No YAML config found, trying direct method...")
                use_yaml = False
            else:
                logger.info(f"Using config: {yaml_file}")
                try:
                    # 优先使用mamba
                    cmd = ["mamba" if has_mamba else "conda", "env", "create", "-f", str(yaml_file)]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=1800  # 30分钟超时
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"✅ Successfully created environment {env_name}")
                        return True
                    else:
                        logger.error(f"Failed to create environment: {result.stderr}")
                        return False
                        
                except subprocess.TimeoutExpired:
                    logger.error(f"Timeout creating environment for {tool_name}")
                    return False
                except Exception as e:
                    logger.error(f"Error creating environment: {e}")
                    return False
        
        # 方式2: 直接命令行创建(备用方案)
        if not use_yaml:
            deps = self.get_env_dependencies(tool_name)
            if not deps:
                logger.error(f"No dependencies found for {tool_name}")
                return False
            
            # 构建包列表,版本约束需要引号
            packages = []
            for pkg, version in deps.items():
                if version and version != "*":
                    packages.append(f"{pkg}{version}")
                else:
                    packages.append(pkg)
            
            logger.info(f"Creating environment with: {' '.join(packages)}")
            
            try:
                # 优先使用mamba
                base_cmd = "mamba" if has_mamba else "conda"
                cmd = [base_cmd, "create", "-n", env_name, "-c", "bioconda", "-c", "conda-forge", "-y"] + packages
                logger.info(f"Command: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=1800
                )
                
                if result.returncode == 0:
                    logger.info(f"✅ Successfully created environment {env_name}")
                    return True
                else:
                    logger.error(f"Failed to create environment: {result.stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                logger.error(f"Timeout creating environment for {tool_name}")
                return False
            except Exception as e:
                logger.error(f"Error creating environment: {e}")
                return False
    
    def generate_wrapper(self, tool_name: str, exe_path: str, 
                        wrapper_path: Path) -> bool:
        """
        生成工具的wrapper脚本
        
        Args:
            tool_name: 工具名称
            exe_path: 实际可执行文件的相对路径
            wrapper_path: wrapper脚本保存路径
            
        Returns:
            是否成功生成
        """
        _validate_safe_name(tool_name, "tool_name")
        env_name = self.get_env_name(tool_name)
        safe_env_name = shlex.quote(env_name)
        safe_tool_name = shlex.quote(tool_name)
        safe_exe_path = shlex.quote(exe_path)
        
        wrapper_content = f'''#!/usr/bin/env bash
# Auto-generated wrapper for {safe_tool_name}
# Activates conda environment and executes tool

set -e

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
TOOL_PATH="$SCRIPT_DIR/{safe_exe_path}"

# 激活conda环境
eval "$(conda shell.bash hook)"
conda activate {safe_env_name} 2>/dev/null || {{
    echo "Error: Conda environment '{safe_env_name}' not found" >&2
    echo "Please run: mito-forge tools setup-env {safe_tool_name}" >&2
    exit 1
}}

# 执行工具
exec "$TOOL_PATH" "$@"
'''
        
        try:
            wrapper_path.parent.mkdir(parents=True, exist_ok=True)
            wrapper_path.write_text(wrapper_content)
            wrapper_path.chmod(0o755)  # 设置可执行权限
            logger.info(f"✅ Generated wrapper: {wrapper_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to generate wrapper: {e}")
            return False
    
    def setup_tool(self, tool_name: str, exe_relative_path: str) -> bool:
        """
        完整设置工具:创建环境+生成wrapper
        
        Args:
            tool_name: 工具名称
            exe_relative_path: 实际可执行文件相对于bin/{tool}/version/的路径
            
        Returns:
            是否成功
        """
        # 创建环境
        if not self.create_env(tool_name):
            return False
        
        # 生成wrapper
        # 假设wrapper放在bin/{tool}/latest/{tool}
        wrapper_path = self.bin_dir / tool_name / "latest" / tool_name
        if not self.generate_wrapper(tool_name, exe_relative_path, wrapper_path):
            return False
        
        return True
    
    def list_available_envs(self) -> List[str]:
        """列出所有可用的环境配置"""
        if not self.envs_dir.exists():
            return []
        
        yaml_files = list(self.envs_dir.glob("*_env.yaml"))
        return [f.stem.replace("_env", "") for f in yaml_files]
    
    def get_env_info(self, tool_name: str) -> Dict[str, any]:
        """获取工具环境的信息"""
        return {
            "tool_name": tool_name,
            "env_name": self.get_env_name(tool_name),
            "yaml_file": str(self.get_env_yaml(tool_name)),
            "exists": self.env_exists(tool_name)
        }
    
    def get_env_bin_path(self, tool_name: str) -> Optional[Path]:
        """
        获取工具环境的bin目录路径
        
        Returns:
            环境bin路径,如果环境不存在则返回None
        """
        if not self.env_exists(tool_name):
            return None
        
        env_name = self.get_env_name(tool_name)
        try:
            # 获取conda base路径
            result = subprocess.run(
                ["conda", "info", "--base"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                conda_base = Path(result.stdout.strip())
                env_bin = conda_base / "envs" / env_name / "bin"
                if env_bin.exists():
                    return env_bin
        except Exception as e:
            logger.warning(f"Failed to get env bin path: {e}")
        
        return None
    
    def get_tool_required_env(self, tool_name: str) -> Optional[str]:
        """
        从sources.json获取工具需要的环境名称
        
        Args:
            tool_name: 工具名称(如 pmat2, spades)
            
        Returns:
            环境名称(如 pmat),如果不需要环境则返回None
        """
        sources_file = self.tools_dir / "sources.json"
        if not sources_file.exists():
            return None
        
        try:
            import json
            sources = json.loads(sources_file.read_text())
            tool_config = sources.get(tool_name, {})
            return tool_config.get("requires_env")
        except Exception as e:
            logger.warning(f"Failed to get tool env requirement: {e}")
            return None
    
    def get_env_dependencies(self, tool_name: str) -> Dict[str, str]:
        """
        从sources.json获取工具的环境依赖
        
        Args:
            tool_name: 工具名称
            
        Returns:
            依赖字典,如 {"blast": ">=2.10.0"}
        """
        sources_file = self.tools_dir / "sources.json"
        if not sources_file.exists():
            return {}
        
        try:
            import json
            sources = json.loads(sources_file.read_text())
            tool_config = sources.get(tool_name, {})
            return tool_config.get("env_dependencies", {})
        except Exception:
            return {}
