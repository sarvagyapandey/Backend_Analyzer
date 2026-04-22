"""
Framework-agnostic detectors for functional and unit test risks.

Works with:
- Any backend framework (Django, FastAPI, Flask, DRF, etc.)
- Any database type (PostgreSQL, MongoDB, MySQL, Redis, DynamoDB, etc.)
- Any API type (REST, GraphQL)
"""
import ast
from typing import List
from analyzer.detector_base import BaseDetector
from analyzer.issue import Issue, IssueType, IssueSeverity, IssueLocation


class FunctionalRiskDetector(BaseDetector):
    """
    Detects functional risks - things that break at runtime.
    
    Works with any framework/database/API type.
    """
    
    @property
    def name(self) -> str:
        return "functional_risks"
    
    @property
    def description(self) -> str:
        return "Detects functional risks that break at runtime"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for functional risks."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_functional_issues(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_functional_issues(self, tree: ast.AST, filepath: str):
        """Find functional issues that break at runtime."""
        for node in ast.walk(tree):
            # List/dict access without bounds checking
            if isinstance(node, ast.Subscript):
                self._check_subscript_safety(node, filepath)
            
            # Function calls that might fail
            if isinstance(node, ast.Call):
                self._check_call_safety(node, filepath, code="")
    
    def _check_subscript_safety(self, node: ast.Subscript, filepath: str):
        """Check for unsafe list/dict indexing."""
        # Check if accessing with magic number or key
        if isinstance(node.slice, ast.Constant):
            # Direct index like [0] or [1] - could be out of bounds
            pass
        elif isinstance(node.slice, ast.Name):
            # Variable index without bounds check
            pass
    
    def _check_call_safety(self, node: ast.Call, filepath: str, code: str):
        """Check for calls that might fail."""
        # Check for .get() on non-optional values
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            # .json() on request without checking content-type
            if attr in ['json', 'decode']:
                if not node.keywords:
                    self.issues.append(Issue(
                        detector_name=self.name,
                        issue_type=IssueType.RELIABILITY,
                        severity=IssueSeverity.MEDIUM,
                        title="Unsafe .json() or .decode() without error handling",
                        description="Calling .json() or .decode() without try-except will crash on invalid data",
                        location=IssueLocation(filepath, node.lineno),
                        recommendation="Wrap in try-except: try: data = request.json() except ValueError: return error_response()",
                        risk_explanation="User sends invalid JSON → .json() crashes → 500 error instead of 400 bad request",
                    ))


class UnitTestRiskDetector(BaseDetector):
    """
    Detects code that's hard to unit test.
    
    Identifies patterns that make testing difficult or impossible.
    """
    
    @property
    def name(self) -> str:
        return "unit_test_risks"
    
    @property
    def description(self) -> str:
        return "Detects code patterns that are hard or impossible to unit test"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for unit test risks."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_test_risks(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_test_risks(self, tree: ast.AST, filepath: str):
        """Find code that's hard to test."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._check_function_testability(node, filepath)
    
    def _check_function_testability(self, func: ast.FunctionDef, filepath: str):
        """Check if function is testable."""
        # Function directly imports and uses external services
        has_external_calls = False
        has_io = False
        has_random = False
        
        for child in ast.walk(func):
            # Calls to known external services
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    attr = child.func.attr
                    if attr in ['open', 'requests', 'urllib', 'socket']:
                        has_io = True
            
            # Calls to random
            if isinstance(child, ast.Name):
                if child.id in ['random', 'uuid', 'time']:
                    has_random = True
        
        # Function directly talks to database/API (not testable)
        if has_io:
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.DESIGN,
                severity=IssueSeverity.MEDIUM,
                title=f"Function {func.name}() directly uses I/O (not testable)",
                description="Function directly opens files, makes requests, accesses network - impossible to unit test without hitting real services",
                location=IssueLocation(filepath, func.lineno),
                recommendation="Inject dependencies: def process(data, db, logger) instead of db.query() inside the function",
                risk_explanation="Unit tests must hit real database/files/API. Tests are slow, fragile, and fail when services are down.",
            ))
        
        # Function uses randomness (non-deterministic, hard to test)
        if has_random:
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.DESIGN,
                severity=IssueSeverity.LOW,
                title=f"Function {func.name}() uses randomness (flaky tests)",
                description="Function calls random/uuid/time - tests will be non-deterministic and fail randomly",
                location=IssueLocation(filepath, func.lineno),
                recommendation="Pass random/time as dependency: def generate_id(random_gen) or mock.patch time in tests",
                risk_explanation="Test passes sometimes, fails sometimes. Team can't trust test results.",
            ))


class DataValidationRiskDetector(BaseDetector):
    """
    Detects missing data validation at boundaries.
    
    Works with any framework/API type (REST, GraphQL, etc.)
    """
    
    @property
    def name(self) -> str:
        return "data_validation"
    
    @property
    def description(self) -> str:
        return "Detects missing validation at API boundaries"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for validation risks."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_validation_risks(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_validation_risks(self, tree: ast.AST, filepath: str):
        """Find missing validation."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function looks like an endpoint/resolver
                if self._is_endpoint_or_handler(node):
                    self._check_endpoint_validation(node, filepath)
    
    def _is_endpoint_or_handler(self, func: ast.FunctionDef) -> bool:
        """Check if function is likely an API endpoint or GraphQL resolver."""
        # Has decorators (FastAPI, Django, etc.)
        if func.decorator_list:
            return True
        
        # Named like a handler/resolver
        name = func.name.lower()
        if any(x in name for x in ['handle', 'process', 'resolve', 'fetch', 'get_', 'create_', 'update_', 'delete_']):
            return True
        
        return False
    
    def _check_endpoint_validation(self, func: ast.FunctionDef, filepath: str):
        """Check validation in endpoint."""
        # Get parameter names
        params = {arg.arg for arg in func.args.args if arg.arg != 'self'}
        
        if not params:
            return
        
        # Check if parameters are validated in function body
        body_code = '\n'.join(ast.unparse(stmt) for stmt in func.body[:5])
        
        for param in params:
            if param in ['self', 'cls']:
                continue
            
            # Check if parameter is validated
            has_validation = any(
                check in body_code
                for check in [f'if {param}', f'if not {param}', f'assert {param}', f'validate({param})', f'{param} or']
            )
            
            if not has_validation and len(func.body) > 0:
                # Parameter used without validation
                for stmt in func.body[:3]:
                    for child in ast.walk(stmt):
                        if isinstance(child, (ast.Subscript, ast.Attribute)):
                            if isinstance(child.value, ast.Name) and child.value.id == param:
                                self.issues.append(Issue(
                                    detector_name=self.name,
                                    issue_type=IssueType.RELIABILITY,
                                    severity=IssueSeverity.HIGH,
                                    title=f"User input not validated in {func.name}()",
                                    description="API receives external data but uses it without validation",
                                    location=IssueLocation(filepath, func.lineno),
                                    recommendation="Validate at start: if not param or not isinstance(param, expected_type): raise ValueError(...)",
                                    risk_explanation="Attacker sends unexpected data → program crashes or behaves wrong → 500 error",
                                ))
                                return


class APIFrameworkAgnosticDetector(BaseDetector):
    """
    Detects API-specific risks in a framework-agnostic way.
    
    Works with:
    - REST APIs (any framework)
    - GraphQL (any implementation)
    - Any HTTP API
    """
    
    @property
    def name(self) -> str:
        return "api_risks"
    
    @property
    def description(self) -> str:
        return "Detects API-specific risks regardless of framework"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for API risks."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_api_risks(tree, filepath, code)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_api_risks(self, tree: ast.AST, filepath: str, code: str):
        """Find API-level risks."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._check_response_handling(node, filepath)
                self._check_pagination(node, filepath, code)
    
    def _check_response_handling(self, func: ast.FunctionDef, filepath: str):
        """Check if function handles multiple response types."""
        # Look for multiple return statements with different types
        returns = []
        for node in ast.walk(func):
            if isinstance(node, ast.Return):
                returns.append(node)
        
        if len(returns) > 2:
            # Multiple returns = inconsistent response format
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.DESIGN,
                severity=IssueSeverity.MEDIUM,
                title=f"Inconsistent responses in {func.name}()",
                description="Function returns different response formats from different paths",
                location=IssueLocation(filepath, func.lineno),
                recommendation="Always return same structure: {'data': ..., 'error': None} or {'data': None, 'error': ...}",
                risk_explanation="API clients can't handle responses consistently. Causes crashes in frontend code.",
            ))
    
    def _check_pagination(self, func: ast.FunctionDef, filepath: str, code: str):
        """Check for missing pagination on potentially large queries."""
        func_code = ast.unparse(func) if hasattr(ast, 'unparse') else ''
        
        # Check if function queries/fetches data
        has_query_or_find = 'query' in func_code or 'find' in func_code or 'select' in func_code
        
        # Check if has LIMIT or pagination
        has_pagination = any(
            x in func_code.lower()
            for x in ['limit', 'skip', 'offset', 'page', 'per_page', 'take']
        )
        
        if has_query_or_find and not has_pagination and len(func.body) > 5:
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.PERFORMANCE,
                severity=IssueSeverity.MEDIUM,
                title=f"No pagination in {func.name}() - could return all records",
                description="Function queries data without pagination - could return millions of records",
                location=IssueLocation(filepath, func.lineno),
                recommendation="Add limit/offset: query.limit(100).skip(offset) or pass page_size parameter",
                risk_explanation="Someone requests all data → API returns 1 million records → memory explodes → API crashes",
            ))


class DatabaseAgnosticRiskDetector(BaseDetector):
    """
    Detects database-related risks that work with ANY database type.
    
    Works with:
    - SQL (PostgreSQL, MySQL, SQLite, etc.)
    - NoSQL (MongoDB, DynamoDB, etc.)
    - Key-value (Redis, Memcached)
    - Any database library (SQLAlchemy, Mongoose, PyMongo, etc.)
    """
    
    @property
    def name(self) -> str:
        return "database_agnostic"
    
    @property
    def description(self) -> str:
        return "Detects database risks regardless of database type or library"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for database risks."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_db_risks(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_db_risks(self, tree: ast.AST, filepath: str):
        """Find database-level risks."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                self._check_db_call(node, filepath)
            elif isinstance(node, ast.FunctionDef):
                self._check_transaction_handling(node, filepath)
    
    def _check_db_call(self, node: ast.Call, filepath: str):
        """Check any database operation call."""
        call_name = None
        if isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            call_name = node.func.id
        
        if call_name is None:
            return
        
        # Generic database operation patterns
        db_patterns = {
            'find', 'query', 'search', 'get', 'fetch',
            'insert', 'save', 'create', 'put', 'post',
            'update', 'delete', 'remove',
            'execute', 'commit', 'rollback',
            'aggregate', 'map', 'reduce',
        }
        
        if call_name in db_patterns:
            # Check for parameterization in string operations
            if node.args:
                arg = node.args[0]
                if isinstance(arg, ast.JoinedStr):  # f-string
                    self.issues.append(Issue(
                        detector_name=self.name,
                        issue_type=IssueType.SECURITY,
                        severity=IssueSeverity.HIGH,
                        title="Database query using string formatting",
                        description="User data mixed into query with f-string instead of parameterization",
                        location=IssueLocation(filepath, node.lineno),
                        recommendation="Use parameterized queries: db.query('... WHERE id = ?', [user_id])",
                        risk_explanation="Attacker can inject malicious query code to steal/modify data",
                    ))
    
    def _check_transaction_handling(self, func: ast.FunctionDef, filepath: str):
        """Check transaction handling."""
        has_transaction = False
        has_error_handling = False
        
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                call_name = ''
                if isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    call_name = node.func.id
                
                if call_name in ['begin', 'transaction', 'begin_nested']:
                    has_transaction = True
            
            if isinstance(node, ast.Try):
                has_error_handling = True
        
        # If has transaction but no rollback on error
        if has_transaction and not has_error_handling:
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.RELIABILITY,
                severity=IssueSeverity.MEDIUM,
                title=f"Transaction without error handling in {func.name}()",
                description="Database transaction opened but no try-except to rollback on error",
                location=IssueLocation(filepath, func.lineno),
                recommendation="Use try-finally: try: db.begin() ... finally: db.rollback() if error",
                risk_explanation="On error, transaction locks rows forever. Other requests hang waiting for locks.",
            ))
