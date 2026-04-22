# Backend Analyzer

A **backend intelligence layer** that helps developers understand system-level problems in Python backend services faster.

Unlike traditional linters or security tools, Backend Analyzer:
- Identifies **production-level risks** (slow endpoints, reliability issues, architectural problems)
- Correlates multiple signals into meaningful insights
- Understands backend behavior, not just syntax/style
- Integrates with existing tools (Bandit, Flake8) instead of duplicating them

---

## Quick Start

### Installation

```bash
cd /path/to/backend-analyzer
# No external dependencies required for core analysis
# Optional: pip install bandit flake8 (for deeper analysis)
```

### Usage

```bash
# Analyze a single file
python cli.py /path/to/backend.py

# Analyze entire project
python cli.py /path/to/backend/codebase

# Analyze code and run live REST/GraphQL checks from config
python cli.py --cli /path/to/backend/codebase functional_test_config.sample.json
```

### Example Output

```
📊 HEALTH SCORE
  Overall:      75/100
  Security:     60/100 ← CRITICAL
  Performance:  80/100
  Design:       82/100
  Reliability:  78/100

🧠 BACKEND INTELLIGENCE INSIGHTS
  Risk Assessment:
    • Security        [CRITICAL] Code injection risk via eval()
    • Reliability     [HIGH] 3 potential service crash points
    • Scalability     [MEDIUM] N+1 query patterns in API handlers

  Correlated Issues:
    • CRITICAL - eval() + missing input validation
      → URGENT: Remove eval, add strict type validation
```

---

## What It Detects

### Security Issues
- `eval()` / `exec()` / pickle - "Anyone can run any code"
- SQL injection from string formatting - "User data goes directly to database"
- Missing input validation - "Program crashes instead of rejecting bad data"

### Performance Issues
- N+1 query patterns - "With 1000 users, system runs million database queries"
- Large API handlers - "System slows with 100 users, crashes at 1000"
- Slow endpoints doing too much work

### Reliability Issues
- Silent exception handling - "Errors disappear, nobody knows what's broken"
- Missing query timeouts - "Database hangs = entire system stops"
- Unsafe global state - "Data gets corrupted with concurrent requests"

### Design Issues
- Functions too large - "Hard to understand, easy to break"
- Missing type hints - "Users will pass wrong data, cause crashes"
- Too many parameters - "Confusing to use"

### Unique Advanced Detection
- Data flow security - Tracks user input → database
- State management bugs - Race conditions from shared state
- Resource leaks - Files opened without guaranteed cleanup
- Business logic bugs - Division by zero, bad comparisons
- Error handling chains - Errors that silently disappear

### Functional API Testing
- Calls live REST endpoints over HTTP
- Calls GraphQL queries and mutations over HTTP
- Fails when `data` is null, `errors` are present, or API error fields are returned
- Works for Python, Java, or any backend language because it tests the running API contract

---

## How It's Different from Other Tools

| Problem | Bandit/Flake8 | IDE | Backend Analyzer |
|---------|---|---|---|
| Finds style issues? | ✅ | ✅ | Only critical ones |
| Finds security issues? | ✅ Basic | Some | ✅ With context |
| Explains production impact? | ❌ | ❌ | ✅ Plain English |
| Correlates patterns? | ❌ | ❌ | ✅ |
| Tells you what breaks? | ❌ | ❌ | ✅ Real scenarios |
| Detects N+1 queries? | ❌ | ❌ | ✅ |
| Data flow analysis? | Some | Some | ✅ Specialized |
| Race conditions? | ❌ | ❌ | ✅ |

---

## Real Examples

### Example 1: N+1 Query Disaster
```python
# Your code
for user in users:
    for post in db.query(f"SELECT * FROM posts WHERE user_id = {user.id}"):
        print(post)

# Bandit says: Nothing
# Flake8 says: "Nested loop detected"
# Backend Analyzer says:
#   "N+1 query problem - loops inside loops
#    With 100 users = 10,100 queries
#    With 1000 users = 1,001,000 queries  
#    System will hang or crash
#    Query all data once, then loop"
```

### Example 2: Silent Crash
```python
# Your code
try:
    process_user_data(request.json)
except:
    pass  # Oops we swallowed the error

# Bandit says: Nothing
# Flake8 says: Nothing  
# Backend Analyzer says:
#   "CRITICAL: Silent error handling
#    Errors disappear - nobody knows why it broke
#    User report: 'It doesn't work'
#    You response: 'But I see no errors!'
#    Solution: Log the error"
```

### Example 3: Security Risk
```python
# Your code
query = f"SELECT * FROM users WHERE name = '{name}'"
result = db.execute(query)

# Bandit says: "SQL injection possible"
# Backend Analyzer says:
#   "CRITICAL: User data goes directly to database
#    Someone enters: ' OR '1'='1
#    Result: Attackers read entire database
#    Solution: Use parameterized queries"
```

---

## Creating Custom Detectors

Add a new detector to analyze specific patterns:

```python
# detectors/my_detector.py
from analyzer.detector_base import BaseDetector
from analyzer.issue import Issue, IssueType, IssueSeverity, IssueLocation
import ast
from typing import List

class MyCustomDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "my_detector"
    
    @property
    def description(self) -> str:
        return "Detects my specific issue pattern"
    
    def analyze(self, filepath: str, code: str) -> List[Issue]:
        """Analyze code and return issues."""
        issues = []
        
        try:
            tree = ast.parse(code)
            # Your detection logic using AST walking
            issues.append(Issue(
                detector_name=self.name,
                issue_type=IssueType.DESIGN,
                severity=IssueSeverity.MEDIUM,
                title="Issue title",
                description="Issue description",
                location=IssueLocation(filepath, line_num),
                recommendation="How to fix it",
                risk_explanation="Why this matters in production",
            ))
        except SyntaxError:
            pass
        
        return issues
```

Done! Detector auto-registers and runs automatically.

---

## Project Structure

```
backend-analyzer/
├── cli.py                    # Entry point
├── analyzer/
│   ├── issue.py             # Issue data model
│   ├── functional_testing.py # Live REST/GraphQL test runner
│   ├── detector_base.py      # Base class for detectors
│   ├── detector_manager.py   # Discovers and runs detectors
│   ├── engine.py            # Main analysis engine
│   ├── integrations.py      # External tool integration (Bandit, Flake8)
│   ├── intelligence.py      # Correlation & pattern analysis
│   ├── report.py            # Health scoring & reporting
│   └── ast_engine.py        # Legacy compatibility
├── detectors/
│   ├── __init__.py
│   ├── ast_detectors.py     # Security, complexity, validation detectors
│   └── api_detectors.py     # API performance & reliability detectors
├── functional_test_config.sample.json # Sample live API test config
└── test_sample.py           # Example with intentional issues
```

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture explanation.

**Quick Summary:**
1. **AST Detectors** - Analyze code structure (fast, precise)
2. **External Tools Integration** - Leverage Bandit, Flake8, etc.
3. **Intelligence Layer** - Correlate signals into patterns
4. **Health Scoring** - Quantify backend health
5. **Reporting** - Present actionable insights

---

## Use Cases

### Before Deploying to Production
```bash
python cli.py ./backend
# Review health report for critical issues
# Fix security/reliability problems before shipping
```

### After Production Incident
```bash
python cli.py ./backend
# Analyze for similar patterns
# Find systemic architectural issues
```

### Code Review Support
```bash
python cli.py ./src/new_feature.py
# Check for performance/reliability issues
# Validate against backend patterns
```

### Performance Investigation
```bash
python cli.py ./backend
# Identify N+1 queries, slow endpoints
# Understand scalability limitations
```

---

## How We Keep Our Unique Value

**We don't rebuild what exists:**
- Bandit handles security scanning → We interpret findings
- Flake8 handles code quality → We extract backend-critical issues
- IDEs handle syntax → We focus on behavior

**We add value by:**
- Correlating multiple signals
- Explaining production impact
- Providing backend-specific analysis
- Making findings actionable

---

## Roadmap

### Phase 2: Runtime Analysis
- Instrument code to detect actual N+1 queries  
- Profile endpoint performance
- Monitor behavior under load

### Phase 3: API Contract Validation
- Endpoint specification matching
- Response consistency checking
- Pagination pattern validation

### Phase 4: Advanced Patterns
- Deadlock detection
- Connection pool exhaustion patterns
- Race condition indicators

---

## Contributing

To add a new detector:

1. Create a class extending `BaseDetector`
2. Implement `name`, `description`, and `analyze()` methods
3. Return list of `Issue` objects
4. Drop in `detectors/` folder
5. Auto-discovered on next run

See detector examples in `detectors/ast_detectors.py` and `detectors/api_detectors.py`.

---

## License

[Your License Here]

---

## Questions?

See [ARCHITECTURE.md](ARCHITECTURE.md) for deep dive into design patterns and philosophy.
