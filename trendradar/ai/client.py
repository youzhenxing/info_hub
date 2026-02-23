# coding=utf-8
"""
AI 客户端模块

基于 LiteLLM 的统一 AI 模型接口
支持 100+ AI 提供商（OpenAI、DeepSeek、Gemini、Claude、国内模型等）
"""

import os
from typing import Any, Dict, List, Optional

from litellm import completion


class AIClient:
    """统一的 AI 客户端（基于 LiteLLM）"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化 AI 客户端

        Args:
            config: AI 配置字典
                - MODEL: 模型标识（格式: provider/model_name）
                - API_KEY: API 密钥
                - API_BASE: API 基础 URL（可选）
                - TEMPERATURE: 采样温度
                - MAX_TOKENS: 最大生成 token 数
                - TIMEOUT: 请求超时时间（秒）
                - NUM_RETRIES: 重试次数（可选）
                - FALLBACK_MODELS: 备用模型列表（可选）
        """
        # 支持大写和小写 key（优先大写，兼容小写）
        self.model = config.get("MODEL") or config.get("model", "deepseek/deepseek-chat")
        self.api_key = config.get("API_KEY") or config.get("api_key") or os.environ.get("AI_API_KEY", "")
        self.api_base = config.get("API_BASE") or config.get("api_base", "")
        self.temperature = config.get("TEMPERATURE") or config.get("temperature", 1.0)
        self.max_tokens = config.get("MAX_TOKENS") or config.get("max_tokens", 160000)
        self.timeout = config.get("TIMEOUT") or config.get("timeout", 900)
        self.num_retries = config.get("NUM_RETRIES") or config.get("num_retries", 2)
        self.fallback_models = config.get("FALLBACK_MODELS") or config.get("fallback_models", [])

    def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        调用 AI 模型进行对话

        Args:
            messages: 消息列表，格式: [{"role": "system/user/assistant", "content": "..."}]
            **kwargs: 额外参数，会覆盖默认配置

        Returns:
            str: AI 响应内容

        Raises:
            Exception: API 调用失败时抛出异常
        """
        # 处理模型名称
        # 当使用自定义 api_base 且模型名以 openai/ 开头时，
        # 需要将 openai/ 去掉作为实际模型名，并强制使用 OpenAI 协议
        model_name = self.model
        custom_llm_provider = None
        
        if self.api_base and model_name.startswith("openai/"):
            # 去掉 openai/ 前缀，使用实际模型名
            model_name = model_name[7:]  # 去掉 "openai/"
            custom_llm_provider = "openai"
        
        # 构建请求参数
        params = {
            "model": model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "timeout": kwargs.get("timeout", self.timeout),
            "num_retries": kwargs.get("num_retries", self.num_retries),
        }

        # 调试：打印传递给 LiteLLM 的 timeout
        if 'timeout' in kwargs:
            print(f"[AIClient-DEBUG] kwargs contains timeout={kwargs['timeout']}, will override self.timeout={self.timeout}")
        else:
            print(f"[AIClient-DEBUG] No timeout in kwargs, using self.timeout={self.timeout}")
        print(f"[AIClient-DEBUG] Final timeout passed to LiteLLM: {params.get('timeout')} (model={model_name[:30]}...)")
        
        # 强制使用 OpenAI 协议（当有自定义 api_base 时）
        if custom_llm_provider:
            params["custom_llm_provider"] = custom_llm_provider

        # 添加 API Key
        if self.api_key:
            params["api_key"] = self.api_key

        # 添加 API Base（如果配置了）
        if self.api_base:
            params["api_base"] = self.api_base

        # 添加 max_tokens（如果配置了且不为 0）
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens and max_tokens > 0:
            params["max_tokens"] = max_tokens

        # 添加 fallback 模型（如果配置了）
        if self.fallback_models:
            params["fallbacks"] = self.fallback_models

        # 提取 extra_body 参数（用于传递提供商特定的参数）
        extra_body = kwargs.pop("extra_body", None)

        # 合并其他额外参数（排除 extra_body 和 timeout）
        for key, value in kwargs.items():
            if key not in params and key not in ["extra_body", "timeout"]:
                params[key] = value

        # 调用 LiteLLM
        # 如果有 extra_body，将其添加到参数中
        if extra_body:
            params["extra_body"] = extra_body
        # 禁用代理：AI API（api.siliconflow.cn）不需要代理，直连访问
        # 保存当前环境变量
        old_env = {}
        proxy_vars = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]

        for var in proxy_vars:
            if var in os.environ:
                old_env[var] = os.environ[var]
                del os.environ[var]

        try:
            response = completion(**params)
        finally:
            # 恢复环境变量
            for var, value in old_env.items():
                os.environ[var] = value

        # 提取响应内容
        return response.choices[0].message.content

    def validate_config(self) -> tuple[bool, str]:
        """
        验证配置是否有效

        Returns:
            tuple: (是否有效, 错误信息)
        """
        if not self.model:
            return False, "未配置 AI 模型（model）"

        if not self.api_key:
            return False, "未配置 AI API Key，请在 config.yaml 或环境变量 AI_API_KEY 中设置"

        # 验证模型格式（应该包含 provider/model）
        if "/" not in self.model:
            return False, f"模型格式错误: {self.model}，应为 'provider/model' 格式（如 'deepseek/deepseek-chat'）"

        return True, ""
