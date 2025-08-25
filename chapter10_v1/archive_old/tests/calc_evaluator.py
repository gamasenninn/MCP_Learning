#!/usr/bin/env python3
"""
計算式評価ツール
複雑な数式を一度に評価
"""

from fastmcp import FastMCP
import ast
import operator

# MCPサーバーを作成
mcp = FastMCP("Calculator Evaluator")

# 安全な演算子のマッピング
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

class SafeEvaluator(ast.NodeVisitor):
    """安全な数式評価クラス"""
    
    def visit_BinOp(self, node):
        """二項演算を評価"""
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = SAFE_OPERATORS.get(type(node.op))
        if op:
            return op(left, right)
        raise ValueError(f"サポートされていない演算子: {type(node.op).__name__}")
    
    def visit_UnaryOp(self, node):
        """単項演算を評価"""
        operand = self.visit(node.operand)
        op = SAFE_OPERATORS.get(type(node.op))
        if op:
            return op(operand)
        raise ValueError(f"サポートされていない演算子: {type(node.op).__name__}")
    
    def visit_Constant(self, node):
        """定数を返す"""
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"数値以外の定数は許可されていません: {type(node.value).__name__}")
    
    def visit_Num(self, node):
        """数値を返す（後方互換性）"""
        return node.n
    
    def generic_visit(self, node):
        """その他のノードは許可しない"""
        raise ValueError(f"許可されていない構文: {type(node).__name__}")

@mcp.tool()
def evaluate_expression(expression: str) -> float:
    """数式を安全に評価します。
    
    基本的な四則演算（+, -, *, /）と括弧、べき乗（**）をサポート。
    例: "100 + 200 + 4 * 50", "(100 + 200) * 2", "2 ** 8"
    """
    try:
        # 式を解析
        tree = ast.parse(expression, mode='eval')
        
        # 安全性チェック
        evaluator = SafeEvaluator()
        result = evaluator.visit(tree.body)
        
        return float(result)
    except SyntaxError as e:
        raise ValueError(f"無効な式: {e}")
    except Exception as e:
        raise ValueError(f"評価エラー: {e}")

@mcp.tool()
def evaluate_with_steps(expression: str) -> dict:
    """数式を評価し、計算過程も返します。
    
    括弧の優先順位に従って計算の手順を示します。
    """
    try:
        # まず結果を計算
        tree = ast.parse(expression, mode='eval')
        evaluator = SafeEvaluator()
        result = evaluator.visit(tree.body)
        
        # 計算の優先順位を説明
        steps = []
        
        # 括弧があるかチェック
        if '(' in expression:
            steps.append("括弧内を優先的に計算")
        
        # 演算子の優先順位
        if '*' in expression or '/' in expression:
            steps.append("乗算・除算を先に計算")
        
        if '+' in expression or '-' in expression:
            steps.append("加算・減算を計算")
        
        return {
            "expression": expression,
            "result": result,
            "steps": steps,
            "description": f"{expression} = {result}"
        }
        
    except Exception as e:
        return {
            "expression": expression,
            "error": str(e),
            "result": None
        }

if __name__ == "__main__":
    # テスト実行
    print("計算式評価サーバー起動")
    mcp.run()