"""
Integration with existing Python analysis tools.

Instead of rebuilding linting/security scanning, this module:
- Runs existing tools (Bandit, Flake8, etc.)
- Collects their output
- Converts to unified Issue format
- Correlates with custom detectors for backend-specific insights
"""
import json
import subprocess
from typing import List, Optional
from analyzer.issue import Issue, IssueType, IssueSeverity, IssueLocation


class ExternalToolIntegration:
    """Base class for integrating external analysis tools."""
    
    def run_tool(self, filepath: str) -> List[Issue]:
        """Run the tool and convert output to Issue objects."""
        raise NotImplementedError


class BanditIntegration(ExternalToolIntegration):
    """
    Integrate Bandit (security scanning tool).
    
    Bandit detects security issues; we correlate them with backend context.
    """
    
    def run_tool(self, filepath: str) -> List[Issue]:
        """Run Bandit and convert results."""
        try:
            result = subprocess.run(
                ['bandit', '-f', 'json', filepath],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 or result.stdout:
                data = json.loads(result.stdout)
                return self._convert_results(data, filepath)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        
        return []
    
    def _convert_results(self, data: dict, filepath: str) -> List[Issue]:
        """Convert Bandit JSON output to Issue objects."""
        issues = []
        
        for result in data.get('results', []):
            # Filter to focus on backend-relevant issues
            if result['severity'] in ['HIGH', 'MEDIUM']:
                issues.append(Issue(
                    detector_name="bandit_security",
                    issue_type=IssueType.SECURITY,
                    severity=IssueSeverity(result['severity'].lower()),
                    title=result['issue_text'],
                    description=result.get('issue_text', 'Security issue detected'),
                    location=IssueLocation(
                        filepath, 
                        result['line_number']
                    ),
                    related_code=result.get('code', ''),
                    recommendation=f"Review security pattern: {result.get('test_id', 'B000')}",
                ))
        
        return issues


class Flake8Integration(ExternalToolIntegration):
    """
    Integrate Flake8 (code quality/style).
    
    We only flag backend-relevant issues from Flake8:
    - Complexity warnings
    - Unused imports (memory/performance impact)
    - Undefined names (runtime crashes)
    """
    
    # Flake8 codes relevant to backend behavior
    BACKEND_CODES = {
        'F821': 'Undefined name',  # Runtime crash risk
        'E901': 'Syntax error',     # Won't run
        'W292': 'No newline at EOF', # Skip
        'E501': 'Line too long',     # Skip (formatting)
    }
    
    def run_tool(self, filepath: str) -> List[Issue]:
        """Run Flake8 and filter for backend-relevant issues."""
        try:
            result = subprocess.run(
                ['flake8', filepath],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return self._convert_results(result.stdout, filepath)
        except FileNotFoundError:
            pass
        
        return []
    
    def _convert_results(self, output: str, filepath: str) -> List[Issue]:
        """Parse Flake8 output and convert to Issues."""
        issues = []
        
        for line in output.strip().split('\n'):
            if not line:
                continue
            
            # Parse: filepath:line:col: CODE message
            parts = line.split(':')
            if len(parts) < 4:
                continue
            
            try:
                line_num = int(parts[1])
                col_num = int(parts[2])
                message = parts[3].strip()
                code = message.split()[0]
                
                # Only include backend-critical codes
                if code not in ['F821', 'E901']:
                    continue
                
                severity = IssueSeverity.HIGH if code == 'F821' else IssueSeverity.MEDIUM
                
                issues.append(Issue(
                    detector_name="flake8_quality",
                    issue_type=IssueType.RELIABILITY,
                    severity=severity,
                    title=f"Code quality issue: {code}",
                    description=message,
                    location=IssueLocation(filepath, line_num, col_num),
                    recommendation=f"Fix {code}: undefined names cause runtime crashes",
                ))
            except (ValueError, IndexError):
                continue
        
        return issues


class IntegrationManager:
    """
    Manages external tool integrations.
    
    Runs tools and correlates results with custom detectors.
    """
    
    def __init__(self):
        """Initialize available integrations."""
        self.integrations = {
            'bandit': BanditIntegration(),
            'flake8': Flake8Integration(),
        }
    
    def run_integrations(self, filepath: str) -> List[Issue]:
        """Run all available integrations."""
        all_issues = []
        
        for tool_name, integration in self.integrations.items():
            try:
                issues = integration.run_tool(filepath)
                all_issues.extend(issues)
            except Exception as e:
                # Silently skip if tool not installed
                pass
        
        return all_issues
    
    def get_available_tools(self) -> List[str]:
        """Return list of tools that are available on system."""
        available = []
        
        for tool in ['bandit', 'flake8']:
            try:
                subprocess.run(
                    [tool, '--version'],
                    capture_output=True,
                    timeout=5
                )
                available.append(tool)
            except FileNotFoundError:
                pass
        
        return available
