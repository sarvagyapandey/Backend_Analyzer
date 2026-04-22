"""
Structured representation of detected issues in backend code.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class IssueSeverity(str, Enum):
    """Severity levels for issues."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueType(str, Enum):
    """Categories of issues."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    DESIGN = "design"
    RELIABILITY = "reliability"
    FUNCTIONAL = "functional"
    ARCHITECTURE = "architecture"


@dataclass
class IssueLocation:
    """File and line location of an issue."""
    filepath: str
    line: int
    column: Optional[int] = None
    
    def __str__(self) -> str:
        if self.column:
            return f"{self.filepath}:{self.line}:{self.column}"
        return f"{self.filepath}:{self.line}"


@dataclass
class Issue:
    """Represents a single issue found in backend code."""
    
    # Core identification
    detector_name: str
    issue_type: IssueType
    severity: IssueSeverity
    
    # Description
    title: str
    description: str
    
    # Location
    location: IssueLocation
    
    # Additional context
    recommendation: Optional[str] = None
    related_code: Optional[str] = None
    risk_explanation: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert issue to dictionary for serialization."""
        return {
            "detector": self.detector_name,
            "type": self.issue_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "location": str(self.location),
            "recommendation": self.recommendation,
            "risk_explanation": self.risk_explanation,
            "code_snippet": self.related_code,
        }
    
    def __lt__(self, other):
        """Sort by severity (HIGH > MEDIUM > LOW) then by location."""
        severity_order = {"high": 0, "medium": 1, "low": 2}
        if severity_order[self.severity.value] != severity_order[other.severity.value]:
            return severity_order[self.severity.value] < severity_order[other.severity.value]
        return str(self.location) < str(other.location)
