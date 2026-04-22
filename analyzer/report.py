"""
Unified reporting system for backend analysis results.
"""
from typing import List, Dict
from collections import defaultdict
from analyzer.issue import Issue, IssueSeverity, IssueType
from analyzer.discovery import BackendDiscovery


class HealthScore:
    """Backend health score breakdown."""
    
    def __init__(self):
        self.security_score = 100
        self.performance_score = 100
        self.design_score = 100
        self.reliability_score = 100
    
    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score."""
        scores = [
            self.security_score * 0.35,      # 35% weight
            self.performance_score * 0.30,   # 30% weight
            self.design_score * 0.20,        # 20% weight
            self.reliability_score * 0.15,   # 15% weight
        ]
        return sum(scores)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "overall": round(self.overall_score, 1),
            "security": round(self.security_score, 1),
            "performance": round(self.performance_score, 1),
            "design": round(self.design_score, 1),
            "reliability": round(self.reliability_score, 1),
        }


class AnalysisReport:
    """
    Unified analysis report combining all detected issues.
    
    Organizes issues by type/severity and provides health scoring.
    """
    
    def __init__(self, issues: List[Issue]):
        """Initialize report with issues."""
        self.issues = sorted(issues)  # Sort by severity
        self.functional_issues: List[Issue] = []
        self.health_score = self._calculate_health_score()
        self.intelligence = None  # Set by engine after report creation
        self.functional_summary = None  # Set by engine when live API tests run
        self.backend_discovery = BackendDiscovery()
    
    def _calculate_health_score(self) -> HealthScore:
        """Calculate health scores based on issues."""
        score = HealthScore()
        
        # Deduct points for each issue
        penalty_by_severity = {
            IssueSeverity.HIGH: 15,
            IssueSeverity.MEDIUM: 8,
            IssueSeverity.LOW: 3,
        }
        
        by_type = defaultdict(list)
        for issue in self.issues:
            by_type[issue.issue_type].append(issue)
        
        # Apply penalties
        for issue in self.issues:
            penalty = penalty_by_severity[issue.severity]
            
            if issue.issue_type == IssueType.SECURITY:
                score.security_score = max(0, score.security_score - penalty)
            elif issue.issue_type == IssueType.PERFORMANCE:
                score.performance_score = max(0, score.performance_score - penalty)
            elif issue.issue_type == IssueType.DESIGN:
                score.design_score = max(0, score.design_score - penalty)
            elif issue.issue_type == IssueType.RELIABILITY:
                score.reliability_score = max(0, score.reliability_score - penalty)
            elif issue.issue_type == IssueType.FUNCTIONAL:
                score.reliability_score = max(0, score.reliability_score - penalty)
        
        return score
    
    def get_issues_by_type(self) -> Dict[IssueType, List[Issue]]:
        """Group issues by type."""
        by_type = defaultdict(list)
        for issue in self.issues:
            by_type[issue.issue_type].append(issue)
        return dict(by_type)
    
    def get_issues_by_severity(self) -> Dict[IssueSeverity, List[Issue]]:
        """Group issues by severity."""
        by_severity = defaultdict(list)
        for issue in self.issues:
            by_severity[issue.severity].append(issue)
        return dict(by_severity)
    
    def get_critical_issues(self) -> List[Issue]:
        """Return only HIGH severity issues."""
        return [i for i in self.issues if i.severity == IssueSeverity.HIGH]
    
    def to_dict(self) -> dict:
        """Convert report to dictionary (JSON-serializable)."""
        return {
            "health_score": self.health_score.to_dict(),
            "summary": {
                "total_issues": len(self.issues),
                "critical": len(self.get_critical_issues()),
                "warnings": len([i for i in self.issues if i.severity == IssueSeverity.MEDIUM]),
                "info": len([i for i in self.issues if i.severity == IssueSeverity.LOW]),
            },
            "functional_summary": self.functional_summary.to_dict() if self.functional_summary else None,
            "functional_issues": [issue.to_dict() for issue in self.functional_issues],
            "backend_discovery": self.backend_discovery.to_dict() if self.backend_discovery else None,
            "issues_by_type": {
                issue_type.value: [i.to_dict() for i in issues]
                for issue_type, issues in self.get_issues_by_type().items()
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }


class ReportPrinter:
    """Pretty-print analysis reports to console."""
    
    @staticmethod
    def print_report(report: AnalysisReport):
        """Print a formatted analysis report."""
        print("\n" + "=" * 70)
        print("HEALTH REPORT - See What Is Wrong In Your Code")
        print("=" * 70)
        
        # Health Score
        print("\n📊 HOW GOOD IS YOUR CODE (Score out of 100)")
        print("-" * 70)
        scores = report.health_score.to_dict()
        print(f"  Overall:          {scores['overall']}/100")
        print(f"  Safety:           {scores['security']}/100")
        print(f"  Speed:            {scores['performance']}/100")
        print(f"  Structure:        {scores['design']}/100")
        print(f"  Can Trust It:     {scores['reliability']}/100")
        
        # Intelligence Layer Insights
        if report.intelligence:
            ReportPrinter._print_intelligence(report.intelligence)
        
        # Summary
        summary = report.to_dict()["summary"]
        print("\n📈 WHAT DID WE FIND")
        print("-" * 70)
        print(f"  Total Problems:     {summary['total_issues']}")
        print(f"  🔴 Very Bad:        {summary['critical']}")
        print(f"  🟡 Need To Fix:     {summary['warnings']}")
        print(f"  🟢 Small Issues:    {summary['info']}")
        
        # Issues by Type
        if report.issues:
            print("\n🔍 WHAT KIND OF PROBLEMS")
            print("-" * 70)
            by_type = report.get_issues_by_type()
            for issue_type in [IssueType.SECURITY, IssueType.PERFORMANCE, 
                             IssueType.DESIGN, IssueType.RELIABILITY,
                             IssueType.FUNCTIONAL,
                             IssueType.ARCHITECTURE]:
                issues = by_type.get(issue_type, [])
                if issues:
                    print(f"\n  {issue_type.value.upper()} ({len(issues)})")
                    for issue in issues:
                        severity_icon = "🔴" if issue.severity == IssueSeverity.HIGH else "🟡"
                        print(f"    {severity_icon} {issue.title} ({issue.location})")
                        print(f"       {issue.description}")
                        if issue.recommendation:
                            print(f"       → {issue.recommendation}")
        
        print("\n" + "=" * 70 + "\n")
    
    @staticmethod
    def _print_intelligence(intelligence: Dict):
        """Print intelligence layer insights."""
        print("\n🧠 WHAT WE THINK COULD GO WRONG")
        print("-" * 70)
        
        # Overall risk assessment
        categories = ['reliability', 'scalability', 'security', 'maintainability']
        print("\n  Big Problems To Fix:\n")
        for category in categories:
            if category in intelligence:
                insight = intelligence[category]
                risk = insight.get('risk_level', 'unknown').upper()
                summary = insight.get('summary', '')
                
                print(f"    • {category.capitalize():15} [{risk:8}]")
                print(f"      {summary}")
                
                # Show specific examples
                if category == 'reliability' and 'examples' in insight:
                    examples = insight.get('examples', [])
                    if examples:
                        print(f"      Problems: {', '.join(examples[:2])}")
                
                if category == 'scalability' and 'slow_functions' in insight:
                    slow = insight.get('slow_functions', [])
                    if slow:
                        print(f"      Slow spots: {', '.join(slow[:2])}")
                
                if category == 'security' and 'vulnerability_types' in insight:
                    vulns = insight.get('vulnerability_types', [])
                    if vulns:
                        print(f"      Security issues: {', '.join(vulns[:2])}")
                
                if category == 'maintainability' and 'top_issues' in insight:
                    issues = insight.get('top_issues', [])
                    if issues:
                        print(f"      Problems: {', '.join(issues[:2])}")
                
                print()
        
        # Correlated patterns
        correlations = intelligence.get('correlations', [])
        if correlations:
            print("\n  Connected Problems (when one problem makes another worse):")
            for corr in correlations:
                severity = corr.get('severity', 'medium').upper()
                pattern = corr.get('pattern', '')
                rec = corr.get('recommendation', '')
                print(f"    • {severity:8} - {pattern}")
                print(f"              → {rec}")
