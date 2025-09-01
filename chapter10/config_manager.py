#!/usr/bin/env python3
"""
Configuration management for MCP Agent
設定管理モジュール
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class DisplayConfig:
    """表示設定"""
    ui_mode: str = "basic"
    show_timing: bool = True
    show_thinking: bool = True


@dataclass
class RetryStrategyConfig:
    """リトライ戦略設定"""
    max_retries: int = 3
    progressive_temperature: bool = True
    initial_temperature: float = 0.1
    temperature_increment: float = 0.2


@dataclass
class ExecutionConfig:
    """実行設定"""
    max_retries: int = 3
    timeout_seconds: int = 30
    fallback_enabled: bool = False
    max_tasks: int = 10
    retry_strategy: RetryStrategyConfig = field(default_factory=RetryStrategyConfig)


@dataclass
class LLMConfig:
    """LLM設定"""
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    force_json: bool = True
    reasoning_effort: str = "minimal"
    max_completion_tokens: int = 5000


@dataclass
class ConversationConfig:
    """会話設定"""
    context_limit: int = 10
    max_history: int = 50


@dataclass
class ErrorHandlingConfig:
    """エラー対処設定"""
    auto_correct_params: bool = True
    retry_interval: float = 1.0


@dataclass
class DevelopmentConfig:
    """開発設定"""
    verbose: bool = True
    log_level: str = "INFO"
    show_api_calls: bool = True


@dataclass
class ResultDisplayConfig:
    """結果表示設定"""
    max_result_length: int = 1000
    show_truncated_info: bool = True


@dataclass
class Config:
    """統一設定クラス"""
    display: DisplayConfig = field(default_factory=DisplayConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    error_handling: ErrorHandlingConfig = field(default_factory=ErrorHandlingConfig)
    development: DevelopmentConfig = field(default_factory=DevelopmentConfig)
    result_display: ResultDisplayConfig = field(default_factory=ResultDisplayConfig)


class ConfigManager:
    """設定管理クラス"""
    
    @staticmethod
    def load(config_path: str) -> Config:
        """
        設定ファイルを読み込み、型安全な設定オブジェクトを返す
        
        Args:
            config_path: 設定ファイルのパス
            
        Returns:
            Config: 型安全な設定オブジェクト
            
        Raises:
            FileNotFoundError: 設定ファイルが存在しない場合
            ValueError: 設定ファイルの内容が不正な場合
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"設定ファイル '{config_path}' が見つかりません。\n"
                f"'config.sample.yaml' を '{config_path}' にコピーしてください。"
            )
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
            
            return ConfigManager._create_config_from_dict(yaml_data)
            
        except yaml.YAMLError as e:
            raise ValueError(f"設定ファイルの解析エラー: {e}")
        except Exception as e:
            raise ValueError(f"設定ファイル読み込みエラー: {e}")
    
    @staticmethod
    def _create_config_from_dict(data: Dict[str, Any]) -> Config:
        """辞書からConfigオブジェクトを作成"""
        config = Config()
        
        # Display設定
        if "display" in data:
            display_data = data["display"]
            config.display = DisplayConfig(
                ui_mode=display_data.get("ui_mode", "basic"),
                show_timing=display_data.get("show_timing", True),
                show_thinking=display_data.get("show_thinking", True)
            )
        
        # Execution設定
        if "execution" in data:
            exec_data = data["execution"]
            retry_data = exec_data.get("retry_strategy", {})
            
            config.execution = ExecutionConfig(
                max_retries=exec_data.get("max_retries", 3),
                timeout_seconds=exec_data.get("timeout_seconds", 30),
                fallback_enabled=exec_data.get("fallback_enabled", False),
                max_tasks=exec_data.get("max_tasks", 10),
                retry_strategy=RetryStrategyConfig(
                    max_retries=retry_data.get("max_retries", 3),
                    progressive_temperature=retry_data.get("progressive_temperature", True),
                    initial_temperature=retry_data.get("initial_temperature", 0.1),
                    temperature_increment=retry_data.get("temperature_increment", 0.2)
                )
            )
        
        # LLM設定
        if "llm" in data:
            llm_data = data["llm"]
            config.llm = LLMConfig(
                model=llm_data.get("model", "gpt-4o-mini"),
                temperature=llm_data.get("temperature", 0.2),
                force_json=llm_data.get("force_json", True),
                reasoning_effort=llm_data.get("reasoning_effort", "minimal"),
                max_completion_tokens=llm_data.get("max_completion_tokens", 5000)
            )
        
        # Conversation設定
        if "conversation" in data:
            conv_data = data["conversation"]
            config.conversation = ConversationConfig(
                context_limit=conv_data.get("context_limit", 10),
                max_history=conv_data.get("max_history", 50)
            )
        
        # ErrorHandling設定
        if "error_handling" in data:
            error_data = data["error_handling"]
            config.error_handling = ErrorHandlingConfig(
                auto_correct_params=error_data.get("auto_correct_params", True),
                retry_interval=error_data.get("retry_interval", 1.0)
            )
        
        # Development設定
        if "development" in data:
            dev_data = data["development"]
            config.development = DevelopmentConfig(
                verbose=dev_data.get("verbose", True),
                log_level=dev_data.get("log_level", "INFO"),
                show_api_calls=dev_data.get("show_api_calls", True)
            )
        
        # ResultDisplay設定
        if "result_display" in data:
            result_data = data["result_display"]
            config.result_display = ResultDisplayConfig(
                max_result_length=result_data.get("max_result_length", 1000),
                show_truncated_info=result_data.get("show_truncated_info", True)
            )
        
        return config
    
    @staticmethod
    def validate_config(config: Config) -> None:
        """設定の妥当性をチェック"""
        
        # UIモードの検証
        valid_ui_modes = ["basic", "rich"]
        if config.display.ui_mode not in valid_ui_modes:
            raise ValueError(f"Invalid ui_mode: {config.display.ui_mode}. Must be one of {valid_ui_modes}")
        
        # LLMモデルの検証
        valid_models = ["gpt-4o-mini", "gpt-5-mini", "gpt-5-nano", "gpt-5"]
        if config.llm.model not in valid_models:
            raise ValueError(f"Invalid model: {config.llm.model}. Must be one of {valid_models}")
        
        # 温度の検証
        if not 0 <= config.llm.temperature <= 2:
            raise ValueError(f"Invalid temperature: {config.llm.temperature}. Must be between 0 and 2")
        
        # 推論レベルの検証
        valid_reasoning = ["minimal", "low", "medium", "high"]
        if config.llm.reasoning_effort not in valid_reasoning:
            raise ValueError(f"Invalid reasoning_effort: {config.llm.reasoning_effort}. Must be one of {valid_reasoning}")
        
        # ログレベルの検証
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if config.development.log_level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log_level: {config.development.log_level}. Must be one of {valid_log_levels}")
        
        # 数値範囲の検証
        if config.execution.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        
        if config.execution.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        
        if config.conversation.context_limit < 0:
            raise ValueError("context_limit must be non-negative")