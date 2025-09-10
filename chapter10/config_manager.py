#!/usr/bin/env python3
"""
Configuration management for MCP Agent
設定管理モジュール
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from utils import Logger


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
class InterruptHandlingConfig:
    """中断処理設定"""
    timeout: float = 10.0
    non_interactive_default: str = "abort"


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
    interrupt_handling: InterruptHandlingConfig = field(default_factory=InterruptHandlingConfig)


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
    def update_config_value(config: Config, key_path: str, new_value: str) -> None:
        """設定値をドット記法で更新"""
        keys = key_path.split('.')
        target = config
        for key in keys[:-1]:
            if hasattr(target, key):
                target = getattr(target, key)
            else:
                raise ValueError(f"設定キー '{key_path}' が見つかりません")
        
        final_key = keys[-1]
        if hasattr(target, final_key):
            # 型を自動変換
            current_value = getattr(target, final_key)
            converted_value = ConfigManager._convert_value_type(new_value, type(current_value))
            setattr(target, final_key, converted_value)
        else:
            raise ValueError(f"設定キー '{key_path}' が見つかりません")
    
    @staticmethod
    def get_config_value(config: Config, key_path: str):
        """ドット記法で設定値を取得"""
        keys = key_path.split('.')
        value = config
        for key in keys:
            if hasattr(value, key):
                value = getattr(value, key)
            else:
                return None
        return value
    
    @staticmethod
    def _convert_value_type(value: str, target_type):
        """文字列を指定された型に変換"""
        if target_type == bool:
            if value.lower() in ['true', 'on', 'yes', '1']:
                return True
            elif value.lower() in ['false', 'off', 'no', '0']:
                return False
            else:
                raise ValueError(f"bool値として解釈できません: {value}")
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        else:
            return value
    
    @staticmethod
    def get_all_config_keys(config: Config, prefix=""):
        """すべての設定キーを取得（ドット記法）"""
        keys = []
        for attr_name in dir(config):
            if not attr_name.startswith('_'):
                attr_value = getattr(config, attr_name)
                full_key = f"{prefix}.{attr_name}" if prefix else attr_name
                
                # データクラスの場合は再帰的に探索
                if hasattr(attr_value, '__dataclass_fields__'):
                    keys.extend(ConfigManager.get_all_config_keys(attr_value, full_key))
                else:
                    keys.append(full_key)
        return keys
    
    @staticmethod
    def save_config_to_file(config: Config, config_path: str = "config.yaml") -> bool:
        """設定をファイルに保存（コメント保持）"""
        try:
            # ruamel.yamlでコメント保持保存を試行
            return ConfigManager._save_config_with_comments(config, config_path)
        except ImportError:
            # ruamel.yamlがない場合は従来の方法にフォールバック
            Logger().ulog("ruamel.yaml not available, using standard yaml (comments will be lost)", "info:config")
            return ConfigManager._save_config_simple(config, config_path)
        except Exception as e:
            Logger().ulog(f"コメント保持保存に失敗: {e}", "warning:config")
            # フォールバックを試行
            return ConfigManager._save_config_simple(config, config_path)
    
    @staticmethod
    def _save_config_with_comments(config: Config, config_path: str) -> bool:
        """ruamel.yamlを使ってコメントを保持して保存"""
        from ruamel.yaml import YAML
        
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.width = 4096  # 行幅制限を大きく
        yaml.map_indent = 2
        yaml.sequence_indent = 4
        
        # 既存のconfig.yamlを読み込み（コメント保持）
        if not os.path.exists(config_path):
            # ファイルが存在しない場合は従来の方法で作成
            return ConfigManager._save_config_simple(config, config_path)
        
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.load(f)
        
        # 現在の設定値でYAMLデータを更新（構造とコメントは保持）
        ConfigManager._update_yaml_values(config_data, config)
        
        # コメントを保持して書き込み
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)
        
        return True
    
    @staticmethod
    def _save_config_simple(config: Config, config_path: str) -> bool:
        """標準yamlライブラリで保存（コメントは失われる）"""
        import yaml
        
        # 現在の設定をdict形式に変換
        config_dict = ConfigManager._config_to_dict(config)
        
        # config.yamlに書き込み
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, allow_unicode=True, default_flow_style=False, indent=2)
            
        return True
    
    @staticmethod
    def _config_to_dict(config: Config) -> dict:
        """Config オブジェクトを辞書に変換"""
        result = {}
        
        # 各セクションを辞書に変換
        sections = {
            'display': config.display,
            'execution': config.execution,
            'llm': config.llm,
            'conversation': config.conversation,
            'error_handling': config.error_handling,
            'development': config.development,
            'result_display': config.result_display
        }
        
        for section_name, section_obj in sections.items():
            result[section_name] = {}
            
            # 各属性を辞書にコピー
            for attr_name in dir(section_obj):
                if not attr_name.startswith('_'):
                    value = getattr(section_obj, attr_name)
                    
                    # ネストしたオブジェクトの場合は再帰的に変換
                    if hasattr(value, '__dataclass_fields__'):
                        result[section_name][attr_name] = {}
                        for nested_attr in dir(value):
                            if not nested_attr.startswith('_'):
                                nested_value = getattr(value, nested_attr)
                                result[section_name][attr_name][nested_attr] = nested_value
                    else:
                        result[section_name][attr_name] = value
        
        return result
    
    @staticmethod
    def _update_yaml_values(yaml_data, config):
        """YAMLデータの値部分のみを更新（構造とコメントは保持）"""
        # 安全にキーが存在することを確認して更新
        if 'display' in yaml_data:
            if hasattr(config.display, 'ui_mode'):
                yaml_data['display']['ui_mode'] = config.display.ui_mode
            if hasattr(config.display, 'show_timing'):
                yaml_data['display']['show_timing'] = config.display.show_timing
            if hasattr(config.display, 'show_thinking'):
                yaml_data['display']['show_thinking'] = config.display.show_thinking
        
        if 'development' in yaml_data:
            if hasattr(config.development, 'verbose'):
                yaml_data['development']['verbose'] = config.development.verbose
            if hasattr(config.development, 'log_level'):
                # log_levelがYAMLに存在しない場合は追加
                if 'log_level' not in yaml_data['development']:
                    yaml_data['development']['log_level'] = config.development.log_level
                else:
                    yaml_data['development']['log_level'] = config.development.log_level
            if hasattr(config.development, 'show_api_calls'):
                yaml_data['development']['show_api_calls'] = config.development.show_api_calls
        
        if 'llm' in yaml_data:
            if hasattr(config.llm, 'model'):
                yaml_data['llm']['model'] = config.llm.model
            if hasattr(config.llm, 'temperature'):
                yaml_data['llm']['temperature'] = config.llm.temperature
            if hasattr(config.llm, 'force_json'):
                yaml_data['llm']['force_json'] = config.llm.force_json
            if hasattr(config.llm, 'reasoning_effort'):
                yaml_data['llm']['reasoning_effort'] = config.llm.reasoning_effort
            if hasattr(config.llm, 'max_completion_tokens'):
                yaml_data['llm']['max_completion_tokens'] = config.llm.max_completion_tokens
        
        if 'execution' in yaml_data:
            if hasattr(config.execution, 'max_retries'):
                yaml_data['execution']['max_retries'] = config.execution.max_retries
            if hasattr(config.execution, 'timeout_seconds'):
                yaml_data['execution']['timeout_seconds'] = config.execution.timeout_seconds
            if hasattr(config.execution, 'fallback_enabled'):
                # fallback_enabledがYAMLに存在しない場合は追加
                if 'fallback_enabled' not in yaml_data['execution']:
                    yaml_data['execution']['fallback_enabled'] = config.execution.fallback_enabled
                else:
                    yaml_data['execution']['fallback_enabled'] = config.execution.fallback_enabled
            if hasattr(config.execution, 'max_tasks'):
                # max_tasksがYAMLに存在しない場合は追加
                if 'max_tasks' not in yaml_data['execution']:
                    yaml_data['execution']['max_tasks'] = config.execution.max_tasks
                else:
                    yaml_data['execution']['max_tasks'] = config.execution.max_tasks
            
            # ネストしたretry_strategy
            if 'retry_strategy' in yaml_data['execution'] and hasattr(config.execution, 'retry_strategy'):
                rs = config.execution.retry_strategy
                yaml_data['execution']['retry_strategy']['max_retries'] = rs.max_retries
                yaml_data['execution']['retry_strategy']['progressive_temperature'] = rs.progressive_temperature
                yaml_data['execution']['retry_strategy']['initial_temperature'] = rs.initial_temperature
                yaml_data['execution']['retry_strategy']['temperature_increment'] = rs.temperature_increment
        
        if 'conversation' in yaml_data:
            if hasattr(config.conversation, 'context_limit'):
                yaml_data['conversation']['context_limit'] = config.conversation.context_limit
            if hasattr(config.conversation, 'max_history'):
                yaml_data['conversation']['max_history'] = config.conversation.max_history
        
        if 'error_handling' in yaml_data:
            if hasattr(config.error_handling, 'auto_correct_params'):
                yaml_data['error_handling']['auto_correct_params'] = config.error_handling.auto_correct_params
            if hasattr(config.error_handling, 'retry_interval'):
                yaml_data['error_handling']['retry_interval'] = config.error_handling.retry_interval
        
        if 'result_display' in yaml_data:
            if hasattr(config.result_display, 'max_result_length'):
                yaml_data['result_display']['max_result_length'] = config.result_display.max_result_length
            if hasattr(config.result_display, 'show_truncated_info'):
                yaml_data['result_display']['show_truncated_info'] = config.result_display.show_truncated_info
    
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