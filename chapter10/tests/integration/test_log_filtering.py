#!/usr/bin/env python3
"""
Integration tests for log filtering
config.yaml設定とログ出力の統合テスト
"""

import pytest
import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from config_manager import ConfigManager
from display_manager import DisplayManager
from utils import Logger


@pytest.mark.integration
def test_config_log_level_integration():
    """config.yamlのlog_level設定がLoggerに正しく渡されることをテスト"""
    # テスト用config作成
    config_content = """
development:
  verbose: true
  log_level: "INFO"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        config = ConfigManager.load(config_path)
        logger = Logger(
            verbose=config.development.verbose,
            log_level=config.development.log_level
        )
        
        assert logger.verbose is True
        assert logger.log_level == "INFO"
        assert logger.min_priority == 20
    finally:
        Path(config_path).unlink()


@pytest.mark.integration
def test_config_verbose_false_integration():
    """config.yamlのverbose: false設定がLoggerに正しく渡されることをテスト"""
    # テスト用config作成
    config_content = """
development:
  verbose: false
  log_level: "DEBUG"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        config = ConfigManager.load(config_path)
        logger = Logger(
            verbose=config.development.verbose,
            log_level=config.development.log_level
        )
        
        captured_output = io.StringIO()
        with redirect_stdout(captured_output):
            logger.ulog("Debug message", "debug", show_level=True)
            logger.ulog("Info message", "info", show_level=True)
        
        output = captured_output.getvalue()
        assert output == ""  # verbose=Falseなので何も出力されない
    finally:
        Path(config_path).unlink()


@pytest.mark.integration 
def test_display_manager_respects_logger_settings():
    """DisplayManagerがLogger設定を尊重することをテスト"""
    # INFO レベルのlogger
    logger = Logger(verbose=True, log_level="INFO")
    
    # 将来的にDisplayManagerがloggerを受け取るようになったらテスト
    # 現在は直接printしているため、修正後に有効化
    pytest.skip("DisplayManager integration pending - requires Logger integration first")


@pytest.mark.integration
def test_end_to_end_log_filtering():
    """エンドツーエンドのログフィルタリングテスト"""
    # テスト用config作成
    config_content = """
development:
  verbose: true
  log_level: "WARNING"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        config = ConfigManager.load(config_path)
        logger = Logger(
            verbose=config.development.verbose,
            log_level=config.development.log_level
        )
        
        captured_output = io.StringIO()
        with redirect_stdout(captured_output):
            # 各レベルのメッセージを出力
            logger.ulog("Debug message", "debug", show_level=True)  # 出力されない
            logger.ulog("Info message", "info", show_level=True)    # 出力されない  
            logger.ulog("Warning message", "warning", show_level=True)  # 出力される
            logger.ulog("Error message", "error", show_level=True)      # 出力される
        
        output = captured_output.getvalue()
        assert "[DEBUG] Debug message" not in output
        assert "[INFO] Info message" not in output
        assert "[WARNING] Warning message" in output
        assert "[ERROR] Error message" in output
    finally:
        Path(config_path).unlink()


@pytest.mark.integration
def test_logger_with_config_defaults():
    """config.yamlの実際の設定値でのLogger動作テスト"""
    # 実際のconfig.yamlを読み込み
    config = ConfigManager.load("config.yaml")
    logger = Logger(
        verbose=config.development.verbose,
        log_level=config.development.log_level
    )
    
    # 設定値を動的に確認（現在の設定: verbose: true, log_level: "DEBUG"）
    expected_verbose = config.development.verbose
    expected_log_level = config.development.log_level
    
    assert logger.verbose == expected_verbose
    assert logger.log_level == expected_log_level
    
    # 設定に応じたテスト
    captured_output = io.StringIO()
    with redirect_stdout(captured_output):
        logger.ulog("Debug test message", "debug", show_level=True)
    
    output = captured_output.getvalue()
    
    if expected_verbose:
        # verbose=Trueの場合、DEBUG以上であればメッセージが出力される
        if expected_log_level == "DEBUG":
            assert "[DEBUG] Debug test message" in output
        else:
            # DEBUG未満の場合は出力されない
            assert output == ""
    else:
        # verbose=Falseの場合は出力されない
        assert output == ""