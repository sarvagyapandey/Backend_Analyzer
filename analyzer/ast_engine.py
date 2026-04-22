# analyzer/ast_engine.py
"""Legacy compatibility module - use engine.py instead"""

from analyzer.engine import run_analysis as run_ast_analysis

__all__ = ['run_ast_analysis']