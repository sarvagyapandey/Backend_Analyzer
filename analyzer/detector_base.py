"""
Base class for all detectors in the backend analyzer.
"""
from abc import ABC, abstractmethod
from typing import List
from analyzer.issue import Issue


class BaseDetector(ABC):
    """
    Abstract base class for all detectors.
    
    A detector analyzes Python backend code for specific types of issues.
    Each detector should focus on a particular concern (security, performance, etc.)
    and return structured issues rather than printing logs.
    """
    
    def __init__(self):
        """Initialize detector."""
        self.issues: List[Issue] = []
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this detector."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what this detector checks."""
        pass
    
    @abstractmethod
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """
        Analyze code and return list of issues found.
        
        Args:
            filepath: Path to the file being analyzed
            code: Source code to analyze
            
        Returns:
            List of Issue objects found during analysis
        """
        pass
    
    def collect_issues(self) -> List[Issue]:
        """Return all collected issues from this detector."""
        return self.issues
    
    def clear_issues(self):
        """Clear collected issues."""
        self.issues = []
