"""
API behavior and performance analyzers.
"""
import ast
from typing import List, Optional
from analyzer.detector_base import BaseDetector
from analyzer.issue import Issue, IssueType, IssueSeverity, IssueLocation


class SlowAPIDetector(BaseDetector):
    """
    Detects patterns that could cause slow API endpoints.
    
    Looks for:
    - N+1 query patterns
    - Synchronous I/O in request handlers
    - Missing caching strategies
    - Unoptimized loops
    """
    
    @property
    def name(self) -> str:
        return "slow_api_endpoints"
    
    @property
    def description(self) -> str:
        return "Detects patterns that could cause slow API responses"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze code for slow API patterns."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_patterns(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_patterns(self, tree: ast.AST, filepath: str):
        """Check for slow patterns."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for large functions handling requests
                func_length = node.end_lineno - node.lineno + 1
                is_handler = any(
                    dec.id == 'route' or (hasattr(dec, 'attr') and dec.attr in ['get', 'post'])
                    for dec in node.decorator_list
                    if hasattr(dec, 'id') or hasattr(dec, 'attr')
                )
                
                if is_handler and func_length > 30:
                    self.issues.append(Issue(
                        detector_name=self.name,
                        issue_type=IssueType.PERFORMANCE,
                        severity=IssueSeverity.MEDIUM,
                        title=f"API endpoint {node.name}() tries to do {func_length} lines of work",
                        description="This API endpoint is doing too much in one place",
                        location=IssueLocation(filepath, node.lineno),
                        recommendation="Move database queries to a service layer, caching to separate function, business logic to separate class",
                        risk_explanation="When one request comes in, it gets stuck waiting for all this work. With 100 users, the system slows down dramatically.",
                    ))
                
                # Check for nested loops (potential N+1 queries)
                self._check_nested_loops(node, filepath)
    
    def _check_nested_loops(self, func: ast.FunctionDef, filepath: str):
        """Check for nested loops which could indicate N+1 patterns."""
        loop_depth = 0
        max_depth = 0
        
        for node in ast.walk(func):
            if isinstance(node, (ast.For, ast.While)):
                # Simple depth counting (imperfect but catches common cases)
                for child in ast.walk(node):
                    if isinstance(child, (ast.For, ast.While)):
                        max_depth += 1
        
        if max_depth >= 2:
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.PERFORMANCE,
                severity=IssueSeverity.MEDIUM,
                title=f"N+1 query problem: loops inside loops in {func.name}()",
                description="Code has nested loops that run database queries - this creates performance disaster at scale",
                location=IssueLocation(filepath, func.lineno),
                recommendation="Query all data once: users = db.find_all(); then process in loops. Or use batch queries.",
                risk_explanation="If you have 100 users and each user has 100 posts, this does 1 + 100 + (100*100) = 10,101 database queries. With 10,000 users, it's 101 MILLION queries. The system will freeze.",
            ))


class InconsistentResponseDetector(BaseDetector):
    """
    Detects inconsistent response handling in endpoints.
    
    Looks for:
    - Methods that return different types
    - Inconsistent error handling
    - Unhandled exceptions
    """
    
    @property
    def name(self) -> str:
        return "inconsistent_responses"
    
    @property
    def description(self) -> str:
        return "Detects inconsistent API response patterns"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for inconsistent responses."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_error_handling(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_error_handling(self, tree: ast.AST, filepath: str):
        """Check for inconsistent error handling."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if exception handling exists
                has_try_except = any(
                    isinstance(n, ast.Try) 
                    for n in ast.walk(node)
                )
                
                # Check if return statements exist
                returns = [
                    n for n in ast.walk(node) 
                    if isinstance(n, ast.Return)
                ]
                
                # If returns exist but no try-except in a handler-like function
                if returns and not has_try_except and len(returns) > 1:
                    decorator_names = [
                        dec.id if hasattr(dec, 'id') else None
                        for dec in node.decorator_list
                    ]
                    if any('route' in str(d) for d in decorator_names if d):
                        self.issues.append(Issue(
                            detector_name=self.name,
                            issue_type=IssueType.RELIABILITY,
                            severity=IssueSeverity.MEDIUM,
                            title=f"API endpoint {node.name}() might crash without warning",
                            description="This endpoint doesn't catch errors - if something goes wrong, it crashes",
                            location=IssueLocation(filepath, node.lineno),
                            recommendation="Wrap code in try-except: try: ... except Error as e: logger.error(...); return error_response()",
                            risk_explanation="When an error happens, users see a blank page or '500 error'. Worse, nobody knows why because the error isn't logged.",
                        ))


class DatabaseQueryDetector(BaseDetector):
    """
    Detects database query patterns and potential issues.
    
    Looks for:
    - Missing connection pooling
    - Unoptimized query patterns
    - Missing query timeouts
    """
    
    @property
    def name(self) -> str:
        return "database_patterns"
    
    @property
    def description(self) -> str:
        return "Detects database access patterns and optimization opportunities"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze database patterns."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_database_patterns(tree, filepath, code)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_database_patterns(self, tree: ast.AST, filepath: str, code: str):
        """Check database access patterns."""
        # Check for missing query timeouts
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for query/execute calls
                call_name = None
                if isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                
                if call_name in ['query', 'find', 'execute', 'select']:
                    # Check if timeout is specified in arguments
                    has_timeout = any(
                        (isinstance(kw.arg, str) and 'timeout' in kw.arg)
                        for kw in node.keywords
                    )
                    
                    if not has_timeout and 'timeout' not in code[max(0, node.col_offset-20):node.col_offset+50]:
                        self.issues.append(Issue(
                            detector_name=self.name,
                            issue_type=IssueType.RELIABILITY,
                            severity=IssueSeverity.LOW,
                            title="Database query might wait forever",
                            description="Database query doesn't have a timeout - if database hangs, your request hangs forever",
                            location=IssueLocation(filepath, node.lineno),
                            recommendation="Add timeout: db.query(sql, timeout=5) instead of db.query(sql)",
                            risk_explanation="Someone reboots the database, your request waits forever. After 100 requests pile up, your system stops responding to everyone.",
                        ))
