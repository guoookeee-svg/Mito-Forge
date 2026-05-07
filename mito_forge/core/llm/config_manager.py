"""
模型配置管理器
提供用户友好的配置管理和模型切换功能
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path

from .unified_provider import UnifiedProvider
from ...utils.logging import get_logger

logger = get_logger(__name__)

class ModelConfigManager:
    """模型配置管理器"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录，默认为用户主目录下的 .mito-forge
        """
        if config_dir is None:
            config_dir = Path.home() / ".mito-forge"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.config_file = self.config_dir / "model_config.yaml"
        self.profiles_file = self.config_dir / "model_profiles.yaml"
        
        # 加载配置
        self.config = self._load_config()
        self.profiles = self._load_profiles()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载主配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")
        
        # 返回默认配置
        return {
            "default_profile": "openai",
            "fallback_profiles": ["ollama"],
            "auto_fallback": True
        }
    
    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        """加载模型配置文件"""
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load profiles file: {e}")
        
        # 返回默认配置文件
        return self._get_default_profiles()
    
    def _get_default_profiles(self) -> Dict[str, Dict[str, Any]]:
        """获取默认配置文件"""
        return {
            "openai": {
                "provider_type": "openai",
                "model": "gpt-4o-mini",
                "api_key": "${OPENAI_API_KEY}",
                "api_base": "https://api.openai.com/v1",
                "description": "OpenAI 官方 API"
            },
            
            "openai-gpt4": {
                "provider_type": "openai", 
                "model": "gpt-4o",
                "api_key": "${OPENAI_API_KEY}",
                "api_base": "https://api.openai.com/v1",
                "description": "OpenAI GPT-4"
            },
            
            "ollama": {
                "provider_type": "ollama",
                "model": "qwen2.5:7b",
                "api_base": "http://localhost:11434",
                "description": "本地 Ollama 服务"
            },
            
            "zhipu": {
                "provider_type": "zhipu",
                "model": "glm-4",
                "api_key": "${ZHIPU_API_KEY}",
                "description": "智谱 AI GLM-4"
            },
            
            "moonshot": {
                "provider_type": "moonshot",
                "model": "moonshot-v1-8k",
                "api_key": "${MOONSHOT_API_KEY}",
                "description": "月之暗面 Kimi"
            },
            
            "deepseek": {
                "provider_type": "deepseek",
                "model": "deepseek-chat",
                "api_key": "${DEEPSEEK_API_KEY}",
                "description": "DeepSeek Chat"
            },
            
            "custom": {
                "provider_type": "openai_compatible",
                "model": "gpt-3.5-turbo",
                "api_key": "${CUSTOM_API_KEY}",
                "api_base": "http://localhost:8000/v1",
                "description": "自定义 OpenAI 兼容 API"
            }
        }
    
    def save_config(self):
        """保存主配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def save_profiles(self):
        """保存配置文件"""
        try:
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.profiles, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
    
    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定配置文件"""
        profile = self.profiles.get(name)
        if profile:
            # 解析环境变量
            return self._resolve_env_vars(profile.copy())
        return None
    
    def _resolve_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解析配置中的环境变量"""
        resolved = {}
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                resolved[key] = os.getenv(env_var, "")
            else:
                resolved[key] = value
        return resolved
    
    def create_provider(self, profile_name: Optional[str] = None) -> UnifiedProvider:
        """
        创建模型提供者实例
        
        Args:
            profile_name: 配置文件名称，默认使用默认配置文件
            
        Returns:
            UnifiedProvider: 模型提供者实例
        """
        if profile_name is None:
            profile_name = self.config.get("default_profile", "openai")
        
        profile = self.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")
        
        return UnifiedProvider.create_from_config(profile)
    
    def create_provider_with_fallback(self) -> UnifiedProvider:
        """创建带回退的模型提供者"""
        # 尝试默认配置文件
        default_profile = self.config.get("default_profile", "openai")
        
        try:
            provider = self.create_provider(default_profile)
            if provider.is_available():
                logger.info(f"Using default profile: {default_profile}")
                return provider
        except Exception as e:
            logger.warning(f"Failed to create provider with default profile '{default_profile}': {e}")
        
        # 尝试回退配置文件
        if self.config.get("auto_fallback", True):
            fallback_profiles = self.config.get("fallback_profiles", [])
            
            for profile_name in fallback_profiles:
                try:
                    provider = self.create_provider(profile_name)
                    if provider.is_available():
                        logger.info(f"Using fallback profile: {profile_name}")
                        return provider
                except Exception as e:
                    logger.warning(f"Failed to create provider with fallback profile '{profile_name}': {e}")
        
        raise RuntimeError("No available model providers found")
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """列出所有配置文件"""
        profiles = []
        for name, config in self.profiles.items():
            has_api_key = bool(config.get("api_key") and not config["api_key"].startswith("${"))
            profiles.append({
                "name": name,
                "description": config.get("description", ""),
                "provider_type": config.get("provider_type", ""),
                "model": config.get("model", ""),
                "has_api_key": has_api_key
            })
        return profiles
    
    def add_profile(self, name: str, config: Dict[str, Any]):
        """添加新的配置文件"""
        self.profiles[name] = config
        self.save_profiles()
        logger.info(f"Added profile: {name}")
    
    def update_profile(self, name: str, config: Dict[str, Any]):
        """更新配置文件"""
        if name not in self.profiles:
            raise ValueError(f"Profile '{name}' not found")
        
        self.profiles[name].update(config)
        self.save_profiles()
        logger.info(f"Updated profile: {name}")
    
    def remove_profile(self, name: str):
        """删除配置文件"""
        if name not in self.profiles:
            raise ValueError(f"Profile '{name}' not found")
        
        del self.profiles[name]
        self.save_profiles()
        logger.info(f"Removed profile: {name}")
    
    def set_default_profile(self, name: str):
        """设置默认配置文件"""
        if name not in self.profiles:
            raise ValueError(f"Profile '{name}' not found")
        
        self.config["default_profile"] = name
        self.save_config()
        logger.info(f"Set default profile: {name}")
    
    def test_profile(self, name: str) -> Dict[str, Any]:
        """测试配置文件"""
        try:
            provider = self.create_provider(name)
            available = provider.is_available()
            
            if available:
                # 尝试生成测试响应
                try:
                    test_response = provider.generate("Hello", max_tokens=10)
                    return {
                        "success": True,
                        "available": True,
                        "test_response": test_response[:50] + "..." if len(test_response) > 50 else test_response
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "available": True,
                        "error": f"Generation test failed: {e}"
                    }
            else:
                return {
                    "success": False,
                    "available": False,
                    "error": "Provider not available"
                }
                
        except Exception as e:
            return {
                "success": False,
                "available": False,
                "error": f"Failed to create provider: {e}"
            }
    
    def export_config(self, file_path: Path):
        """导出配置到文件"""
        export_data = {
            "config": self.config,
            "profiles": self.profiles
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(export_data, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"Configuration exported to: {file_path}")
    
    _ALLOWED_CONFIG_KEYS = {"default_profile", "fallback_profiles", "auto_fallback"}
    _ALLOWED_PROFILE_KEYS = {
        "provider_type", "model", "api_key", "api_base",
        "description", "custom_config", "timeout", "max_retries"
    }

    def import_config(self, file_path: Path):
        """从文件导入配置"""
        with open(file_path, 'r', encoding='utf-8') as f:
            import_data = yaml.safe_load(f)
        
        if "config" in import_data:
            filtered_config = {k: v for k, v in import_data["config"].items() if k in self._ALLOWED_CONFIG_KEYS}
            self.config.update(filtered_config)
            self.save_config()
        
        if "profiles" in import_data:
            for name, profile in import_data["profiles"].items():
                if not isinstance(profile, dict):
                    continue
                filtered_profile = {k: v for k, v in profile.items() if k in self._ALLOWED_PROFILE_KEYS}
                self.profiles[name] = filtered_profile
            self.save_profiles()
        
        logger.info(f"Configuration imported from: {file_path}")