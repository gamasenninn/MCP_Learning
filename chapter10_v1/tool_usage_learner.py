#!/usr/bin/env python3
"""
動的ツール使用方法学習システム
MCPサーバーのツール説明から使用パターンを自動学習
"""

import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

@dataclass
class ToolUsageExample:
    """ツール使用例のデータ構造"""
    tool_name: str
    query_pattern: str  # ユーザーの質問パターン
    params: Dict[str, Any]  # 実際のパラメータ
    success_count: int = 0  # 成功回数
    last_used: str = ""  # 最後に使用された日時
    source: str = "inferred"  # "inferred" または "learned"
    use_cases: List[str] = field(default_factory=list)  # 使用例（「商品の合計」など）
    param_details: Dict[str, Any] = field(default_factory=dict)  # パラメータ詳細情報
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ToolUsageExample':
        return cls(**data)

class ToolUsageLearner:
    """ツール使用方法の自動学習システム（ダブル情報対応版）"""
    
    def __init__(self, cache_file: str = "tool_usage_cache.json"):
        self.cache_file = Path(cache_file)
        self.usage_patterns: Dict[str, List[ToolUsageExample]] = {}
        self.tool_categories: Dict[str, str] = {}
        self.detailed_tool_info: Dict[str, Dict] = {}  # 詳細ツール情報のキャッシュ
        self.load_cache()
        
        # 基本的なカテゴリマッピング
        self.keyword_categories = {
            "data_retrieval": [
                "select", "get", "fetch", "list", "show", "retrieve", "query", 
                "一覧", "表示", "取得", "検索", "抽出", "データ"
            ],
            "schema_info": [
                "structure", "schema", "describe", "info", "table_info",
                "構造", "スキーマ", "テーブル", "情報", "設計"
            ],
            "data_analysis": [
                "analyze", "count", "sum", "average", "max", "min", "group",
                "分析", "集計", "合計", "平均", "最大", "最小", "統計"
            ],
            "file_operations": [
                "read", "write", "create", "delete", "file", "directory",
                "読み", "書き", "作成", "削除", "ファイル", "フォルダ"
            ],
            "calculations": [
                "calculate", "compute", "add", "subtract", "multiply", "divide",
                "計算", "足し", "引き", "掛け", "割り", "乗"
            ]
        }
    
    def categorize_tool(self, tool_name: str, description: str) -> str:
        """ツールをカテゴリに分類"""
        description_lower = description.lower()
        tool_name_lower = tool_name.lower()
        
        category_scores = {}
        for category, keywords in self.keyword_categories.items():
            score = 0
            for keyword in keywords:
                if keyword in description_lower:
                    score += 2
                if keyword in tool_name_lower:
                    score += 1
            category_scores[category] = score
        
        # 最高スコアのカテゴリを返す
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                return best_category
        
        return "general"
    
    def collect_detailed_tool_info(self, connection_manager):
        """詳細ツール情報を収集（mcp_llm_step2スタイル）"""
        from mcp_llm_step1 import ToolCollector
        from mcp_llm_step2 import LLMIntegrationPrep
        
        # 既存の接続マネージャーから詳細情報を抽出
        prep = LLMIntegrationPrep()
        
        # 接続マネージャーのツール情報を step1 形式に変換
        tools_schema = {}
        for tool_name, tool_info in connection_manager.tools_info.items():
            server_name = tool_info["server"]
            schema = tool_info["schema"]
            
            if server_name not in tools_schema:
                tools_schema[server_name] = []
            
            # mcp_llm_step1と同じ形式に変換
            tool_data = {
                "name": tool_name,
                "description": schema.get("description", ""),
                "parameters": schema.get("inputSchema", {})
            }
            tools_schema[server_name].append(tool_data)
        
        # 詳細情報を生成
        detailed_desc = prep.prepare_tools_for_llm(tools_schema)
        
        # 詳細情報をパースして保存
        self._parse_detailed_descriptions(detailed_desc)
        
        return detailed_desc
    
    def _parse_detailed_descriptions(self, detailed_desc: str):
        """詳細説明をパースして構造化データに変換"""
        sections = detailed_desc.split("\n\n")
        
        for section in sections:
            if not section.strip():
                continue
                
            lines = section.split("\n")
            if not lines:
                continue
                
            # ツール名を抽出（例: "calculator.add:"）
            header = lines[0].strip()
            if ":" not in header:
                continue
                
            tool_full_name = header.replace(":", "")
            if "." in tool_full_name:
                server, tool_name = tool_full_name.split(".", 1)
            else:
                tool_name = tool_full_name
                server = "unknown"
            
            # 詳細情報を抽出
            description = ""
            use_cases = []
            param_details = {}
            
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("説明:"):
                    description = line.replace("説明:", "").strip()
                elif "例:" in line or "例F:" in line:
                    # 使用例を抽出（複数行にまたがる場合も考慮）
                    examples_text = ""
                    if "例:" in line:
                        examples_text = line.split("例:")[-1].strip()
                    elif "例F:" in line:
                        examples_text = line.split("例F:")[-1].strip()
                    
                    if examples_text:
                        # 「」で囲まれた例を抽出
                        import re
                        quoted_examples = re.findall(r'「([^」]+)」', examples_text)
                        if quoted_examples:
                            use_cases.extend(quoted_examples)
                        else:
                            # 「」がない場合は通常の分割
                            use_cases.extend([ex.strip() for ex in examples_text.split("、") if ex.strip() and "H" not in ex])
                elif line.startswith("- ") and "(" in line:
                    # パラメータ詳細を抽出
                    param_line = line[2:]  # "- " を除去
                    if "(" in param_line and ")" in param_line:
                        param_name = param_line.split("(")[0].strip()
                        param_info_str = param_line.split("(")[1].split(")")[0]
                        param_details[param_name] = param_info_str
            
            # 詳細情報を保存
            self.detailed_tool_info[tool_name] = {
                "server": server,
                "description": description,
                "use_cases": use_cases,
                "param_details": param_details
            }
    
    def infer_usage_patterns(self, tool_name: str, tool_schema: Dict[str, Any]) -> List[ToolUsageExample]:
        """ツールスキーマから使用パターンを推論（ダブル情報対応版）"""
        description = tool_schema.get("description", "")
        input_schema = tool_schema.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        
        patterns = []
        category = self.categorize_tool(tool_name, description)
        
        # 詳細情報があれば活用
        detailed_info = self.detailed_tool_info.get(tool_name, {})
        use_cases = detailed_info.get("use_cases", [])
        param_details = detailed_info.get("param_details", {})
        
        # カテゴリに基づいた基本パターンを生成
        if category == "data_retrieval":
            patterns.extend(self._generate_data_retrieval_patterns(tool_name, description, properties, use_cases, param_details))
        elif category == "schema_info":
            patterns.extend(self._generate_schema_info_patterns(tool_name, description, properties, use_cases, param_details))
        elif category == "calculations":
            patterns.extend(self._generate_calculation_patterns(tool_name, description, properties, use_cases, param_details))
        elif category == "file_operations":
            patterns.extend(self._generate_file_operation_patterns(tool_name, description, properties, use_cases, param_details))
        else:
            # 汎用パターン
            patterns.extend(self._generate_generic_patterns(tool_name, description, properties, use_cases, param_details))
        
        return patterns
    
    def _generate_data_retrieval_patterns(self, tool_name: str, description: str, properties: Dict, use_cases: List[str] = None, param_details: Dict = None) -> List[ToolUsageExample]:
        """データ取得系ツールのパターン生成（詳細情報対応版）"""
        patterns = []
        use_cases = use_cases or []
        param_details = param_details or {}
        
        if "sql" in properties:
            # 基本パターン
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern="データを表示",
                params={"sql": "SELECT * FROM table_name"},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern="条件付きで検索",
                params={"sql": "SELECT * FROM table_name WHERE condition"},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
            
            # 詳細情報からの追加パターン
            for use_case in use_cases[:2]:  # 最大2個の使用例
                patterns.append(ToolUsageExample(
                    tool_name=tool_name,
                    query_pattern=use_case,
                    params={"sql": f"-- {use_case} のSQL"},
                    source="inferred",
                    use_cases=use_cases,
                    param_details=param_details
                ))
                
        elif "table_name" in properties:
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern="テーブルの詳細",
                params={"table_name": "example_table"},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
        else:
            # パラメータなしの一覧取得
            query_pattern = use_cases[0] if use_cases else "一覧を表示"
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern=query_pattern,
                params={},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
        
        return patterns
    
    def _generate_schema_info_patterns(self, tool_name: str, description: str, properties: Dict, use_cases: List[str] = None, param_details: Dict = None) -> List[ToolUsageExample]:
        """スキーマ情報系ツールのパターン生成（詳細情報対応版）"""
        patterns = []
        use_cases = use_cases or []
        param_details = param_details or {}
        
        if "table_name" in properties:
            query_pattern = use_cases[0] if use_cases else "テーブル構造を確認"
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern=query_pattern,
                params={"table_name": "table_name"},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
        else:
            query_pattern = use_cases[0] if use_cases else "構造を確認"
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern=query_pattern,
                params={},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
        
        return patterns
    
    def _generate_calculation_patterns(self, tool_name: str, description: str, properties: Dict, use_cases: List[str] = None, param_details: Dict = None) -> List[ToolUsageExample]:
        """計算系ツールのパターン生成（詳細情報対応版）"""
        patterns = []
        use_cases = use_cases or []
        param_details = param_details or {}
        
        if "a" in properties and "b" in properties:
            # 基本パターン
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern="数値を計算",
                params={"a": 10, "b": 5},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
            
            # 詳細情報からの追加パターン
            for use_case in use_cases[:3]:  # 最大3個の使用例
                patterns.append(ToolUsageExample(
                    tool_name=tool_name,
                    query_pattern=use_case,
                    params={"a": 100, "b": 50},  # より実用的な数値
                    source="inferred",
                    use_cases=use_cases,
                    param_details=param_details
                ))
                
        elif len(properties) == 1:
            param_name = list(properties.keys())[0]
            query_pattern = use_cases[0] if use_cases else "単一値で計算"
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern=query_pattern,
                params={param_name: 10},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
        
        return patterns
    
    def _generate_file_operation_patterns(self, tool_name: str, description: str, properties: Dict, use_cases: List[str] = None, param_details: Dict = None) -> List[ToolUsageExample]:
        """ファイル操作系ツールのパターン生成（詳細情報対応版）"""
        patterns = []
        use_cases = use_cases or []
        param_details = param_details or {}
        
        if "path" in properties or "file_path" in properties:
            param_name = "path" if "path" in properties else "file_path"
            
            if "read" in tool_name.lower() or "読" in description:
                query_pattern = use_cases[0] if use_cases else "ファイルを読む"
                patterns.append(ToolUsageExample(
                    tool_name=tool_name,
                    query_pattern=query_pattern,
                    params={param_name: "example.txt"},
                    source="inferred",
                    use_cases=use_cases,
                    param_details=param_details
                ))
            elif "write" in tool_name.lower() or "書" in description:
                params = {param_name: "example.txt"}
                if "content" in properties:
                    params["content"] = "サンプルテキスト"
                query_pattern = use_cases[0] if use_cases else "ファイルに書く"
                patterns.append(ToolUsageExample(
                    tool_name=tool_name,
                    query_pattern=query_pattern,
                    params=params,
                    source="inferred",
                    use_cases=use_cases,
                    param_details=param_details
                ))
        else:
            # パラメータが無い場合
            query_pattern = use_cases[0] if use_cases else f"{tool_name}を実行"
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern=query_pattern,
                params={},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
        
        return patterns
    
    def _generate_generic_patterns(self, tool_name: str, description: str, properties: Dict, use_cases: List[str] = None, param_details: Dict = None) -> List[ToolUsageExample]:
        """汎用パターン生成（詳細情報対応版）"""
        patterns = []
        use_cases = use_cases or []
        param_details = param_details or {}
        
        # 基本的なパターンを生成
        if properties:
            # サンプルパラメータを作成
            sample_params = {}
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "string")
                if param_type == "string":
                    sample_params[param_name] = "sample_value"
                elif param_type == "number" or param_type == "integer":
                    sample_params[param_name] = 10
                elif param_type == "boolean":
                    sample_params[param_name] = True
                else:
                    sample_params[param_name] = "sample_value"
            
            query_pattern = use_cases[0] if use_cases else f"{tool_name}を実行"
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern=query_pattern,
                params=sample_params,
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
        else:
            query_pattern = use_cases[0] if use_cases else f"{tool_name}を実行"
            patterns.append(ToolUsageExample(
                tool_name=tool_name,
                query_pattern=query_pattern,
                params={},
                source="inferred",
                use_cases=use_cases,
                param_details=param_details
            ))
        
        return patterns
    
    def learn_from_success(self, tool_name: str, query: str, params: Dict[str, Any]):
        """成功した実行から学習"""
        timestamp = datetime.now().isoformat()
        
        # 既存のパターンを探す
        if tool_name in self.usage_patterns:
            # 類似のパターンがあるかチェック
            for pattern in self.usage_patterns[tool_name]:
                if self._is_similar_pattern(pattern.params, params):
                    pattern.success_count += 1
                    pattern.last_used = timestamp
                    pattern.source = "learned"
                    self.save_cache()
                    return
        
        # 新しいパターンとして追加
        new_pattern = ToolUsageExample(
            tool_name=tool_name,
            query_pattern=self._extract_query_pattern(query),
            params=params,
            success_count=1,
            last_used=timestamp,
            source="learned"
        )
        
        if tool_name not in self.usage_patterns:
            self.usage_patterns[tool_name] = []
        
        self.usage_patterns[tool_name].append(new_pattern)
        self.save_cache()
    
    def _is_similar_pattern(self, pattern1: Dict, pattern2: Dict) -> bool:
        """パラメータパターンが類似しているかチェック"""
        if set(pattern1.keys()) != set(pattern2.keys()):
            return False
        
        # SQLパターンの場合は特別処理
        if "sql" in pattern1:
            sql1 = pattern1["sql"].upper().strip()
            sql2 = pattern2["sql"].upper().strip()
            # 基本的なSQL構造が同じかチェック
            return self._normalize_sql(sql1) == self._normalize_sql(sql2)
        
        return True
    
    def _normalize_sql(self, sql: str) -> str:
        """SQLを正規化（テーブル名や値を汎用化）"""
        # 基本的な正規化のみ実装
        sql = re.sub(r'\b\w+\b(?=\s+FROM)', 'COLUMNS', sql)  # カラム名を汎用化
        sql = re.sub(r'FROM\s+\w+', 'FROM TABLE', sql)  # テーブル名を汎用化
        sql = re.sub(r"'\w+'", "'VALUE'", sql)  # 文字列値を汎用化
        sql = re.sub(r'\b\d+\b', 'NUMBER', sql)  # 数値を汎用化
        return sql
    
    def _extract_query_pattern(self, query: str) -> str:
        """クエリから汎用パターンを抽出"""
        # 具体的な値を汎用的な表現に置換
        pattern = re.sub(r'\b\d+\b', 'NUMBER', query)
        pattern = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b(?=テーブル|table)', 'TABLE_NAME', pattern)
        return pattern[:50]  # 最大50文字に制限
    
    def get_usage_examples(self, tool_name: str, limit: int = 3) -> List[ToolUsageExample]:
        """ツールの使用例を取得（成功回数でソート）"""
        if tool_name not in self.usage_patterns:
            return []
        
        patterns = self.usage_patterns[tool_name]
        # 成功回数でソート
        sorted_patterns = sorted(patterns, key=lambda x: x.success_count, reverse=True)
        return sorted_patterns[:limit]
    
    def initialize_tool_patterns(self, tools_info: Dict[str, Dict]):
        """ツール情報から初期パターンを生成"""
        for tool_name, tool_info in tools_info.items():
            if tool_name not in self.usage_patterns:
                schema = tool_info.get("schema", {})
                patterns = self.infer_usage_patterns(tool_name, schema)
                self.usage_patterns[tool_name] = patterns
                self.tool_categories[tool_name] = self.categorize_tool(
                    tool_name, schema.get("description", "")
                )
        
        self.save_cache()
    
    def load_cache(self):
        """キャッシュファイルから使用パターンを読み込み"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.usage_patterns = {}
                for tool_name, patterns_data in data.get("patterns", {}).items():
                    self.usage_patterns[tool_name] = [
                        ToolUsageExample.from_dict(p) for p in patterns_data
                    ]
                
                self.tool_categories = data.get("categories", {})
                self.detailed_tool_info = data.get("detailed_info", {})
            except Exception as e:
                print(f"キャッシュ読み込みエラー: {e}")
                self.usage_patterns = {}
                self.tool_categories = {}
                self.detailed_tool_info = {}
    
    def save_cache(self):
        """使用パターンをキャッシュファイルに保存（詳細情報対応版）"""
        try:
            data = {
                "patterns": {
                    tool_name: [p.to_dict() for p in patterns]
                    for tool_name, patterns in self.usage_patterns.items()
                },
                "categories": self.tool_categories,
                "detailed_info": self.detailed_tool_info,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"キャッシュ保存エラー: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """学習統計を取得"""
        total_patterns = sum(len(patterns) for patterns in self.usage_patterns.values())
        learned_patterns = sum(
            len([p for p in patterns if p.source == "learned"])
            for patterns in self.usage_patterns.values()
        )
        
        return {
            "total_tools": len(self.usage_patterns),
            "total_patterns": total_patterns,
            "learned_patterns": learned_patterns,
            "inferred_patterns": total_patterns - learned_patterns,
            "categories": len(set(self.tool_categories.values()))
        }

# 使用例とテスト
if __name__ == "__main__":
    learner = ToolUsageLearner()
    
    # サンプルツール情報
    sample_tools = {
        "execute_safe_query": {
            "schema": {
                "description": "SELECTクエリのみを安全に実行。データの検索、集計、分析に使用。",
                "inputSchema": {
                    "properties": {
                        "sql": {"type": "string"}
                    }
                }
            }
        },
        "list_tables": {
            "schema": {
                "description": "データベース内のすべてのテーブルとスキーマ情報を一覧表示。",
                "inputSchema": {
                    "properties": {}
                }
            }
        }
    }
    
    # 初期パターン生成
    learner.initialize_tool_patterns(sample_tools)
    
    # 統計情報を表示
    stats = learner.get_statistics()
    print("学習統計:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 使用例を表示
    for tool_name in sample_tools.keys():
        examples = learner.get_usage_examples(tool_name)
        print(f"\n{tool_name}の使用例:")
        for example in examples:
            print(f"  - {example.query_pattern}: {example.params}")