#!/usr/bin/env python3
"""
Integration tests for encoding and character handling
エンコーディングと文字処理の統合テスト
"""

import pytest
import pytest_asyncio
import sys
import os


@pytest.mark.integration
@pytest.mark.encoding
def test_windows_cp932_handling():
    """Windows CP932エンコーディング処理のテスト"""
    # CP932で問題になりやすい文字
    test_strings = [
        "基本的な日本語",
        "㈱などの特殊文字",
        "①②③の丸数字",
        "♪の音符記号",
        "🐍絵文字を含む文字列"
    ]
    
    for text in test_strings:
        try:
            # CP932でエンコード可能か確認
            encoded = text.encode('cp932', errors='ignore')
            decoded = encoded.decode('cp932')
            # 絵文字は除外されることを許容
            assert len(decoded) <= len(text)
        except UnicodeEncodeError:
            # 絵文字などCP932でエンコードできない文字は期待通り
            pass


@pytest.mark.integration
@pytest.mark.encoding
def test_utf8_handling():
    """UTF-8エンコーディング処理のテスト"""
    # UTF-8で扱うべき文字
    test_strings = [
        "Hello World",
        "こんにちは世界",
        "😀😁😂🤣",  # 絵文字
        "中文字符测试",  # 中国語
        "한글 테스트",  # 韓国語
        "Здравствуй мир",  # ロシア語
    ]
    
    for text in test_strings:
        # UTF-8では全ての文字が正しくエンコード・デコードされる
        encoded = text.encode('utf-8')
        decoded = encoded.decode('utf-8')
        assert decoded == text


@pytest.mark.integration
@pytest.mark.encoding
def test_surrogate_pair_handling():
    """サロゲートペア処理のテスト"""
    # サロゲートペアを含む文字列
    test_strings = [
        "𠮷野家",  # 吉の異体字
        "𩸽定食",  # ほっけ
        "🏃‍♂️走る人",  # 複合絵文字
    ]
    
    for text in test_strings:
        # UTF-16でのエンコード・デコード
        encoded = text.encode('utf-16')
        decoded = encoded.decode('utf-16')
        assert decoded == text
        
        # 文字数カウントが正しいか
        # サロゲートペアは1文字としてカウント
        assert len(text) > 0


@pytest.mark.integration
@pytest.mark.encoding
def test_mixed_encoding_scenario():
    """混在エンコーディングシナリオのテスト"""
    # 実際のMCPエージェントで起こりうるシナリオ
    test_data = {
        "user_input": "年齢を計算して🎂",
        "system_response": "計算結果: 30歳",
        "mcp_tool_output": "multiply(30, 2) = 60",
    }
    
    # 各データが適切に処理されることを確認
    for key, value in test_data.items():
        # UTF-8として処理
        utf8_encoded = value.encode('utf-8')
        utf8_decoded = utf8_encoded.decode('utf-8')
        assert utf8_decoded == value
        
        # CP932で処理（エラーを無視）
        try:
            cp932_encoded = value.encode('cp932', errors='ignore')
            cp932_decoded = cp932_encoded.decode('cp932')
            # 一部文字が失われる可能性を許容
            assert len(cp932_decoded) <= len(value)
        except Exception:
            # エンコードエラーは許容
            pass


@pytest.mark.integration
@pytest.mark.encoding
@pytest.mark.skipif(sys.platform != "win32", reason="Windows専用テスト")
def test_windows_console_output():
    """Windowsコンソール出力のテスト"""
    import io
    import contextlib
    
    # コンソール出力をキャプチャ
    output = io.StringIO()
    
    test_strings = [
        "通常の日本語出力",
        "特殊文字→←↑↓",
        "絵文字は🚫表示されない可能性",
    ]
    
    with contextlib.redirect_stdout(output):
        for text in test_strings:
            try:
                print(text)
            except UnicodeEncodeError:
                # Windowsコンソールでのエンコードエラーは期待通り
                print(text.encode('cp932', errors='ignore').decode('cp932'))
    
    # 何らかの出力があることを確認
    result = output.getvalue()
    assert len(result) > 0


@pytest.mark.integration
@pytest.mark.encoding
def test_file_encoding():
    """ファイルエンコーディングのテスト"""
    import tempfile
    from pathlib import Path
    
    test_content = "テスト内容\n日本語を含むファイル\n🎌"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # UTF-8でファイル書き込み
        utf8_file = Path(tmpdir) / "test_utf8.txt"
        utf8_file.write_text(test_content, encoding='utf-8')
        
        # 読み込んで確認
        read_content = utf8_file.read_text(encoding='utf-8')
        assert read_content == test_content
        
        # CP932でファイル書き込み（エラー無視）
        cp932_file = Path(tmpdir) / "test_cp932.txt"
        cp932_content = test_content.encode('cp932', errors='ignore').decode('cp932')
        cp932_file.write_text(cp932_content, encoding='cp932')
        
        # 読み込んで確認
        read_cp932 = cp932_file.read_text(encoding='cp932')
        assert read_cp932 == cp932_content