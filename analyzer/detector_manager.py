"""
Manager for discovering and running detectors.
"""
import os
import importlib
from typing import List, Dict
from analyzer.detector_base import BaseDetector
from analyzer.issue import Issue


class DetectorManager:
    """
    Manages detector discovery, initialization, and execution.
    
    Automatically discovers detector modules and coordinates analysis.
    """
    
    def __init__(self, detectors_dir: str = None):
        """
        Initialize detector manager.
        
        Args:
            detectors_dir: Path to detectors directory. Defaults to ./detectors
        """
        self.detectors: Dict[str, BaseDetector] = {}
        self.detectors_dir = detectors_dir or os.path.join(
            os.path.dirname(__file__), '..', 'detectors'
        )
        self._discover_detectors()
    
    def _discover_detectors(self):
        """Auto-discover and load all detector modules."""
        if not os.path.exists(self.detectors_dir):
            return
        
        # Add detectors dir to path for imports
        import sys
        if self.detectors_dir not in sys.path:
            sys.path.insert(0, os.path.dirname(self.detectors_dir))
        
        for filename in os.listdir(self.detectors_dir):
            if filename.startswith('_') or not filename.endswith('.py'):
                continue
            
            module_name = filename[:-3]
            try:
                # Import the module
                module = importlib.import_module(f'detectors.{module_name}')
                
                # Find BaseDetector subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseDetector) and 
                        attr is not BaseDetector):
                        
                        # Instantiate detector
                        detector = attr()
                        self.detectors[detector.name] = detector
            except Exception as e:
                print(f"Warning: Failed to load detector {module_name}: {e}")
    
    def register_detector(self, detector: BaseDetector):
        """Manually register a detector."""
        self.detectors[detector.name] = detector
    
    def get_detectors(self) -> List[BaseDetector]:
        """Return list of all registered detectors."""
        return list(self.detectors.values())
    
    def run_all(self, filepath: str, code: str) -> List[Issue]:
        """
        Run all detectors on a single file.
        
        Args:
            filepath: Path to the file being analyzed
            code: Source code to analyze
            
        Returns:
            Combined list of all issues found by all detectors
        """
        all_issues = []
        for detector in self.detectors.values():
            try:
                issues = detector.analyze(filepath, code)
                all_issues.extend(issues)
            except Exception as e:
                print(f"Error in {detector.name}: {e}")
        
        return all_issues
