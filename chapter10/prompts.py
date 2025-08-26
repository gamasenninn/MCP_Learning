#!/usr/bin/env python3
"""
Prompt Templates for MCP Agent V4
プロンプト管理の一元化

段階的にプロンプトを外部化し、管理を改善する
"""

from typing import Optional, Dict, List


class PromptTemplates:
    """
    プロンプトテンプレートの一元管理クラス
    
    各メソッドは動的な値を引数として受け取り、
    完成されたプロンプト文字列を返す
    """
    
    @staticmethod
    def get_execution_type_determination_prompt(
        recent_context: Optional[str],
        user_query: str,
        tools_info: Optional[str] = None
    ) -> str:
        """
        実行方式判定用のプロンプトを生成
        
        Args:
            recent_context: 最近の会話文脈
            user_query: ユーザーの要求
            tools_info: 利用可能なツール情報
            
        Returns:
            実行方式判定用プロンプト
        """
        context_section = recent_context if recent_context else "（新規会話）"
        tools_section = tools_info if tools_info else "（ツール情報の取得に失敗しました）"
        
        return f"""ユーザーの要求を分析し、適切な実行方式を判定してください。

## 最近の会話
{context_section}

## ユーザーの要求
{user_query}

## 利用可能なツール
{tools_section}

## 判定基準
- **NO_TOOL**: 日常会話（挨拶・雑談・自己紹介・感想・お礼等のみ）
- **SIMPLE**: 1-2ステップの単純なタスク（計算、単一API呼び出し等）
- **COMPLEX**: データベース操作、多段階処理等

## 重要な注意
- 上記のツール一覧を確認し、実行可能なタスクかどうか判定してください
- 「天気」「温度」「気象」→外部APIツールが必要
- 「商品」「データベース」「一覧」→データベースツールが必要
- 「ディレクトリ」「ファイル」「フォルダ」「読む」「書く」「保存」→ファイルシステムツールが必要
- 利用可能なツールで実行可能な場合はNO_TOOLではありません！

## 出力形式
NO_TOOLの場合：
```json
{{"type": "NO_TOOL", "response": "**Markdown形式**で適切な応答メッセージ", "reason": "判定理由"}}
```

その他の場合：
```json
{{"type": "SIMPLE|COMPLEX", "reason": "判定理由"}}
```"""

    @staticmethod
    def get_adaptive_task_list_prompt(
        recent_context: Optional[str],
        user_query: str,
        tools_info: str,
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        クエリの複雑さに応じて適応的なタスクリスト生成プロンプトを生成
        
        Args:
            recent_context: 最近の会話文脈
            user_query: ユーザーの要求
            tools_info: 利用可能なツール情報
            custom_instructions: カスタム指示（オプション）
            
        Returns:
            適応的なタスクリスト生成プロンプト
        """
        context_section = recent_context if recent_context else "（新規会話）"
        
        # カスタム指示がある場合は複雑タスク用の詳細プロンプト
        if custom_instructions:
            custom_section = custom_instructions
            max_tasks_note = "必要最小限のタスクで構成し、効率的な実行計画を作成してください。"
            database_rules = """
## データベース操作の必須ルール（重要）
データベース関連の要求は必ず以下の3ステップ：
1. list_tables - テーブル一覧確認
2. get_table_schema - 対象テーブルのスキーマ確認  
3. execute_safe_query - 実際のクエリ実行

## データベース表示ルール
- 「一覧」「全件」「すべて」→ LIMIT 20（適度な件数）
- 「少し」「いくつか」→ LIMIT 5
- 「全部」「制限なし」→ LIMIT 50（最大）
- 「1つ」「最高」「最安」→ LIMIT 1

例：「商品データ一覧を表示して」
→ [
  {{"tool": "list_tables", "description": "テーブル一覧を確認"}},
  {{"tool": "get_table_schema", "params": {{"table_name": "products"}}, "description": "商品テーブルのスキーマを確認"}},
  {{"tool": "execute_safe_query", "params": {{"query": "SELECT * FROM products LIMIT 20"}}, "description": "商品データを20件表示"}}
]
"""
        else:
            custom_section = "なし"
            max_tasks_note = "1-3個の必要最小限のタスクで構成してください。"
            database_rules = ""
        
        return f"""ユーザーの要求を分析し、実行に必要なタスクリストを生成してください。

## 現在のユーザー要求（独立して処理）
{user_query}

## 利用可能なツール
{tools_info}

## カスタム指示
{custom_section}

## 注意: 以下は参考文脈のみ（現在の要求とは独立して扱う）
最近の会話: {context_section}

{database_rules}

## 指針
- 計算の場合は演算順序を考慮
- 天気等の単純API呼び出しは1つのタスクで完結
- {max_tasks_note}

## タスク依存関係の表現
前のタスクの結果を使用する場合：
- `"取得した都市名"` - IP情報から取得した都市
- `"{{{{previous_result}}}}"` - 直前のタスク結果
- `"{{{{task_1.city}}}}"` - 1番目のタスクのcityフィールド

例：「IPから現在地を調べて天気を取得」
```json
{{"tasks": [
  {{"tool": "get_ip_info", "params": {{}}, "description": "現在のIPアドレスの地理的情報を取得する"}},
  {{"tool": "get_weather", "params": {{"city": "取得した都市名"}}, "description": "取得した都市の現在の天気を取得する"}}
]}}
```

## 出力形式
```json
{{"tasks": [
  {{"tool": "ツール名", "params": {{"param": "値"}}, "description": "何をするかの説明"}},
  ...
]}}
```"""
    
    @staticmethod
    def get_simple_task_list_prompt(
        recent_context: Optional[str],
        user_query: str,
        tools_info: str
    ) -> str:
        """
        シンプルなタスクリスト生成用のプロンプトを生成
        
        Args:
            recent_context: 最近の会話文脈
            user_query: ユーザーの要求
            tools_info: 利用可能なツール情報
            
        Returns:
            シンプルなタスクリスト生成用プロンプト
        """
        context_section = recent_context if recent_context else "（新規会話）"
        
        return f"""ユーザーの単純な要求に対して、最小限のタスクリストを生成してください。

## 最近の会話
{context_section}

## ユーザーの要求
{user_query}

## 利用可能なツール
{tools_info}

## 指針
- 1-3個の必要最小限のタスクで構成
- 計算の場合は演算順序を考慮
- 天気等の単一API呼び出しは1つのタスクで完結

## タスク依存関係の表現
前のタスクの結果を使用する場合：
- `"取得した都市名"` - IP情報から取得した都市
- `"{{previous_result}}"` - 直前のタスク結果
- `"{{task_1.city}}"` - 1番目のタスクのcityフィールド

例：「IPから現在地を調べて天気を取得」
```json
{{"tasks": [
  {{"tool": "get_ip_info", "params": {{}}, "description": "現在のIPアドレスの地理的情報を取得する"}},
  {{"tool": "get_weather", "params": {{"city": "取得した都市名"}}, "description": "取得した都市の現在の天気を取得する"}}
]}}
```

## 出力形式
```json
{{"tasks": [
  {{"tool": "ツール名", "params": {{"param": "値"}}, "description": "何をするかの説明"}},
  ...
]}}
```"""

    @staticmethod  
    def get_complex_task_list_prompt(
        recent_context: Optional[str],
        user_query: str,
        tools_info: str,
        custom_instructions: Optional[str]
    ) -> str:
        """
        複雑なタスクリスト生成用のプロンプトを生成
        
        Args:
            recent_context: 最近の会話文脈
            user_query: ユーザーの要求
            tools_info: 利用可能なツール情報
            custom_instructions: カスタム指示
            
        Returns:
            複雑なタスクリスト生成用プロンプト
        """
        context_section = recent_context if recent_context else "（新規会話）"
        custom_section = custom_instructions if custom_instructions else "なし"
        
        return f"""ユーザーの要求を分析し、実行に必要なタスクリストを生成してください。

## 最近の会話
{context_section}

## ユーザーの要求
{user_query}

## 利用可能なツール
{tools_info}

## カスタム指示
{custom_section}

## データベース操作の必須ルール（重要）
データベース関連の要求は必ず以下の3ステップ：
1. list_tables - テーブル一覧確認
2. get_table_schema - 対象テーブルのスキーマ確認  
3. execute_safe_query - 実際のクエリ実行

## データベース表示ルール
- 「一覧」「全件」「すべて」→ LIMIT 20（適度な件数）
- 「少し」「いくつか」→ LIMIT 5
- 「全部」「制限なし」→ LIMIT 50（最大）
- 「1つ」「最高」「最安」→ LIMIT 1

例：「商品データ一覧を表示して」
→ [
  {{"tool": "list_tables", "description": "テーブル一覧を確認"}},
  {{"tool": "get_table_schema", "params": {{"table_name": "products"}}, "description": "商品テーブルのスキーマを確認"}},
  {{"tool": "execute_safe_query", "params": {{"query": "SELECT * FROM products LIMIT 20"}}, "description": "商品データを20件表示"}}
]

## 出力形式
```json
{{"tasks": [
  {{"tool": "ツール名", "params": {{"param": "値"}}, "description": "何をするかの説明"}},
  ...
]}}
```

必要最小限のタスクで構成し、効率的な実行計画を作成してください。"""

    @staticmethod
    def get_result_interpretation_prompt(
        recent_context: Optional[str],
        user_query: str,
        serializable_results: str,
        custom_instructions: Optional[str]
    ) -> str:
        """
        実行結果解釈用のプロンプトを生成
        
        Args:
            recent_context: 最近の会話文脈
            user_query: ユーザーの元の質問
            serializable_results: 実行結果（JSON文字列）
            custom_instructions: カスタム指示
            
        Returns:
            実行結果解釈用プロンプト
        """
        context_section = recent_context if recent_context else "（新規会話）"
        custom_section = custom_instructions if custom_instructions else "特になし"
        
        return f"""実行結果を解釈して、ユーザーに分かりやすく回答してください。

## 会話の文脈
{context_section}

## ユーザーの元の質問
{user_query}

## 実行されたタスクと結果
{serializable_results}

## カスタム指示
{custom_section}

ユーザーの質問に直接答え、成功したタスクの結果を統合して自然な回答を生成してください。
失敗したタスクがある場合は、その影響を考慮した回答にしてください。

## 出力形式
回答は**Markdown形式**で整理して出力してください：
- 見出しは `### タイトル`
- 重要な情報は `**太字**`
- リストは `-` または `1.` 
- コードや値は `code`
- 実行結果は `> 結果`
- 長い結果は適切に改行・整理

例：
### 実行結果
計算が完了しました：
- **100 + 200** = `300`
- 実行時間: `0.5秒`

> すべての計算が正常に完了しました。"""