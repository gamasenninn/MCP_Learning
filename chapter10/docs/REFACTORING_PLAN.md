# MCP Agent Refactoring Plan
**Chapter10 リファクタリング指示書 - LLM通信一元化計画**

生成日: 2025-09-06  
最終更新: 2025-09-06  
基づく分析: chapter10 コードレビュー結果（総合評価 86/100）+ LLM使用箇所全体調査

## 📊 現状分析

### コードベース概要
- **現在の規模**: mcp_agent.py 737行（過大なファイル）
- **LLM使用の散在**: 5つのクラスがLLMを直接使用
- **主要な問題点**:
  - LLM通信ロジックの重複と散在
  - テスタビリティの課題（複数箇所でのモック化が必要）
  - モデル切り替えの困難性
  - API呼び出しの統計・監視の不備

### LLM使用箇所の詳細分析
| クラス | 使用箇所 | 用途 | 行数 |
|--------|----------|------|------|
| MCPAgent | 3箇所 | 実行判定、タスク生成、結果解釈 | 175行 |
| TaskExecutor | 1箇所 | パラメータ解決 | 25行 |
| ErrorHandler | 2箇所 | エラー修正、回復戦略 | 35行 |
| TaskManager | 0箇所 | **未使用**（削除対象） | - |
| **合計** | 6箇所 | | **235行** |

### アーキテクチャ評価
- **優れた点**: 責任分離、設定管理、テストカバレッジ
- **改善点**: LLM通信の重複、モック化の複雑性、モデル切り替えの困難

## 🎯 リファクタリング方針

### ✅ **Priority 1: LLMInterface統一化（最優先）**
- **効果**: 235行のLLM関連コードを一元管理
- **価値**: 極めて高い
- **削減**: mcp_agent.py 175行削減（24%）

### 🔄 **Future Phase: ClarificationHandler分離**
- **効果**: 95行削減（13%）
- **価値**: 中程度
- **位置付け**: LLMInterface完成後の改善項目

### ❌ **推奨しない分離**
**ResultProcessor**: MCPAgentのコア機能として保持
**ExecutionEngine**: エージェントの存在意義そのもの

**理由**: LLMInterface一元化により十分な効果が得られるため、過度な分離は不要

## 🏗️ 詳細設計

### Priority 1: LLMInterface統一化

#### ファイル構造（簡素化）
```
chapter10/
├── llm_interface.py    # 新規 - 約250行
├── mcp_agent.py        # 修正 - 562行（175行削減）
├── task_executor.py    # 修正 - LLMInterface経由に変更
├── error_handler.py    # 修正 - LLMInterface経由に変更
└── task_manager.py     # 修正 - 不要なLLM参照を削除
```

#### LLMInterfaceクラス設計（包括版）
```python
class LLMInterface:
    """全LLM通信の統一インターフェース"""
    
    def __init__(self, config: Config, logger: Logger)
    
    # ===== MCPAgent用メソッド =====
    async def determine_execution_type(self, user_query: str, 
                                      recent_context: str, 
                                      tools_info: str) -> Dict
    
    async def generate_task_list(self, user_query: str, 
                                context: str, 
                                tools_info: str, 
                                custom_instructions: str = "") -> List[Dict]
    
    async def interpret_results(self, user_query: str,
                               results: List[Dict],
                               context: str,
                               custom_instructions: str = "") -> str
    
    # ===== TaskExecutor用メソッド =====  
    async def resolve_task_parameters(self, task: TaskState, 
                                     context: List[Dict], 
                                     tools_info: str,
                                     user_query: str) -> Dict
    
    # ===== ErrorHandler用メソッド =====
    async def fix_error_parameters(self, tool: str, 
                                  params: Dict, 
                                  error_msg: str, 
                                  tools_info: str,
                                  user_query: str = "") -> Optional[Dict]
    
    async def generate_error_recovery_plan(self, error_context: Dict,
                                          user_query: str,
                                          attempt_count: int) -> Dict
    
    # ===== 共通内部メソッド =====
    def _get_model_params(self, **kwargs) -> Dict
    async def _call_llm_json(self, prompt: str, temperature: float, 
                            fallback: Optional[Dict] = None) -> Dict
    async def _call_llm_text(self, prompt: str, temperature: float) -> str
    def _log_api_call(self, method: str, tokens_used: int = 0)
```

#### 移行対象メソッドと影響範囲

| ファイル | 移行メソッド | 新メソッド |
|---------|-------------|-----------|
| **mcp_agent.py** | `_get_llm_params` | `_get_model_params` |
| | `_determine_execution_type` | `determine_execution_type` |
| | `_generate_task_list_with_retry` + `_generate_unified_task_list` | `generate_task_list` |
| | `_generate_interpretation_response` | `interpret_results` |
| **task_executor.py** | `resolve_parameters_with_llm` の一部 | `resolve_task_parameters` |
| **error_handler.py** | `fix_params_with_llm` | `fix_error_parameters` |
| | `handle_and_retry` の一部 | `generate_error_recovery_plan` |
| **task_manager.py** | `llm_client` 参照 | **削除** |

#### 各クラスの変更詳細

**1. MCPAgent の変更**
```python
class MCPAgent:
    def __init__(self, config_path: str = "config.yaml"):
        # 変更前
        # self.llm = AsyncOpenAI()
        
        # 変更後
        self.llm_interface = LLMInterface(self.config, self.logger)
        
        # 他のマネージャーにもLLMInterfaceを渡す
        self.error_handler = ErrorHandler(
            config=self.config,
            llm_interface=self.llm_interface,  # 変更
            verbose=self.config.development.verbose
        )
        
        self.task_executor = TaskExecutor(
            # task_manager は llm を受け取らなくなる
            task_manager=self.task_manager,
            llm_interface=self.llm_interface,  # 追加
            # llm=self.llm 削除
            # ... その他のパラメータ
        )
    
    async def _determine_execution_type(self, user_query: str) -> Dict:
        """実行方式判定（LLMInterfaceに委譲）"""
        recent_context = self.conversation_manager.get_recent_context(include_results=False)
        tools_info = self.connection_manager.format_tools_for_llm()
        
        result = await self.llm_interface.determine_execution_type(
            user_query, recent_context, tools_info
        )
        
        # 結果の正規化処理はMCPAgentに残す
        if result.get('type') not in ['NO_TOOL', 'CLARIFICATION']:
            result['type'] = 'TOOL'
        
        self.logger.ulog(f"判定: {result.get('type')}", "info:classification")
        return result
```

**2. TaskExecutor の変更**
```python  
class TaskExecutor:
    def __init__(self, 
                 task_manager: TaskManager,
                 # ... 他のパラメータ
                 llm_interface: LLMInterface,  # 追加
                 # llm: AsyncOpenAI,  # 削除
                 verbose: bool = True):
        # self.llm = llm  # 削除
        self.llm_interface = llm_interface  # 追加
    
    async def resolve_parameters_with_llm(self, task: TaskState, execution_context: List[Dict]) -> Dict:
        """LLMInterfaceを使用するよう変更"""
        # 既存のプロンプト生成ロジックは保持
        # LLM呼び出し部分のみ変更
        return await self.llm_interface.resolve_task_parameters(
            task, execution_context, tools_info, self.current_user_query
        )
```

**3. ErrorHandler の変更**
```python
class ErrorHandler:
    def __init__(self, config: Config, 
                 llm_interface: Optional[LLMInterface] = None,  # 変更
                 verbose: bool = True):
        self.llm_interface = llm_interface  # 変更
        # self.llm = llm  # 削除
    
    async def fix_params_with_llm(self, tool: str, params: Dict, 
                                 error_msg: str, tools_info: str) -> Optional[Dict]:
        """LLMInterfaceを使用するよう変更"""
        if not self.llm_interface:
            return None
            
        return await self.llm_interface.fix_error_parameters(
            tool, params, error_msg, tools_info, self.current_user_query
        )
```

**4. TaskManager の変更**
```python
class TaskManager:
    def __init__(self, state_manager: StateManager):
        # llm_client パラメータを削除
        self.state_manager = state_manager
        # self.llm_client = llm_client  # 削除
```

### Future Phase: ClarificationHandler分離（参考）

**注意**: この段階はLLMInterface完成後の将来的な改善項目です。

#### ファイル構造
```
chapter10/
├── llm_interface.py           # Priority 1で実装済み
├── clarification_handler.py  # Future Phase
└── mcp_agent.py              # さらなる削減
```

#### 期待効果（参考値）
- **追加削減**: mcp_agent.py から95行削除
- **最終的な mcp_agent.py**: 467行（元の737行から37%削減）

## 📋 実装手順（Priority 1: LLMInterface統一化）

### Step 1: 準備作業
1. 既存テストのバックアップ作成
2. LLM関連の現在の動作を記録
3. 依存関係マップの確認

### Step 2: LLMInterface実装
1. **`chapter10/llm_interface.py` を作成**
   - LLMInterfaceクラスの基本構造
   - 共通メソッド（_get_model_params, _call_llm_json, _call_llm_text）
   
2. **MCPAgent用メソッド実装**
   - `determine_execution_type`
   - `generate_task_list`  
   - `interpret_results`

3. **TaskExecutor/ErrorHandler用メソッド実装**
   - `resolve_task_parameters`
   - `fix_error_parameters`
   - `generate_error_recovery_plan`

### Step 3: 各クラスの修正
1. **MCPAgent 修正**
   - LLMInterface初期化
   - LLM関連メソッドを削除し委譲に変更
   - 他のマネージャーへのLLMInterface注入

2. **TaskExecutor 修正**
   - コンストラクタ変更（llm→llm_interface）
   - `resolve_parameters_with_llm`をLLMInterface呼び出しに変更

3. **ErrorHandler 修正**  
   - コンストラクタ変更（llm→llm_interface）
   - エラー修正メソッドをLLMInterface呼び出しに変更

4. **TaskManager 修正**
   - 不要なllm_client参照を削除

### Step 4: テスト修正と検証
1. **テストのモック変更**
   - AsyncOpenAIのモック→LLMInterfaceのモック
   - 各テストファイルの修正
   
2. **段階的検証**
   - LLMInterface単体テスト
   - MCPAgent統合テスト
   - 全機能テストの実行

### Step 5: 最終検証
1. **機能テスト**
   - 既存172テストの成功確認
   - REPLコマンドの動作確認
   - エンドツーエンドテストの実行

2. **品質確認**
   - コード削減量の確認（mcp_agent.py 175行削除）
   - パフォーマンステスト
   - メモリ使用量の確認

## 📊 期待される効果（Priority 1完了時）

### 定量的効果
| 指標 | 変更前 | 変更後 | 改善 |
|------|--------|--------|------|
| **mcp_agent.py行数** | 737行 | **562行** | **-24%** |
| **LLM通信の集約度** | 5クラスに分散 | **100%集約** | ✅ |
| **テストのモック化** | 5箇所で困難 | **1箇所で簡単** | ✅ |
| **LLM関連コード** | 235行分散 | **250行集約** | ✅ |

### 質的効果（Priority 1）
- **統一インターフェース**: 全LLM通信が単一クラスで管理
- **テスタビリティ向上**: LLMInterfaceをモック化するだけで全テスト対応
- **モデル切り替えの容易さ**: 1箇所の変更でGPT-4↔GPT-5↔Claude等の切り替え
- **監視・統計収集**: API呼び出し回数、トークン使用量、応答時間の一元管理
- **エラーハンドリング統一**: LLM関連エラーの一元処理

### 将来的なメリット（実装後すぐに実現）
- **🔄 マルチモデル対応**: 
  ```python
  # 設定変更だけでモデル切り替え可能
  config.llm.model = "gpt-5-mini"  # or "claude-3", "gemini-pro"
  ```

- **📊 統計・監視**: 
  ```python
  # API使用量の自動追跡
  llm_interface.get_usage_stats()  # 呼び出し回数、トークン数等
  ```

- **🧪 A/Bテスト**: 
  ```python
  # 異なるプロンプト戦略の比較が容易
  result_a = await llm_interface.generate_task_list(query, strategy="conservative")
  result_b = await llm_interface.generate_task_list(query, strategy="creative")
  ```

- **⚡ キャッシング**: 
  ```python
  # LLM応答の自動キャッシュ（実装容易）
  @lru_cache(maxsize=100)
  async def cached_llm_call(prompt_hash): ...
  ```

## ⚠️ 注意事項とリスク管理

### 実装時の注意点（Priority 1）
1. **段階的実装**: LLMInterface→各クラス修正→テスト修正の順で慎重に進行
2. **既存動作の維持**: LLM呼び出しのパラメータ・結果が既存と同じになるよう注意
3. **テスト先行修正**: 各クラス修正前にテストのモック戦略を先に修正
4. **エラーハンドリング**: LLMInterface内でのエラーハンドリングを適切に設計

### 重要なリスクと対策
| リスク | 対策 | 優先度 |
|--------|------|--------|
| **LLM応答の変化** | 既存のパラメータ・プロンプト形式を厳密に維持 | 🔴 高 |
| **テスト大量失敗** | LLMInterfaceの段階的実装とモック戦略の事前準備 | 🔴 高 |
| **パフォーマンス劣化** | LLMInterface呼び出しのオーバーヘッド最小化 | 🟡 中 |
| **依存性注入の複雑化** | コンストラクタの変更を最小限に抑制 | 🟡 中 |

### 失敗時のロールバック戦略
1. **Git ブランチ管理**: `feature/llm-interface-refactor` で作業
2. **チェックポイント**: 各Stepの完了時にコミット
3. **テスト基準**: 既存172テストが全て成功することを確認
4. **自動化**: CI/CDでテスト失敗時の自動アラート

## 🎯 成功指標（Priority 1完了基準）

### ✅ 必須達成項目
- [ ] **`llm_interface.py`の完成**: 250行程度で全LLM通信を集約
- [ ] **全既存テストが成功**: 172テスト中172テスト成功
- [ ] **mcp_agent.py削減**: 737行→562行（175行削除）
- [ ] **LLM通信の一元化**: 5クラス→1クラス（LLMInterface）に集約
- [ ] **既存REPLコマンド動作**: 全コマンドが正常動作
- [ ] **エンドツーエンドテスト**: 計算・データベース・確認フローが正常動作

### 📊 品質指標
- [ ] **パフォーマンス維持**: LLM応答時間が既存と同等（±10%以内）
- [ ] **メモリ使用量**: 既存と同等（モジュール分離による増加なし）
- [ ] **テストカバレッジ**: LLMInterface 90%以上のカバレッジ
- [ ] **コード品質**: pylintスコア 8.0以上

### 🧪 機能検証項目
- [ ] **実行タイプ判定**: NO_TOOL/CLARIFICATION/TOOL の正確な判定
- [ ] **タスクリスト生成**: 複雑なタスクの適切な分解
- [ ] **結果解釈**: 実行結果の自然な日本語解釈
- [ ] **パラメータ解決**: TaskExecutorでの動的パラメータ解決
- [ ] **エラー修正**: ErrorHandlerでのLLMベース修正

### 🚀 拡張性検証（実装後すぐにテスト可能）
- [ ] **モデル切り替え**: `gpt-4o-mini` ↔ `gpt-5-mini` の動作確認
- [ ] **統計収集**: API呼び出し回数・トークン使用量の正確な記録
- [ ] **新メソッド追加**: LLMInterfaceに新機能を追加する容易さ

### 📈 長期的な成功指標（3ヶ月後評価）
- [ ] **新LLMモデル対応**: 1日以内での新モデル対応
- [ ] **開発効率向上**: LLM関連機能追加時間の50%短縮
- [ ] **バグ修正効率**: LLM関連バグの修正時間30%短縮
- [ ] **テスト作成効率**: LLM関連テストの作成時間60%短縮

---

## 📝 実装チェックリスト

### Phase 1 完了確認
```
□ Step 1: 準備作業完了
□ Step 2: LLMInterface基本実装完了  
□ Step 3: 全クラス修正完了
□ Step 4: テスト修正・実行完了
□ Step 5: 最終検証完了

□ 成功指標の全項目クリア
□ ドキュメント更新（README.md等）
□ GitタグによるVersion管理
```

**この指示書に基づく実装により、LLM通信の完全な一元化と大幅なコード改善を実現します。**