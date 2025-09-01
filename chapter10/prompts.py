#!/usr/bin/env python3
"""
Prompt Templates for MCP Agent
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
        CLARIFICATION対応の実行方式判定用プロンプトを生成
        
        Args:
            recent_context: 最近の会話文脈
            user_query: ユーザーの要求
            tools_info: 利用可能なツール情報
            
        Returns:
            実行方式判定用プロンプト（CLARIFICATION対応版）
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
- **NO_TOOL**: 日常会話（挨拶・雑談・自己紹介・感想・お礼等）または会話履歴から回答可能な質問
- **CLARIFICATION**: 不明な情報があり、ユーザーに確認が必要（「私の年齢」「当社の売上」等）
- **TOOL**: ツール実行が必要なタスク（計算、データベース操作、API呼び出し等）

## CLARIFICATION判定基準（重要）

**まず最初に必ず会話履歴（最近の会話）を確認してください：**
- ユーザーが尋ねている情報が既に会話履歴に含まれている場合、CLARIFICATIONではありません
- 会話履歴の「User:」の発言がユーザーの情報、「Assistant:」の発言がアシスタント（あなた）の情報です
- 例：User「俺の名前はサトシ」→「俺の名前は？」→ NO_TOOLで「サトシ」と回答
- 例：User「君の名前はガーコ」→「君の名前は？」→ NO_TOOLで「ガーコ」と回答
- 例：User「私の年齢は65歳」→「私の年齢に10を足して」→ TOOLで75と計算

**重要な識別ルール：**
- 「俺の」「私の」「僕の」= ユーザー（User）の情報を指す
- 「君の」「あなたの」= アシスタント（Assistant）の情報を指す
- 会話履歴から正しく人称を識別して回答してください

**アシスタントの名前設定の認識（超重要）：**
- User: 「君の名前は〇〇」「君の名前を〇〇にしよう」「〇〇と呼んでいい？」→ アシスタントの名前を設定
- User: 「君の名前を決めよう。〇〇ってどう？」→ アシスタントの名前を〇〇に設定
- 一度設定された名前は必ず記憶し、その後「君の名前は？」と聞かれたら設定された名前を答える
- 時系列で最新の名前設定を使用する（例：最初「ガーコ」→後で「ミケ」なら「ミケ」を使用）

**会話履歴に情報がない場合のみ、以下のパターンでCLARIFICATIONを選択：**
- 「私の〜」「自分の〜」「僕の〜」「俺の〜」（会話履歴にその情報がない場合）
- 「当社の〜」「うちの〜」「この〜」「その〜」（会話履歴にその情報がない場合）
- 具体的な数値が不明な計算要求（例：会話履歴にない「私の年齢に10を足して」）
- 詳細不明なデータ要求（例：会話履歴にない「私のタスクを表示」）

## 重要な注意
- 上記のツール一覧を確認し、実行可能なタスクかどうか判定してください
- 「天気」「温度」「気象」→外部APIツールが必要
- 「商品」「データベース」「一覧」→データベースツールが必要
- 「ディレクトリ」「ファイル」「フォルダ」「読む」「書く」「保存」→ファイルシステムツールが必要
- 利用可能なツールで実行可能な場合はNO_TOOLではありません！

## 出力形式
NO_TOOLの場合（会話履歴から回答する場合も含む）：
- 会話履歴を参照して、正確に情報を取得してください
- 「俺の名前は？」→ 履歴のUser発言から名前を取得
- 「君の名前は？」→ 履歴でUserが設定したアシスタントの名前を取得
- **重要**: 会話履歴で設定された名前や関係性を一貫して維持し、ユーザーに寄り添った自然な応答をしてください
- ユーザーが設定したアシスタントの名前（例：ガーコ）は必ず記憶し、「アシスタント」という機械的な名前は絶対に使わない
- 「君の名前を決めよう。ガーコちゃんってどう？」のような発言があったら、それ以降は「私の名前はガーコです」と答える
- 親しみやすく、会話の文脈に合った応答を心がける
- 会話履歴を最初から最後まで読み、名前の設定を見逃さないこと
```json
{{"type": "NO_TOOL", "response": "**Markdown形式**で適切な応答メッセージ", "reason": "判定理由"}}
```

CLARIFICATIONの場合（不明な情報がある場合）：
```json
{{"type": "CLARIFICATION", "reason": "不明な情報があります", "clarification": {{"question": "具体的な質問", "context": "詳細説明"}}}}
```

その他の場合：
```json
{{"type": "TOOL", "reason": "判定理由"}}
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
        # 統一版へのラッパーとして実装
        return PromptTemplates.get_unified_task_list_prompt(
            recent_context=recent_context,
            user_query=user_query,
            tools_info=tools_info,
            custom_instructions=custom_instructions
        )
    
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
        # 統一版へのラッパーとして実装（custom_instructions=None）
        return PromptTemplates.get_unified_task_list_prompt(
            recent_context=recent_context,
            user_query=user_query,
            tools_info=tools_info,
            custom_instructions=None
        )


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

    @staticmethod
    def get_unified_task_list_prompt(
        recent_context: Optional[str],
        user_query: str,
        tools_info: str,
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        統一タスクリスト生成プロンプト（SIMPLE/COMPLEX統合版）
        
        Args:
            recent_context: 最近の会話文脈
            user_query: ユーザーの要求
            tools_info: 利用可能なツール情報
            custom_instructions: カスタム指示（AGENT.mdからの内容）
            
        Returns:
            統一されたタスクリスト生成プロンプト
        """
        context_section = recent_context if recent_context else "（新規会話）"
        custom_section = custom_instructions if custom_instructions else "なし"
        
        # カスタム指示がある場合のみ詳細ルールを適用
        if custom_instructions:
            max_tasks_note = "必要最小限のタスクで構成し、効率的な実行計画を作成してください。"
            database_rules = """
## データベース操作の最適化ルール（重要）
データベース関連の要求は効率的な2ステップ：
1. list_tables - テーブル一覧とスキーマ確認（十分な構造情報を含む）
2. execute_safe_query - 実際のクエリ実行

## データベース表示ルール
- 「一覧」「全件」「すべて」→ LIMIT 20（適度な件数）
- 「少し」「いくつか」→ LIMIT 5
- 「全部」「制限なし」→ LIMIT 50（最大）
- 「1つ」「最高」「最安」→ LIMIT 1

例：「売上が高い順に商品を表示して」
→ [
  {{"tool": "list_tables", "description": "テーブル一覧とスキーマ確認"}},
  {{"tool": "execute_safe_query", "params": {{"sql": "SELECT p.name, SUM(s.total_amount) as sales FROM products p JOIN sales s ON p.id = s.product_id GROUP BY p.name ORDER BY sales DESC LIMIT 20"}}, "description": "売上順に商品表示"}}
]
"""
        else:
            max_tasks_note = "1-3個の必要最小限のタスクで構成してください。"
            database_rules = ""

        return f"""ユーザーの要求に対して、適切なタスクリストを生成してください。

## 最近の会話
{context_section}

## ユーザーの要求
{user_query}

## カスタム指示
{custom_section}

## 利用可能なツール
{tools_info}

## 基本指針
{max_tasks_note}
- 計算の場合は演算順序を考慮
- 天気等の単一API呼び出しは1つのタスクで完結

{database_rules}

## 文脈参照の解決（重要）
ユーザーが「この」「その」「さっき」「前の」「生成した」「作成した」「上記の」などの参照を使用している場合：
1. 上記の会話履歴と実行結果から具体的な値を特定して使用
2. 前のタスクの結果を次のタスクで使用する場合、具体的な値として埋め込む
3. 特にPythonコード内では、前の実行結果の実際のデータを直接コードに含める
4. あいまいな参照（"それ"、"あれ"など）は避け、明確な値を設定

## get_weatherツール使用時の重要事項
- 必ずcountry_codeパラメータを指定してください
- 都市名は適切な国コードと組み合わせて使用してください

## データベース操作時の重要事項
- 「データを表示」「一覧を見る」→ まず list_tables でスキーマ確認、次に execute_safe_query でSELECT文を実行
- 「構造を確認」「スキーマを見る」→ list_tables で十分（詳細な構造情報を含む）
- データ表示は必ず2ステップ：list_tables → execute_safe_query

## タスク依存関係の表現
前のタスクの結果を使用する場合は、自然な表現で記述してください：
- `"前のタスクの結果"` - 直前のタスク結果を参照
- `"最初のタスクで取得した都市"` - 特定のタスク結果を参照
- `"計算結果"` - 前の計算結果を参照

例：「データベースのデータ一覧を表示」
```json
{{"tasks": [
  {{"tool": "list_tables", "params": {{}}, "description": "テーブル一覧とスキーマ確認"}},
  {{"tool": "execute_safe_query", "params": {{"sql": "SELECT * FROM products LIMIT 20"}}, "description": "商品データを取得して表示"}}
]}}
```

例：「データベーステーブルを詳しく調査してデータを表示」
```json
{{"tasks": [
  {{"tool": "list_tables", "params": {{}}, "description": "テーブル一覧とスキーマ確認"}},
  {{"tool": "execute_safe_query", "params": {{"sql": "SELECT * FROM products LIMIT 20"}}, "description": "商品データを取得して表示"}}
]}}
```

例：「複数都市の天気を取得」
```json
{{"tasks": [
  {{"tool": "get_weather", "params": {{"city": "City1", "country_code": "XX"}}, "description": "都市1の天気を取得"}},
  {{"tool": "get_weather", "params": {{"city": "City2", "country_code": "YY"}}, "description": "都市2の天気を取得"}}
]}}
```

例：「IPから現在地を調べて天気を取得」
```json
{{"tasks": [
  {{"tool": "get_ip_info", "params": {{}}, "description": "現在のIPアドレスの地理的情報を取得する"}},
  {{"tool": "get_weather", "params": {{"city": "取得した都市名", "country_code": "JP"}}, "description": "取得した都市の現在の天気を取得する"}}
]}}
```

例：「私の年齢に10を足して20を引いて。私の年齢は65歳です。」
```json
{{"tasks": [
  {{"tool": "add", "params": {{"a": 65, "b": 10}}, "description": "年齢65に10を足す"}},
  {{"tool": "subtract", "params": {{"a": "前の計算結果", "b": 20}}, "description": "前の結果から20を引く"}}
]}}
```

## 出力形式
```json
{{"tasks": [
  {{"tool": "ツール名", "params": {{"param": "値"}}, "description": "何をするかの説明"}},
  ...
]}}
```"""