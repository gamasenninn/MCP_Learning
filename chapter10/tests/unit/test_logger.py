#!/usr/bin/env python3
"""
Unit tests for Logger class
ログ機能の単体テスト
"""

import pytest
import io
import sys
from contextlib import redirect_stdout

from utils import Logger


@pytest.mark.unit
def test_logger_initialization():
    """Loggerの初期化テスト"""
    logger = Logger(verbose=True, log_level="INFO")
    assert logger.verbose is True
    assert logger.log_level == "INFO"
    assert logger.min_priority == 20


@pytest.mark.unit
def test_verbose_false_no_output():
    """verbose=False時は何も出力されないことをテスト"""
    logger = Logger(verbose=False, log_level="DEBUG")
    
    # 標準出力をキャプチャ
    captured_output = io.StringIO()
    with redirect_stdout(captured_output):
        logger.ulog("This should not appear", "debug", show_level=True)
        logger.ulog("This should not appear", "info", show_level=True)
        logger.ulog("This should not appear", "warning", show_level=True)
        logger.ulog("This should not appear", "error", show_level=True)
    
    output = captured_output.getvalue()
    assert output == ""


@pytest.mark.unit
def test_log_level_debug_shows_all():
    """log_level=DEBUG時は全レベルのメッセージが出力されることをテスト"""
    logger = Logger(verbose=True, log_level="DEBUG")
    
    captured_output = io.StringIO()
    with redirect_stdout(captured_output):
        logger.ulog("Debug message", "debug", show_level=True)
        logger.ulog("Info message", "info", show_level=True)
        logger.ulog("Warning message", "warning", show_level=True)
        logger.ulog("Error message", "error", show_level=True)
    
    output = captured_output.getvalue()
    assert "[DEBUG] Debug message" in output
    assert "[INFO] Info message" in output
    assert "[WARNING] Warning message" in output
    assert "[ERROR] Error message" in output


@pytest.mark.unit
def test_log_level_info_filters_debug():
    """log_level=INFO時はDEBUGメッセージが出力されないことをテスト"""
    logger = Logger(verbose=True, log_level="INFO")
    
    captured_output = io.StringIO()
    with redirect_stdout(captured_output):
        logger.ulog("Debug message", "debug", show_level=True)
        logger.ulog("Info message", "info", show_level=True)
        logger.ulog("Warning message", "warning", show_level=True)
        logger.ulog("Error message", "error", show_level=True)
    
    output = captured_output.getvalue()
    assert "[DEBUG] Debug message" not in output
    assert "[INFO] Info message" in output
    assert "[WARNING] Warning message" in output
    assert "[ERROR] Error message" in output


@pytest.mark.unit
def test_log_level_warning_filters_debug_info():
    """log_level=WARNING時はDEBUG、INFOメッセージが出力されないことをテスト"""
    logger = Logger(verbose=True, log_level="WARNING")
    
    captured_output = io.StringIO()
    with redirect_stdout(captured_output):
        logger.ulog("Debug message", "debug", show_level=True)
        logger.ulog("Info message", "info", show_level=True)
        logger.ulog("Warning message", "warning", show_level=True)
        logger.ulog("Error message", "error", show_level=True)
    
    output = captured_output.getvalue()
    assert "[DEBUG] Debug message" not in output
    assert "[INFO] Info message" not in output
    assert "[WARNING] Warning message" in output
    assert "[ERROR] Error message" in output


@pytest.mark.unit
def test_log_level_error_only_errors():
    """log_level=ERROR時はERRORのみ出力されることをテスト"""
    logger = Logger(verbose=True, log_level="ERROR")
    
    captured_output = io.StringIO()
    with redirect_stdout(captured_output):
        logger.ulog("Debug message", "debug", show_level=True)
        logger.ulog("Info message", "info", show_level=True)
        logger.ulog("Warning message", "warning", show_level=True)
        logger.ulog("Error message", "error", show_level=True)
    
    output = captured_output.getvalue()
    assert "[DEBUG] Debug message" not in output
    assert "[INFO] Info message" not in output
    assert "[WARNING] Warning message" not in output
    assert "[ERROR] Error message" in output


@pytest.mark.unit
def test_invalid_log_level_defaults_to_info():
    """無効なログレベルの場合はINFOにデフォルトすることをテスト"""
    logger = Logger(verbose=True, log_level="INVALID")
    assert logger.min_priority == 20  # INFO level priority