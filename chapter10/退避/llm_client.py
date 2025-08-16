"""
LLMクライアント
複数のLLMプロバイダーに対応した統一インターフェース
"""

import os
import json
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib

# 環境変数の読み込み
load_dotenv()

logger = logging.getLogger(__name__)

class LLMResponse:
    """LLMレスポンスの統一フォーマット"""
    def __init__(self, content: str, usage: Dict[str, int] = None, model: str = None):
        self.content = content
        self.usage = usage or {}
        self.model = model
        self.timestamp = datetime.now()

class BaseLLMClient(ABC):
    """LLMクライアントの基底クラス"""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.cache = {}
        self.cache_ttl = int(os.getenv("CACHE_TTL_SECONDS", 3600))
        self.enable_cache = os.getenv("ENABLE_CACHE", "true").lower() == "true"
        
    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """プロンプトを実行して結果を返す"""
        pass
    
    def _get_cache_key(self, prompt: str, **kwargs) -> str:
        """キャッシュキーを生成"""
        cache_data = f"{prompt}{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[LLMResponse]:
        """キャッシュから取得"""
        if not self.enable_cache:
            return None
            
        if key in self.cache:
            response, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                logger.info("[CACHE] Using cached response")
                return response
        return None
    
    def _save_to_cache(self, key: str, response: LLMResponse):
        """キャッシュに保存"""
        if self.enable_cache:
            self.cache[key] = (response, datetime.now())

class OpenAIClient(BaseLLMClient):
    """OpenAI APIクライアント"""
    
    def __init__(self, api_key: str = None, model: str = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        super().__init__(api_key, model)
        
        # OpenAIクライアントの初期化
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("Please install openai: pip install openai")
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """OpenAI APIでプロンプトを実行"""
        
        # キャッシュチェック
        cache_key = self._get_cache_key(prompt, **kwargs)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            # システムプロンプトとユーザープロンプトを分離
            system_prompt = kwargs.get("system", "You are a helpful AI assistant.")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=kwargs.get("max_tokens", 1000),
                temperature=kwargs.get("temperature", 0.7),
            )
            
            result = LLMResponse(
                content=response.choices[0].message.content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                model=self.model
            )
            
            # キャッシュに保存
            self._save_to_cache(cache_key, result)
            
            logger.info(f"[LLM] OpenAI response: {result.usage['total_tokens']} tokens")
            return result
            
        except Exception as e:
            logger.error(f"[ERROR] OpenAI API error: {e}")
            raise

class AnthropicClient(BaseLLMClient):
    """Anthropic Claude APIクライアント"""
    
    def __init__(self, api_key: str = None, model: str = None):
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        model = model or os.getenv("LLM_MODEL", "claude-3-haiku-20240307")
        super().__init__(api_key, model)
        
        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("Please install anthropic: pip install anthropic")
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Anthropic APIでプロンプトを実行"""
        
        cache_key = self._get_cache_key(prompt, **kwargs)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            system_prompt = kwargs.get("system", "You are a helpful AI assistant.")
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1000),
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            result = LLMResponse(
                content=response.content[0].text,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                },
                model=self.model
            )
            
            self._save_to_cache(cache_key, result)
            
            logger.info(f"[LLM] Anthropic response: {result.usage['total_tokens']} tokens")
            return result
            
        except Exception as e:
            logger.error(f"[ERROR] Anthropic API error: {e}")
            raise

class GoogleClient(BaseLLMClient):
    """Google Gemini APIクライアント"""
    
    def __init__(self, api_key: str = None, model: str = None):
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        model = model or os.getenv("LLM_MODEL", "gemini-pro")
        super().__init__(api_key, model)
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
        except ImportError:
            raise ImportError("Please install google-generativeai: pip install google-generativeai")
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Google Gemini APIでプロンプトを実行"""
        
        cache_key = self._get_cache_key(prompt, **kwargs)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            # Geminiは非同期をサポートしていないため、同期的に実行
            system_prompt = kwargs.get("system", "")
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            
            response = self.client.generate_content(full_prompt)
            
            result = LLMResponse(
                content=response.text,
                usage={
                    "total_tokens": len(full_prompt.split()) + len(response.text.split())
                },
                model=self.model
            )
            
            self._save_to_cache(cache_key, result)
            
            logger.info(f"[LLM] Google Gemini response received")
            return result
            
        except Exception as e:
            logger.error(f"[ERROR] Google API error: {e}")
            raise

class LLMClientFactory:
    """LLMクライアントのファクトリー"""
    
    @staticmethod
    def create(provider: str = None) -> BaseLLMClient:
        """指定されたプロバイダーのクライアントを作成"""
        
        provider = provider or os.getenv("LLM_PROVIDER", "openai")
        
        if provider.lower() == "openai":
            return OpenAIClient()
        elif provider.lower() == "anthropic":
            return AnthropicClient()
        elif provider.lower() == "google":
            return GoogleClient()
        else:
            raise ValueError(f"Unknown provider: {provider}")

# グローバルLLMクライアント
_llm_client = None

def get_llm_client() -> BaseLLMClient:
    """シングルトンLLMクライアントを取得"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClientFactory.create()
    return _llm_client

# 使用例とテスト
async def test_llm():
    """LLMクライアントのテスト"""
    
    client = get_llm_client()
    
    # シンプルな質問
    response = await client.complete(
        "What is MCP (Model Context Protocol)?",
        system="Answer in 2-3 sentences."
    )
    
    print(f"Response: {response.content}")
    print(f"Tokens used: {response.usage}")
    print(f"Model: {response.model}")
    
    # タスク分解の例
    task_prompt = """
    Task: Analyze sales data and create a report
    Available tools: database_query, data_analyzer, report_generator
    
    Break this task into specific steps. Output as JSON array.
    """
    
    response = await client.complete(task_prompt)
    print(f"\nTask breakdown: {response.content}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm())