"""
Higher-level backend intelligence that correlates multiple signals.

This is where we provide unique value: instead of individual issues,
we correlate signals to identify backend-specific problems.

Examples:
- slow_endpoint + large_function + missing_validation → "Unoptimized request handler"
- eval_usage + user_input → "Code injection risk via eval()"
- nested_loops + database_query → "N+1 query performance disaster"
"""
from typing import List, Dict, Set
from analyzer.issue import Issue, IssueType, IssueSeverity


class CorrelationAnalyzer:
    """
    Correlates multiple issues to identify patterns and backend-specific risks.
    """
    
    def __init__(self, issues: List[Issue]):
        """Initialize with collected issues."""
        self.issues = issues
        self.correlations: List[Dict] = []
    
    def analyze(self) -> List[Dict]:
        """
        Run correlation analysis to find connected issues.
        
        Returns:
            List of correlation patterns discovered
        """
        self.correlations = []
        
        self._find_slow_endpoint_patterns()
        self._find_security_input_chains()
        self._find_reliability_cascades()
        
        return self.correlations
    
    def _find_slow_endpoint_patterns(self):
        """
        Correlation: slow_endpoint + large_function + missing_validation
        
        Indicates: Unoptimized request handler doing too much
        """
        slow_endpoints = [
            i for i in self.issues 
            if i.issue_type == IssueType.PERFORMANCE
        ]
        
        large_functions = [
            i for i in self.issues 
            if i.issue_type == IssueType.DESIGN and 'Large' in i.title
        ]
        
        missing_validation = [
            i for i in self.issues 
            if 'validation' in i.title.lower()
        ]
        
        # If multiple of these are in same file, we have a pattern
        slow_files = {i.location.filepath for i in slow_endpoints}
        large_files = {i.location.filepath for i in large_functions}
        validation_files = {i.location.filepath for i in missing_validation}
        
        intersect = slow_files & large_files
        if intersect:
            self.correlations.append({
                'type': 'slow_endpoint_architecture',
                'severity': 'high',
                'pattern': 'API is slow - function is trying to do too many things at once',
                'affected_files': list(intersect),
                'issue_count': len(slow_endpoints) + len(large_functions),
                'recommendation': "Move database work to separate functions. Use caching. Make functions smaller. Each should do one thing.",
            })
    
    def _find_security_input_chains(self):
        """
        Correlation: eval/exec + user_input + missing_validation
        
        Indicates: Code injection risk
        """
        dangerous_calls = [
            i for i in self.issues 
            if 'eval' in i.title.lower() or 'exec' in i.title.lower()
        ]
        
        missing_validation = [
            i for i in self.issues 
            if 'validation' in i.title.lower() or 'type hint' in i.title.lower()
        ]
        
        danger_files = {i.location.filepath for i in dangerous_calls}
        validation_files = {i.location.filepath for i in missing_validation}
        
        intersect = danger_files & validation_files
        if intersect:
            self.correlations.append({
                'type': 'code_injection_risk',
                'severity': 'critical',
                'pattern': 'DANGER - Attackers can run their code on your server - MUST FIX NOW',
                'affected_files': list(intersect),
                'issue_count': len(dangerous_calls) + len(missing_validation),
                'recommendation': 'FIX THIS NOW: Never use eval() or exec(). Always check user input. Use json.loads(). Add type hints.',
            })
    
    def _find_reliability_cascades(self):
        """
        Correlation: unhandled_exceptions + database_issues + missing_timeouts
        
        Indicates: Service reliability issues under load
        """
        unhandled = [
            i for i in self.issues 
            if i.issue_type == IssueType.RELIABILITY and 'exception' in i.title.lower()
        ]
        
        db_issues = [
            i for i in self.issues 
            if 'timeout' in i.title.lower() or 'query' in i.title.lower()
        ]
        
        if len(unhandled) >= 2 and len(db_issues) >= 2:
            self.correlations.append({
                'type': 'reliability_cascade',
                'severity': 'high',
                'pattern': 'Many problems together - system will break when many people use it',
                'affected_count': len(unhandled) + len(db_issues),
                'recommendation': 'Catch and log every error. Add time limits to database calls. Test with many users together.',
            })


class BackendIntelligenceLayer:
    """
    Synthesizes individual detections into backend-level insights.
    
    This is the unique value proposition:
    - Not just listing issues, but explaining system impact
    - Correlating signals for higher-level understanding
    - Focusing on what matters for production backends
    """
    
    def __init__(self, issues: List[Issue]):
        """Initialize with issues."""
        self.issues = issues
    
    def generate_insights(self) -> Dict:
        """Generate higher-level insights."""
        insights = {
            'reliability': self._analyze_reliability(),
            'scalability': self._analyze_scalability(),
            'security': self._analyze_security(),
            'maintainability': self._analyze_maintainability(),
            'correlations': self._analyze_correlations(),
        }
        
        return insights
    
    def _analyze_reliability(self) -> Dict:
        """Analyze what could cause service crashes."""
        reliability_issues = [
            i for i in self.issues 
            if i.issue_type in [IssueType.RELIABILITY, IssueType.FUNCTIONAL, IssueType.ARCHITECTURE]
        ]
        
        # Group by file to show specific locations
        by_file = {}
        for issue in reliability_issues:
            fname = issue.location.filepath
            if fname not in by_file:
                by_file[fname] = []
            by_file[fname].append(issue.title)
        
        file_list = ", ".join([f"{f} ({len(titles)} issues)" for f, titles in by_file.items()])
        
        return {
            'risk_level': 'high' if len(reliability_issues) > 3 else 'medium' if reliability_issues else 'low',
            'issue_count': len(reliability_issues),
            'affected_files': file_list,
            'examples': [i.title for i in reliability_issues[:3]],
            'summary': f"Your system can stop working in {len(reliability_issues)} different ways. Files with problems: {file_list if file_list else 'None'}",
        }
    
    def _analyze_scalability(self) -> Dict:
        """Analyze what limits throughput."""
        perf_issues = [
            i for i in self.issues 
            if i.issue_type == IssueType.PERFORMANCE
        ]
        
        design_issues = [
            i for i in self.issues 
            if i.issue_type == IssueType.DESIGN and ('Large' in i.title or 'loop' in i.title.lower())
        ]
        
        # Show specific functions that are slow
        slow_functions = [i.title for i in perf_issues]
        
        return {
            'risk_level': 'high' if len(perf_issues) > 3 else 'medium' if perf_issues else 'low',
            'bottleneck_count': len(perf_issues),
            'slow_functions': slow_functions[:5],
            'summary': f"With 100 users it will be slow. With 1000 users it will stop. Slow spots: {', '.join(slow_functions[:3]) if slow_functions else 'None found'}",
        }
    
    def _analyze_security(self) -> Dict:
        """Analyze attack surface."""
        security_issues = [
            i for i in self.issues 
            if i.issue_type == IssueType.SECURITY
        ]
        
        vuln_types = list(set([i.title for i in security_issues]))
        
        return {
            'risk_level': 'critical' if any(i.severity == IssueSeverity.HIGH for i in security_issues) else 'medium' if security_issues else 'low',
            'vulnerability_count': len(security_issues),
            'vulnerability_types': vuln_types[:5],
            'summary': f"Bad guys can: steal your data, control the system, delete files. Problems: {', '.join(vuln_types[:3]) if vuln_types else 'None found'}",
        }
    
    def _analyze_maintainability(self) -> Dict:
        """Analyze code quality and debugging difficulty."""
        design_issues = [
            i for i in self.issues 
            if i.issue_type == IssueType.DESIGN
        ]
        
        # Show top problem types
        issues_list = [i.title for i in design_issues]
        
        return {
            'complexity_score': max(0, 100 - len(design_issues) * 5),
            'issue_count': len(design_issues),
            'top_issues': issues_list[:5],
            'summary': f"Code is messy and hard to change. Top problems: {', '.join(issues_list[:3]) if issues_list else 'None'}",
        }
    
    def _analyze_correlations(self) -> List[Dict]:
        """Analyze correlated issues."""
        analyzer = CorrelationAnalyzer(self.issues)
        return analyzer.analyze()
