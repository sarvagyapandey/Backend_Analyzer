"""
Advanced backend detectors for patterns that other tools don't catch.

These detect real production problems:
- Data flow issues (user input → database)
- State management bugs
- Concurrency problems
- Resource leaks
- Business logic errors
- Error handling chains
"""
import ast
from typing import List, Set, Tuple
from analyzer.detector_base import BaseDetector
from analyzer.issue import Issue, IssueType, IssueSeverity, IssueLocation


class DataFlowSecurityDetector(BaseDetector):
    """
    Tracks user input → database queries to find injection risks.
    
    Simple English: Finds places where user data goes directly into
    database queries without proper checking.
    """
    
    @property
    def name(self) -> str:
        return "data_flow_security"
    
    @property
    def description(self) -> str:
        return "Detects when user input flows directly to database without protection"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for data flow vulnerabilities."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._trace_user_input(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _trace_user_input(self, tree: ast.AST, filepath: str):
        """Look for patterns like: user_data → SQL without parameterization."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for string formatting in query calls
                if self._is_query_call(node):
                    # Check if using string formatting (dangerous)
                    if self._uses_string_format(node):
                        self.issues.append(Issue(
                            detector_name=self.name,
                            issue_type=IssueType.SECURITY,
                            severity=IssueSeverity.HIGH,
                            title="Database query using string formatting",
                            description="User data mixed into SQL query with string formatting instead of parameterization",
                            location=IssueLocation(filepath, node.lineno),
                            recommendation="Use parameterized queries: db.query('SELECT * FROM users WHERE id = ?', user_id) instead of f-strings",
                            risk_explanation="If someone enters malicious data, they can break out of the query and access unauthorized data or modify the database",
                        ))
    
    def _is_query_call(self, node: ast.Call) -> bool:
        """Check if this looks like a database query call."""
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            return attr in ['query', 'execute', 'find', 'find_one', 'update', 'delete']
        elif isinstance(node.func, ast.Name):
            name = node.func.id
            return name in ['query', 'execute', 'sql']
        return False
    
    def _uses_string_format(self, node: ast.Call) -> bool:
        """Check if query uses f-string or .format()."""
        if not node.args:
            return False
        
        arg = node.args[0]
        
        # Check for f-string
        if isinstance(arg, ast.JoinedStr):
            return True
        
        # Check for .format() calls
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
            if arg.func.attr == 'format':
                return True
        
        return False


class StateManagementDetector(BaseDetector):
    """
    Finds places where code changes global/shared state unsafely.
    
    Simple English: Detects when code modifies shared data that might
    cause unexpected behavior when multiple requests happen at once.
    """
    
    @property
    def name(self) -> str:
        return "state_management"
    
    @property
    def description(self) -> str:
        return "Detects unsafe modification of shared state"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for state management issues."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_global_mutations(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_global_mutations(self, tree: ast.AST, filepath: str):
        """Find unsafe modifications to global/module-level variables."""
        globals_defined = set()
        class_vars = set()
        
        # First pass: collect global definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                for name in node.names:
                    globals_defined.add(name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Module-level assignment
                        if node.col_offset == 0:
                            globals_defined.add(target.id)
        
        # Second pass: find mutations
        for node in ast.walk(tree):
            if isinstance(node, ast.AugAssign):  # +=, -=, etc.
                if isinstance(node.target, ast.Name):
                    if node.target.id in globals_defined:
                        self.issues.append(Issue(
                            detector_name=self.name,
                            issue_type=IssueType.RELIABILITY,
                            severity=IssueSeverity.HIGH,
                            title=f"Unsafe modification of shared state: {node.target.id}",
                            description="Code modifies global state that could cause race conditions when handling concurrent requests",
                            location=IssueLocation(filepath, node.lineno),
                            recommendation="Use local variables instead, or use thread-safe mechanisms like locks",
                            risk_explanation="If two requests run at once and both modify this shared variable, data could get corrupted or lost",
                        ))


class InvalidInputHandlingDetector(BaseDetector):
    """
    Finds functions that don't validate their inputs.
    
    Simple English: Detects when functions accept data from users or
    other systems but don't check if that data is valid before using it.
    """
    
    @property
    def name(self) -> str:
        return "invalid_input"
    
    @property
    def description(self) -> str:
        return "Detects functions that use input without validating it first"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for input validation issues."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_input_validation(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_input_validation(self, tree: ast.AST, filepath: str):
        """Find functions that access parameters without validation."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private/test functions
                if node.name.startswith('_') or node.name.startswith('test'):
                    continue
                
                # Check if function has parameters
                if not node.args.args:
                    continue
                
                # Look for immediate access to parameters without checks
                param_names = {arg.arg for arg in node.args.args}
                
                # Check first few lines for validation
                has_validation = False
                for stmt in node.body[:3]:
                    stmt_code = ast.unparse(stmt) if hasattr(ast, 'unparse') else ''
                    if any(param in stmt_code and ('assert' in stmt_code or 'if' in stmt_code or 'raise' in stmt_code)
                           for param in param_names):
                        has_validation = True
                        break
                
                # If no validation and parameter is accessed with subscript/attribute
                if not has_validation:
                    for stmt in node.body[:5]:
                        for child in ast.walk(stmt):
                            if isinstance(child, (ast.Subscript, ast.Attribute)):
                                if isinstance(child.value, ast.Name) and child.value.id in param_names:
                                    self.issues.append(Issue(
                                        detector_name=self.name,
                                        issue_type=IssueType.RELIABILITY,
                                        severity=IssueSeverity.MEDIUM,
                                        title=f"Parameter used without validation in {node.name}()",
                                        description=f"Function receives data but accesses it immediately without checking if it's valid",
                                        location=IssueLocation(filepath, node.lineno),
                                        recommendation="Add validation at start of function: check types, check None, check length",
                                        risk_explanation="If bad data gets in, the program crashes with confusing errors instead of rejecting it cleanly",
                                    ))
                                    return


class ErrorHandlingChainDetector(BaseDetector):
    """
    Detects broken error handling chains.
    
    Simple English: Finds code that catches errors but then loses
    important information about what went wrong.
    """
    
    @property
    def name(self) -> str:
        return "error_handling"
    
    @property
    def description(self) -> str:
        return "Detects error handling that loses important failure information"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for error handling issues."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_error_handling(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_error_handling(self, tree: ast.AST, filepath: str):
        """Find error handling that silently swallows exceptions."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Check exception handlers
                for handler in node.handlers:
                    # Check if handler body is empty or just pass
                    if not handler.body or (len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)):
                        self.issues.append(Issue(
                            detector_name=self.name,
                            issue_type=IssueType.RELIABILITY,
                            severity=IssueSeverity.HIGH,
                            title="Silent error handling - errors get swallowed",
                            description="Code catches errors but does nothing with them, making debugging impossible",
                            location=IssueLocation(filepath, handler.lineno),
                            recommendation="Always log the error or re-raise it: except Error as e: logger.error(f'Something went wrong: {e}')",
                            risk_explanation="When something breaks in production, nobody knows because the error just disappears silently",
                        ))
                    
                    # Check for bare except (catches everything)
                    if handler.type is None:
                        self.issues.append(Issue(
                            detector_name=self.name,
                            issue_type=IssueType.RELIABILITY,
                            severity=IssueSeverity.MEDIUM,
                            title="Bare except clause catches all errors including system exits",
                            description="Using 'except:' catches ALL errors, even ones you shouldn't catch like KeyboardInterrupt",
                            location=IssueLocation(filepath, handler.lineno),
                            recommendation="Catch specific exceptions: except ValueError as e: or except (KeyError, TypeError) as e:",
                            risk_explanation="Your code might catch errors that mean 'stop and shut down' and accidentally keep running",
                        ))


class ResourceLeakDetector(BaseDetector):
    """
    Finds resources that are opened but might not be closed.
    
    Simple English: Detects when code opens files, databases, or
    connections but doesn't guarantee they'll be closed even if
    something goes wrong.
    """
    
    @property
    def name(self) -> str:
        return "resource_leak"
    
    @property
    def description(self) -> str:
        return "Detects files/connections opened without guaranteed cleanup"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for resource leaks."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_resource_handling(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_resource_handling(self, tree: ast.AST, filepath: str):
        """Find resources opened without with statement."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for open(), connect(), etc.
                call_name = None
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                
                if call_name in ['open', 'connect', 'Connection', 'Session']:
                    # Check if it's inside a with statement
                    parent_is_with = False
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.With):
                            for item in parent.items:
                                if item.context_expr == node:
                                    parent_is_with = True
                                    break
                    
                    if not parent_is_with:
                        self.issues.append(Issue(
                            detector_name=self.name,
                            issue_type=IssueType.RELIABILITY,
                            severity=IssueSeverity.MEDIUM,
                            title="Resource opened without guaranteed cleanup",
                            description=f"'{call_name}' called without using 'with' statement - might leak if error occurs",
                            location=IssueLocation(filepath, node.lineno),
                            recommendation="Use 'with' statement: with open(file) as f: or with db.connect() as conn:",
                            risk_explanation="If an error happens in your code, the file/connection stays open forever and the system runs out of resources",
                        ))


class BusinessLogicDetector(BaseDetector):
    """
    Finds suspicious patterns in business logic.
    
    Simple English: Detects code that looks like it might have bugs
    based on common mistakes developers make.
    """
    
    @property
    def name(self) -> str:
        return "business_logic"
    
    @property
    def description(self) -> str:
        return "Detects suspicious patterns that often indicate bugs"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze for business logic issues."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_logic_patterns(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_logic_patterns(self, tree: ast.AST, filepath: str):
        """Find suspicious logic patterns."""
        for node in ast.walk(tree):
            # Pattern: object compared with ==
            if isinstance(node, ast.Compare):
                for op, comparator in zip(node.ops, node.comparators):
                    if isinstance(op, ast.Eq):
                        # Check if comparing objects (not primitives)
                        if isinstance(comparator, ast.Name):
                            if comparator.id.startswith('obj') or comparator.id.endswith('_obj'):
                                self.issues.append(Issue(
                                    detector_name=self.name,
                                    issue_type=IssueType.DESIGN,
                                    severity=IssueSeverity.MEDIUM,
                                    title="Comparing objects with == instead of 'is'",
                                    description="Using == to compare objects checks if they're identical, not if they're equal",
                                    location=IssueLocation(filepath, node.lineno),
                                    recommendation="Use 'is' for object identity check: if obj1 is obj2: or define __eq__ method",
                                    risk_explanation="Two different objects with same data will be treated as different, causing unexpected behavior",
                                ))
            
            # Pattern: division by zero possible
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                # Check if divisor is a variable (not a constant)
                if isinstance(node.right, ast.Name):
                    self.issues.append(Issue(
                        detector_name=self.name,
                        issue_type=IssueType.RELIABILITY,
                        severity=IssueSeverity.MEDIUM,
                        title="Division without checking for zero",
                        description="Dividing by a variable that could be zero - program will crash",
                        location=IssueLocation(filepath, node.lineno),
                        recommendation="Check before dividing: if divisor != 0: result = numerator / divisor",
                        risk_explanation="If someone or something passes zero, your program crashes with a cryptic error",
                    ))
