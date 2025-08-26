# 逐次適応型実行アーキテクチャ移行計画

## 背景と動機

### 現在の問題
- **プレースホルダー機能の冗長性**: `_resolve_placeholders()`（48行）が複雑
- **事前計画型の制約**: タスクリストを先に決めて後から置換する設計
- **LLMの能力活用不足**: 各ステップで文脈を理解し判断できるのに、機械的な置換に依存

### 設計思想の転換
**現在**: 事前計画 → 実行 → 結果置換
**新方式**: 結果を見て → 次を動的決定 → より人間的な思考

## アーキテクチャ比較

### 現在（事前計画型）
```
1. _determine_execution_type()      # LLM呼び出し①
2. _generate_adaptive_task_list()   # LLM呼び出し②
3. Task1実行 → _judge_and_process_result()  # LLM呼び出し③
4. Task2実行 → _judge_and_process_result()  # LLM呼び出し④
5. _interpret_planned_results()     # LLM呼び出し⑤

合計: 5回のLLM呼び出し + 48行のプレースホルダー処理
```

### 新方式（逐次適応型）
```
1. _determine_execution_type()      # LLM呼び出し①
2. Task1決定・実行・判定           # LLM呼び出し②（統合）
3. Task2決定・実行・判定           # LLM呼び出し③（統合）
4. _interpret_final_results()       # LLM呼び出し④

合計: 4回のLLM呼び出し（プレースホルダー不要）
```

## 詳細実装計画

### Phase 1: ハイブリッド実装（リスク低）

既存機能を残しつつ、新方式を設定で切り替え可能に。

```python
class MCPAgentV4:
    async def process_request(self, user_query: str):
        execution_type = await self._determine_execution_type(user_query)
        
        if execution_type == "NO_TOOL":
            return execution_result.get("response")
        elif self.config.get("execution", {}).get("adaptive_mode", False):
            # 新方式: 逐次実行
            return await self._execute_adaptive(user_query)
        else:
            # 既存: タスクリスト方式
            return await self._execute_with_tasklist(user_query)
```

**config.yaml追加**:
```yaml
execution:
  adaptive_mode: false  # テスト時にtrueに変更
  max_steps: 10         # 無限ループ防止
```

### Phase 2: 新メソッド実装

#### 2-1. メインロジック
```python
async def _execute_adaptive(self, user_query: str) -> str:
    """逐次適応型実行エンジン"""
    execution_context = []
    max_steps = self.config.get("execution", {}).get("max_steps", 10)
    
    self.display.show_analysis("適応型実行開始...")
    
    for step in range(max_steps):
        # 次のアクション決定
        decision = await self._decide_and_execute_next(
            user_query=user_query,
            execution_context=execution_context,
            step_num=step + 1
        )
        
        # 完了チェック
        if decision["is_complete"]:
            if decision.get("completion_message"):
                return decision["completion_message"]
            break
        
        # アクション実行
        if decision["needs_action"]:
            self.display.show_step_start(step + 1, "?", decision["description"])
            
            result = await self._execute_tool_with_retry(
                tool=decision["tool"],
                params=decision["params"],  # 実際の値（プレースホルダーなし）
                description=decision["description"]
            )
            
            execution_context.append({
                "step": step + 1,
                "tool": decision["tool"],
                "params": decision["params"],
                "result": result,
                "success": True,
                "description": decision["description"],
                "reasoning": decision.get("reasoning", "")
            })
            
            self.display.show_step_complete(decision["description"], 0, success=True)
    
    # 最終解釈
    return await self._interpret_adaptive_results(user_query, execution_context)
```

#### 2-2. 決定エンジン
```python
async def _decide_and_execute_next(
    self, 
    user_query: str,
    execution_context: List[Dict],
    step_num: int
) -> Dict:
    """次のアクションを動的決定"""
    
    prompt = self._build_adaptive_decision_prompt(
        user_query=user_query,
        execution_context=execution_context,
        step_num=step_num
    )
    
    try:
        response = await self.llm.chat.completions.create(
            model=self.config["llm"]["model"],
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        decision = json.loads(response.choices[0].message.content)
        self.logger.info(f"[適応判断] Step {step_num}: {decision.get('reasoning', 'N/A')}")
        
        return decision
        
    except Exception as e:
        self.logger.error(f"[適応判断エラー] {e}")
        return {"is_complete": True, "completion_message": f"判断エラー: {e}"}
```

#### 2-3. プロンプト設計
```python
def _build_adaptive_decision_prompt(
    self, 
    user_query: str, 
    execution_context: List[Dict], 
    step_num: int
) -> str:
    """適応的決定用プロンプト生成"""
    
    # 文脈整理
    context_str = ""
    if execution_context:
        context_str = "## これまでの実行結果\n"
        for ctx in execution_context:
            context_str += f"Step {ctx['step']}: {ctx['tool']}({ctx['params']}) → {safe_str(ctx['result'])[:200]}\n"
            if ctx.get('reasoning'):
                context_str += f"  理由: {ctx['reasoning']}\n"
    else:
        context_str = "## これまでの実行結果\n（まだ実行なし）"
    
    # ツール情報
    tools_info = self.connection_manager.format_tools_for_llm()
    
    # カスタム指示
    custom_section = self.custom_instructions if self.custom_instructions.strip() else "なし"
    
    return f"""あなたは適応型実行エンジンです。ユーザーの要求を達成するため、現在の状況を分析し次のアクションを決定してください。

## ユーザーの要求
{user_query}

{context_str}

## カスタム指示
{custom_section}

## 利用可能なツール
{tools_info}

## 判断基準
1. **完了判定**: ユーザーの要求は既に達成されたか？
2. **次のアクション**: 達成されていない場合、次に必要な具体的なツールは？
3. **パラメータ決定**: 前の結果を使う場合、実際の値を入力（プレースホルダー禁止）

## 重要な注意
- データベース操作は必ず3ステップ: list_tables → get_table_schema → execute_safe_query
- 前の結果の具体的な値を使う（例: "Tokyo"、"150"など）
- プレースホルダー（{{xxx}}）は使わない

## 出力形式（JSON）
{{
    "is_complete": boolean,  // 要求達成済みか
    "completion_message": "達成メッセージ（完了時のみ）",
    "needs_action": boolean,  // 次のアクション必要か
    "tool": "ツール名（アクション時のみ）",
    "params": {{"実際の値"}},  // 具体的な値のみ
    "description": "何をするかの説明",
    "reasoning": "なぜこのアクションを選んだか"
}}

例: 前回の結果で都市が"Tokyo"なら、params: {{"city": "Tokyo"}} とする"""
```

### Phase 3: テストと調整

#### 3-1. 簡単なタスクテスト
- 「100 + 200を計算」
- 「現在時刻を教えて」

#### 3-2. 複雑なタスクテスト
- 「IPから現在地を調べて天気を取得」
- 「データベースから商品一覧を表示」

#### 3-3. エラーケーステスト
- 無限ループ防止
- LLM判断エラー時の挙動

### Phase 4: 移行判定

#### 成功判定基準
- [ ] 全ての既存テストケースが通る
- [ ] LLM呼び出し回数が同等以下
- [ ] 実行時間が同等以下
- [ ] エラー処理が適切

#### 成功時のクリーンアップ
- `_resolve_placeholders()` 削除（48行）
- `_execute_with_tasklist()` 削除
- タスクリスト関連コード削除

## リスク分析

### 低リスク（対策済み）
1. **ロールバック**: config切り替えで即座に元に戻せる
2. **段階的移行**: 既存機能を残したまま新機能追加
3. **LLM呼び出し**: 回数は増えない（むしろ減る）

### 中リスク（要注意）
1. **LLMの一貫性**
   - **リスク**: 各ステップで判断がブレる
   - **対策**: プロンプトに全体目標と文脈を明記

2. **無限ループ**
   - **リスク**: is_completeが出ない
   - **対策**: max_steps制限（10回）

3. **デバッグ情報**
   - **リスク**: 事前計画がないので予測困難
   - **対策**: reasoning付きで各判断を詳細ログ

### 高リスク（慎重に）
1. **複雑なタスクでの品質**
   - **リスク**: DB操作の3ステップルール忘れ
   - **対策**: プロンプトに明示的ルール記載

2. **パフォーマンス**
   - **リスク**: LLM判断の遅延
   - **対策**: 温度0.1で高速化、タイムアウト設定

## メリット・デメリット比較

| 観点 | 現在（事前計画型） | 新方式（逐次実行型） | 判定 |
|------|-------------------|---------------------|------|
| コード量 | 多い（プレースホルダー等） | 少ない（-100行以上） | ✅新方式 |
| LLM呼び出し | 5回（2タスク時） | 4回以下 | ✅新方式 |
| 柔軟性 | 低い（計画固定） | 高い（動的変更可） | ✅新方式 |
| 予測可能性 | 高い（計画が見える） | 低い（実行まで不明） | ⚠️現在 |
| デバッグ | 中（複雑な依存） | 易（各ステップ独立） | ✅新方式 |
| エラー回復 | 難（計画再生成） | 易（次で修正） | ✅新方式 |
| 学習コスト | 中（プレースホルダー） | 低（自然な流れ） | ✅新方式 |

## 実装スケジュール

### 今日（推奨）
- [x] 計画書作成
- [ ] Phase 1: config追加・分岐ロジック（30分）
- [ ] Phase 2: 新メソッド基本実装（1時間）

### 明日以降
- [ ] Phase 3: テストケース作成・実行（30分）
- [ ] Phase 4: 1週間運用テスト
- [ ] 移行判定・クリーンアップ

## 予想される効果

### 短期効果
- コード量：-100行以上削減
- 複雑性：プレースホルダー機構削除
- バグ修正：依存関係の単純化

### 長期効果
- 保守性：より直感的なコード
- 拡張性：新しいツール追加が容易
- 理解性：人間の思考に近い処理フロー

## 結論

**この移行は挑戦的だが、大幅なアーキテクチャ改善になる可能性が高い。**

段階的なアプローチとロールバック計画により、リスクを最小化しながら、より良いシステムへの進化が期待できる。

---

*作成日: 2025-08-25*  
*作成者: Claude Code Refactoring Team*