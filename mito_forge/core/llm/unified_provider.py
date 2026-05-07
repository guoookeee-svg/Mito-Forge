"""
统一模型提供者
支持多种 API 兼容的模型服务，包括 OpenAI、Azure、Claude、本地模型等
"""

import os
import json
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import ipaddress
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .provider import ModelProvider
from ...utils.logging import get_logger

logger = get_logger(__name__)

_BLOCKED_NETWORKS = None

def _get_blocked_networks():
    global _BLOCKED_NETWORKS
    if _BLOCKED_NETWORKS is not None:
        return _BLOCKED_NETWORKS
    nets = []
    for cidr in [
        "169.254.0.0/16",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "0.0.0.0/8",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ]:
        try:
            nets.append(ipaddress.ip_network(cidr))
        except Exception:
            pass
    _BLOCKED_NETWORKS = nets
    return nets


def _validate_api_base(url: str) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Invalid API base URL: {url}")
    allow_internal = os.getenv("MITO_ALLOW_INTERNAL_API", "").lower() in ("1", "true", "yes")
    if allow_internal:
        return url
    if hostname in ("localhost", "127.0.0.1", "::1"):
        return url
    try:
        resolved_ips = __import__('socket').getaddrinfo(hostname, parsed.port)
        for family, type_, proto, canonname, sockaddr in resolved_ips:
            ip = ipaddress.ip_address(sockaddr[0])
            for net in _get_blocked_networks():
                if ip in net:
                    raise ValueError(
                        f"API base URL resolves to internal address {ip} ({net}). "
                        f"Set MITO_ALLOW_INTERNAL_API=1 to allow."
                    )
    except ValueError:
        raise
    except Exception:
        pass
    return url

class UnifiedProvider(ModelProvider):
    """统一模型提供者，支持多种 API 格式"""
    
    # 预定义的模型配置
    PRESET_CONFIGS = {
        # OpenAI 官方
        "openai": {
            "api_base": "https://api.openai.com/v1",
            "api_format": "openai",
            "default_model": "gpt-4o-mini",
            "auth_header": "Authorization",
            "auth_prefix": "Bearer"
        },
        
        # Azure OpenAI
        "azure": {
            "api_base": "https://{resource}.openai.azure.com",
            "api_format": "azure",
            "default_model": "gpt-4",
            "auth_header": "api-key",
            "auth_prefix": ""
        },
        
        # Anthropic Claude
        "anthropic": {
            "api_base": "https://api.anthropic.com/v1",
            "api_format": "anthropic",
            "default_model": "claude-3-sonnet-20240229",
            "auth_header": "x-api-key",
            "auth_prefix": ""
        },
        
        # 本地 Ollama
        "ollama": {
            "api_base": "http://localhost:11434",
            "api_format": "ollama",
            "default_model": "qwen2.5:7b",
            "auth_header": None,
            "auth_prefix": ""
        },
        
        # 通用 OpenAI 兼容 API
        "openai_compatible": {
            "api_base": "http://localhost:8000/v1",
            "api_format": "openai",
            "default_model": "gpt-3.5-turbo",
            "auth_header": "Authorization",
            "auth_prefix": "Bearer"
        },
        
        # 国内 API 服务商示例
        "zhipu": {
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "api_format": "openai",
            "default_model": "glm-4",
            "auth_header": "Authorization",
            "auth_prefix": "Bearer"
        },
        
        "moonshot": {
            "api_base": "https://api.moonshot.cn/v1",
            "api_format": "openai", 
            "default_model": "moonshot-v1-8k",
            "auth_header": "Authorization",
            "auth_prefix": "Bearer"
        },
        
        "deepseek": {
            "api_base": "https://api.deepseek.com/v1",
            "api_format": "openai",
            "default_model": "deepseek-chat",
            "auth_header": "Authorization", 
            "auth_prefix": "Bearer"
        }
    }
    
    def __init__(
        self,
        provider_type: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None,
        timeout: int = 60,
        max_retries: int = 3,
        **kwargs
    ):
        """
        初始化统一模型提供者
        
        Args:
            provider_type: 提供者类型 (openai, azure, anthropic, ollama, etc.)
            model: 模型名称
            api_key: API 密钥
            api_base: API 基础 URL
            custom_config: 自定义配置
            timeout: 请求超时时间
            max_retries: 最大重试次数
        """
        # 获取预设配置
        if provider_type in self.PRESET_CONFIGS:
            self.config = self.PRESET_CONFIGS[provider_type].copy()
        else:
            # 如果不是预设类型，使用 OpenAI 兼容格式作为默认
            self.config = self.PRESET_CONFIGS["openai_compatible"].copy()
        
        # 应用自定义配置
        if custom_config:
            self.config.update(custom_config)
        
        # 设置参数
        self.provider_type = provider_type
        self.model = model or self.config["default_model"]
        self.api_key = api_key or self._get_api_key_from_env()
        raw_api_base = (api_base or self.config["api_base"]).rstrip("/")
        self.api_base = _validate_api_base(raw_api_base)
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 保存配置，因为父类 __init__ 会重置 self.config
        saved_config = self.config.copy()
        super().__init__(self.model, **kwargs)
        self.config = saved_config
        
        # 设置 HTTP 会话
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _get_api_key_from_env(self) -> Optional[str]:
        """从环境变量获取 API 密钥"""
        env_keys = [
            f"{self.provider_type.upper()}_API_KEY",
            "OPENAI_API_KEY",  # 通用回退
            "API_KEY"
        ]
        
        for key in env_keys:
            value = os.getenv(key)
            if value:
                return value
        
        return None
    
    def generate(self, prompt: str, *, system: Optional[str] = None, **kwargs) -> str:
        """生成文本响应"""
        api_format = self.config["api_format"]
        
        if api_format == "openai":
            return self._generate_openai_format(prompt, system=system, **kwargs)
        elif api_format == "anthropic":
            return self._generate_anthropic_format(prompt, system=system, **kwargs)
        elif api_format == "ollama":
            return self._generate_ollama_format(prompt, system=system, **kwargs)
        elif api_format == "azure":
            return self._generate_azure_format(prompt, system=system, **kwargs)
        else:
            raise ValueError(f"Unsupported API format: {api_format}")
    
    def _generate_openai_format(self, prompt: str, *, system: Optional[str] = None, **kwargs) -> str:
        """OpenAI 格式 API 调用"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.2),
            "max_tokens": kwargs.get("max_tokens", 4000),
            "top_p": kwargs.get("top_p", 1.0),
            "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
            "presence_penalty": kwargs.get("presence_penalty", 0.0),
        }
        
        # JSON 模式支持
        if kwargs.get("response_format") == "json":
            payload["response_format"] = {"type": "json_object"}
        
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.config["auth_header"]:
            auth_value = f"{self.config['auth_prefix']} {self.api_key}".strip()
            headers[self.config["auth_header"]] = auth_value
        
        return self._make_request(f"{self.api_base}/chat/completions", payload, headers)
    
    def _generate_anthropic_format(self, prompt: str, *, system: Optional[str] = None, **kwargs) -> str:
        """Anthropic Claude 格式 API 调用"""
        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 4000),
            "temperature": kwargs.get("temperature", 0.2),
            "messages": [{"role": "user", "content": prompt}]
        }
        
        if system:
            payload["system"] = system
        
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        if self.api_key:
            headers["x-api-key"] = self.api_key
        
        response = self._make_request(f"{self.api_base}/messages", payload, headers, response_key="content")
        
        # Anthropic 返回格式特殊处理
        if isinstance(response, list) and len(response) > 0:
            return response[0].get("text", "")
        return str(response)
    
    def _generate_ollama_format(self, prompt: str, *, system: Optional[str] = None, **kwargs) -> str:
        """Ollama 格式 API 调用"""
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "top_p": kwargs.get("top_p", 0.9),
                "num_predict": kwargs.get("max_tokens", 4000),
            }
        }
        
        headers = {"Content-Type": "application/json"}
        
        return self._make_request(f"{self.api_base}/api/generate", payload, headers, response_key="response")
    
    def _generate_azure_format(self, prompt: str, *, system: Optional[str] = None, **kwargs) -> str:
        """Azure OpenAI 格式 API 调用"""
        # Azure 使用 OpenAI 格式，但 URL 结构不同
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.2),
            "max_tokens": kwargs.get("max_tokens", 4000),
        }
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        
        # Azure URL 格式: /openai/deployments/{model}/chat/completions?api-version=2023-12-01-preview
        url = f"{self.api_base}/openai/deployments/{self.model}/chat/completions"
        params = {"api-version": "2023-12-01-preview"}
        
        return self._make_request(url, payload, headers, params=params)
    
    def _make_request(
        self, 
        url: str, 
        payload: Dict[str, Any], 
        headers: Dict[str, str],
        params: Optional[Dict[str, str]] = None,
        response_key: str = "choices"
    ) -> str:
        """发送 HTTP 请求并处理响应"""
        try:
            logger.debug(f"Calling API: {url}")
            start_time = time.time()
            
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            
            elapsed_time = time.time() - start_time
            logger.debug(f"API call completed in {elapsed_time:.2f}s")
            
            response.raise_for_status()
            result = response.json()
            
            # 根据不同的响应格式提取内容
            if response_key == "choices":
                # OpenAI 格式
                if "choices" not in result or not result["choices"]:
                    raise ValueError("Invalid response format")
                return result["choices"][0]["message"]["content"]
            
            elif response_key == "content":
                # Anthropic 格式
                return result.get("content", "")
            
            elif response_key == "response":
                # Ollama 格式
                return result.get("response", "")
            
            else:
                # 直接返回结果
                return str(result)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling API: {e}")
            raise
    
    def is_available(self) -> bool:
        """检查提供者是否可用"""
        # Ollama 不需要 API 密钥
        if self.provider_type == "ollama":
            return self._test_ollama_connection()
        
        # 其他提供者需要 API 密钥
        if not self.api_key:
            return False
        
        return self._test_api_connection()
    
    def _test_ollama_connection(self) -> bool:
        """测试 Ollama 连接"""
        try:
            response = self.session.get(f"{self.api_base}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _test_api_connection(self) -> bool:
        """测试 API 连接"""
        try:
            # 发送最小测试请求
            test_response = self.generate("test", max_tokens=1, temperature=0)
            return bool(test_response)
        except Exception:
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = super().get_model_info()
        info.update({
            "provider_type": self.provider_type,
            "api_base": self.api_base,
            "api_format": self.config["api_format"],
            "has_api_key": bool(self.api_key),
            "timeout": self.timeout,
            "available": self.is_available()
        })
        return info
    
    @classmethod
    def get_preset_configs(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有预设配置"""
        return cls.PRESET_CONFIGS.copy()
    
    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> "UnifiedProvider":
        """从配置字典创建提供者实例"""
        return cls(
            provider_type=config.get("provider_type", "openai"),
            model=config.get("model"),
            api_key=config.get("api_key"),
            api_base=config.get("api_base"),
            custom_config=config.get("custom_config"),
            timeout=config.get("timeout", 60),
            max_retries=config.get("max_retries", 3)
        )