"""
AI 客户端 - 基于 LiteLLM 的轻量封装
"""

import logging
import os
from typing import Optional, List, Dict, Any

try:
    import litellm
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

from .config_loader import AIConfig

logger = logging.getLogger(__name__)


class AIClient:
    """AI 客户端"""
    
    def __init__(self, config: AIConfig):
        if not LITELLM_AVAILABLE:
            raise ImportError("litellm 未安装，请运行: pip install litellm")
        
        self.config = config
        self._setup_litellm()
    
    def _setup_litellm(self):
        """配置 LiteLLM"""
        # 禁用 LiteLLM 的日志输出
        litellm.set_verbose = False
        
        # 设置 API Key
        if self.config.api_key:
            # 根据模型提供商设置对应的 API Key
            if self.config.model.startswith('deepseek/'):
                litellm.api_key = self.config.api_key
            elif self.config.model.startswith('openai/'):
                litellm.openai_key = self.config.api_key
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,  # 新增：允许覆盖模型
        timeout: Optional[int] = None,  # 新增：允许覆盖超时
        extra_body: Optional[Dict[str, Any]] = None  # 新增：Thinking模式等
    ) -> str:
        """
        调用 AI 聊天接口

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 采样温度（可选）
            max_tokens: 最大 token 数（可选）
            model: 覆盖默认模型（可选）
            timeout: 覆盖默认超时（可选）
            extra_body: 额外请求参数（可选，用于 Thinking 模式等）

        Returns:
            AI 回复内容
        """
        try:
            # 构建请求参数（支持参数覆盖）
            kwargs: Dict[str, Any] = {
                "model": model or self.config.model,  # 优先使用传入的model
                "messages": messages,
                "timeout": timeout or self.config.timeout,  # 优先使用传入的timeout
                "temperature": temperature or self.config.temperature,
            }

            # 设置 max_tokens
            max_tok = max_tokens or self.config.max_tokens
            if max_tok > 0:
                kwargs["max_tokens"] = max_tok

            # 设置 API Key（对于使用 openai/ 前缀的模型必须设置）
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key

            # 设置自定义 API Base
            if self.config.api_base:
                kwargs["api_base"] = self.config.api_base

            # 处理 extra_body 参数（用于 Thinking 模式等）
            if extra_body:
                kwargs.update(extra_body)

            logger.debug(f"调用 AI: model={kwargs['model']}, timeout={kwargs['timeout']}")

            # 禁用代理：AI API 不需要代理，直连访问
            # 保存当前环境变量
            old_env = {}
            proxy_vars = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]

            for var in proxy_vars:
                if var in os.environ:
                    old_env[var] = os.environ[var]
                    del os.environ[var]

            try:
                # 调用 LiteLLM
                response = completion(**kwargs)
            finally:
                # 恢复环境变量
                for var, value in old_env.items():
                    os.environ[var] = value

            # 提取回复内容
            content = response.choices[0].message.content
            
            logger.debug(f"AI 响应长度: {len(content)} 字符")
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"AI 调用失败: {e}")
            raise
    
    def summarize(self, text: str, prompt_template: str) -> str:
        """
        生成文本摘要
        
        Args:
            text: 待总结的文本
            prompt_template: 提示词模板（包含 {content} 占位符）
        
        Returns:
            摘要内容
        """
        prompt = prompt_template.replace("{content}", text)
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages)
    
    def analyze_topics(self, articles_text: str, prompt_template: str) -> str:
        """
        话题聚合分析（使用默认模型）

        Args:
            articles_text: 多篇文章的组合文本
            prompt_template: 提示词模板（包含 {content} 占位符）

        Returns:
            话题分析结果
        """
        prompt = prompt_template.replace("{content}", articles_text)
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, temperature=0.5)  # 降低温度，提高一致性

    def analyze_topics_with_thinking(self, articles_text: str, prompt_template: str) -> str:
        """
        话题聚合分析（使用 DeepSeek-V3.2 + Thinking 模式）

        专门用于处理大量文章的话题聚合任务，与单篇摘要分离：
        - 单篇摘要使用：deepseek-ai/DeepSeek-R1-0528-Qwen3-8B（快速）
        - 话题聚合使用：deepseek-ai/DeepSeek-V3.2 + Thinking（大输出）
        - 超时时间 30 分钟（1800秒）
        - 最大输出 64K tokens

        Args:
            articles_text: 多篇文章的组合文本
            prompt_template: 提示词模板（包含 {content} 占位符）

        Returns:
            话题分析结果
        """
        prompt = prompt_template.replace("{content}", articles_text)
        messages = [{"role": "user", "content": prompt}]

        return self.chat(
            messages,
            temperature=0.5,
            model="openai/deepseek-ai/DeepSeek-V3.2",  # 新模型（与播客一致，需添加 openai/ 前缀）
            timeout=1800,  # 30分钟超时
            max_tokens=64000,  # Thinking模式支持
            extra_body={"enable_thinking": True}  # 启用Thinking模式
        )
