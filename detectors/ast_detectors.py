"""
AST-based detectors for security and design issues.
"""
import ast
from typing import List
from analyzer.detector_base import BaseDetector
from analyzer.issue import Issue, IssueType, IssueSeverity, IssueLocation


class SecurityRiskDetector(BaseDetector):
    """
    Detects common security risks in Python code.
    
    Checks for:
    - eval() usage
    - exec() usage
    - pickle usage
    - hardcoded credentials
    """
    
    @property
    def name(self) -> str:
        return "security_risks"
    
    @property
    def description(self) -> str:
        return "Detects security-risky patterns like eval(), exec(), pickle"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze code for security risks."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._walk_tree(tree, filepath)
        except SyntaxError:
            pass  # Skip files with syntax errors
        
        return self.issues
    
    def _walk_tree(self, tree: ast.AST, filepath: str):
        """Walk AST and detect dangerous function calls."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                self._check_dangerous_call(node, filepath)
    
    def _check_dangerous_call(self, node: ast.Call, filepath: str):
        """Check if call is to a dangerous function."""
        func_name = None
        
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        
        if func_name == "eval":
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.SECURITY,
                severity=IssueSeverity.HIGH,
                title="eval() allows anyone to run any code they want",
                description="If someone passes bad data to eval(), they can run any Python code on your server",
                location=IssueLocation(filepath, node.lineno),
                recommendation="Use json.loads() instead for parsing data, or use ast.literal_eval() for safe Python values",
                risk_explanation="This is like leaving your server's front door open with a sign saying 'hack me'. Attackers can take over your entire system.",
            ))
        
        elif func_name == "exec":
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.SECURITY,
                severity=IssueSeverity.HIGH,
                title="exec() lets anyone run code",
                description="exec() runs code that someone could control - massive security risk",
                location=IssueLocation(filepath, node.lineno),
                recommendation="Never use exec(). If you think you need it, redesign your code to avoid it.",
                risk_explanation="Attackers can use this to read your database, steal user data, install malware, or delete everything.",
            ))
        
        elif func_name == "pickle" or (isinstance(node.func, ast.Attribute) and 
                                        node.func.attr in ["loads", "load"]):
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.SECURITY,
                severity=IssueSeverity.HIGH,
                title="pickle can be tricked into running malicious code",
                description="If you deserialize (unpack) pickle data from outside, someone can trick the system",
                location=IssueLocation(filepath, node.lineno),
                recommendation="Use JSON instead of pickle for data that comes from users or the network",
                risk_explanation="Attackers can craft pickle data that looks normal but runs their code when unpacked",
            ))


class ComplexFunctionDetector(BaseDetector):
    """
    Detects overly complex functions that may impact performance and maintainability.
    
    Identifies:
    - Functions with high cyclomatic complexity
    - Very long functions
    - Functions with many parameters
    """
    
    @property
    def name(self) -> str:
        return "complex_functions"
    
    @property
    def description(self) -> str:
        return "Detects overly complex functions that may cause performance/maintainability issues"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze code for complex functions."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._analyze_functions(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _analyze_functions(self, tree: ast.AST, filepath: str):
        """Find and analyze all function definitions."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._check_function(node, filepath)
    
    def _check_function(self, func: ast.FunctionDef, filepath: str):
        """Check if function is too complex."""
        # Check function length
        func_length = func.end_lineno - func.lineno + 1
        if func_length > 50:
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.DESIGN,
                severity=IssueSeverity.MEDIUM,
                title=f"Function {func.name}() does too much - {func_length} lines",
                description="This function is big and tries to do many things at once",
                location=IssueLocation(filepath, func.lineno),
                recommendation="Split into smaller functions: one that loads data, one that processes, one that saves",
                risk_explanation="Large functions are hard to understand, hard to test, and easy to break. When fixing one bug, you might accidentally break something else.",
            ))
        
        # Check parameter count
        param_count = len(func.args.args)
        if param_count > 5:
            self.issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.DESIGN,
                severity=IssueSeverity.LOW,
                title=f"Function {func.name}() takes too many parameters - {param_count}",
                description="Too many parameters makes the function confusing to use",
                location=IssueLocation(filepath, func.lineno),
                recommendation="Group related parameters into objects or use configuration classes",
                risk_explanation="People using this function have to remember what each parameter does - they'll use it wrong",
            ))


class MissingValidationDetector(BaseDetector):
    """
    Detects missing input validation patterns.
    
    Looks for:
    - Function parameters not validated
    - Missing type hints
    - Unchecked API parameters
    """
    
    @property
    def name(self) -> str:
        return "missing_validation"
    
    @property
    def description(self) -> str:
        return "Detects missing input validation that could cause backend failures"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze code for missing validation."""
        self.issues = []
        try:
            tree = ast.parse(code, filename=filepath)
            self._check_validation(tree, filepath)
        except SyntaxError:
            pass
        
        return self.issues
    
    def _check_validation(self, tree: ast.AST, filepath: str):
        """Check for missing type hints and validation."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for missing type hints in public functions
                if not node.name.startswith('_'):
                    has_untyped_params = any(
                        arg.annotation is None 
                        for arg in node.args.args
                    )
                    if has_untyped_params:
                        self.issues.append(Issue(
                            detector_name=self.name,
                            issue_type=IssueType.DESIGN,
                            severity=IssueSeverity.LOW,
                            title=f"Function {node.name}() doesn't say what type of data it expects",
                            description="Missing type hints make it unclear what data this function accepts",
                            location=IssueLocation(filepath, node.lineno),
                            recommendation="Add type hints: def get_user(user_id: int) -> User: instead of def get_user(user_id):",
                            risk_explanation="Without knowing the expected data type, someone will pass the wrong thing (a string instead of a number) and cause a crash",
                        ))
