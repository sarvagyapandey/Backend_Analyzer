"""
Refactored AST analysis engine using modular detector system.
"""
import os
from typing import Any, Dict, List, Optional
from analyzer.detector_manager import DetectorManager
from analyzer.discovery import BackendDiscoveryEngine
from analyzer.functional_testing import FunctionalTestRunner
from analyzer.integrations import IntegrationManager
from analyzer.intelligence import BackendIntelligenceLayer
from analyzer.report import AnalysisReport, ReportPrinter
from analyzer.issue import Issue


class AnalysisEngine:
    """
    Main analysis engine orchestrating all detectors, integrations, and intelligence layers.
    """
    
    # Directories to skip during analysis
    SKIP_DIRS = {
        'venv', 'env', '.venv', '.env',
        '__pycache__', '.git', '.github',
        'node_modules', 'dist', 'build',
        '.pytest_cache', '.tox', 'eggs',
        '.egg-info', '.mypy_cache', '.ruff_cache',
        '.vscode', '.idea', 'htmlcov',
        'site-packages', '.cache',
    }
    
    def __init__(self):
        """Initialize analysis engine with all detectors and integrations."""
        self.detector_manager = DetectorManager()
        self.discovery_engine = BackendDiscoveryEngine()
        self.integration_manager = IntegrationManager()
        self.functional_test_runner = FunctionalTestRunner()
        self.all_issues: List[Issue] = []
    
    def _should_skip_dir(self, dirpath: str) -> bool:
        """Check if directory should be skipped."""
        # Get the directory name
        dir_name = os.path.basename(dirpath)
        
        # Skip if matches skip list
        if dir_name in self.SKIP_DIRS:
            return True
        
        # Skip hidden directories (but not the root)
        if dir_name.startswith('.') and dir_name != '.':
            return True
        
        # Skip if it looks like a venv/virtualenv
        if os.path.exists(os.path.join(dirpath, 'pyvenv.cfg')):
            return True
        
        if os.path.exists(os.path.join(dirpath, 'activate')):
            parent = os.path.dirname(dirpath)
            if dir_name in ('bin', 'Scripts'):  # Common venv activation dirs
                return True
        
        return False
    
    def analyze_file(self, filepath: str) -> List[Issue]:
        """
        Analyze a single Python file using custom detectors and external tools.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            List of issues found in the file
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            print(f"Cannot read file {filepath}: {e}")
            return []
        
        # Run custom detectors
        issues = self.detector_manager.run_all(filepath, code)
        
        # Run external tool integrations (Bandit, Flake8, etc.)
        if filepath.endswith('.py'):
            integration_issues = self.integration_manager.run_integrations(filepath)
            issues.extend(integration_issues)
        
        self.all_issues.extend(issues)
        return issues
    
    def analyze_directory(self, dirpath: str) -> List[Issue]:
        """
        Recursively analyze all Python files in a directory.
        
        Skips:
        - Virtual environments (venv, env, .venv)
        - Cache directories (__pycache__, .pytest_cache, etc.)
        - Version control (.git, .github)
        - Node modules and other non-Python
        
        Args:
            dirpath: Path to directory
            
        Returns:
            List of all issues found
        """
        self.all_issues = []
        
        print(f"🔍 Looking at code in: {dirpath}")
        
        for root, dirs, files in os.walk(dirpath):
            # Remove directories that should be skipped (modifies dirs in-place)
            dirs[:] = [d for d in dirs if not self._should_skip_dir(os.path.join(root, d))]
            
            for filename in files:
                if filename.endswith('.py'):
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, dirpath)
                    print(f"  Checking: {rel_path}")
                    self.analyze_file(filepath)
        
        return self.all_issues
    
    def generate_report(self) -> AnalysisReport:
        """Generate analysis report from collected issues."""
        report = AnalysisReport(self.all_issues)
        
        # Add intelligence layer insights
        intelligence = BackendIntelligenceLayer(self.all_issues)
        report.intelligence = intelligence.generate_insights()
        
        return report

    def analyze_path(
        self,
        path: str,
        functional_config: Optional[str] = None,
        functional_tests: Optional[List[Dict[str, Any]]] = None,
        functional_base_url: str = "",
        functional_defaults: Optional[Dict[str, Any]] = None,
        functional_source_label: str = "Functional Test Builder",
    ) -> Optional[AnalysisReport]:
        """
        Analyze a file or directory and return a structured report.

        Args:
            path: File or directory path to analyze
            functional_config: Optional JSON config for live REST/GraphQL tests
            functional_tests: Optional live tests built from the GUI
            functional_base_url: Base URL used by GUI-built tests
            functional_defaults: Default request options for GUI-built tests
            functional_source_label: Label shown in the report for GUI-built tests

        Returns:
            AnalysisReport when the path is valid, otherwise None
        """
        if os.path.isfile(path):
            self.all_issues = []
            self.analyze_file(path)
        elif os.path.isdir(path):
            self.analyze_directory(path)
        else:
            print(f"Sorry, {path} is not real file or folder")
            return None

        report = self.generate_report()
        report.backend_discovery = self.discovery_engine.discover(path)

        if functional_config:
            functional_summary = self.functional_test_runner.run_config(functional_config)
            report.functional_summary = functional_summary
            report.functional_issues = functional_summary.to_issues()
            report.health_score = report._calculate_health_score()
            report.intelligence = BackendIntelligenceLayer(report.issues + report.functional_issues).generate_insights()
        elif functional_tests:
            functional_summary = self.functional_test_runner.run_tests(
                functional_tests,
                base_url=functional_base_url,
                defaults=functional_defaults,
                source_label=functional_source_label,
            )
            report.functional_summary = functional_summary
            report.functional_issues = functional_summary.to_issues()
            report.health_score = report._calculate_health_score()
            report.intelligence = BackendIntelligenceLayer(report.issues + report.functional_issues).generate_insights()

        return report


def run_analysis(
    path: str,
    functional_config: Optional[str] = None,
    functional_tests: Optional[List[Dict[str, Any]]] = None,
    functional_base_url: str = "",
    functional_defaults: Optional[Dict[str, Any]] = None,
    functional_source_label: str = "Functional Test Builder",
):
    """
    Run complete analysis on a file or directory.
    
    Args:
        path: File or directory path to analyze
        functional_config: Optional JSON config for live functional API tests
    """
    engine = AnalysisEngine()
    report = engine.analyze_path(
        path,
        functional_config=functional_config,
        functional_tests=functional_tests,
        functional_base_url=functional_base_url,
        functional_defaults=functional_defaults,
        functional_source_label=functional_source_label,
    )
    if report is not None:
        ReportPrinter.print_report(report)
