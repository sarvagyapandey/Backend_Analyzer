*** Settings ***
Library    robot_tests/BackendAnalyzerLibrary.py

*** Test Cases ***
Analyze path and get backend discovery
    [Documentation]    Checks that analysis can inspect a valid path and discover backend metadata.
    Log    Running engine discovery case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    app.py    print("hello")
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python
    Log    Passed because the engine identified the sample project as Python.

Return none for invalid path
    [Documentation]    Checks that an invalid path returns no report instead of crashing.
    Log    Running invalid path case.
    ${result}=    Evaluate    __import__("analyzer.engine", fromlist=["AnalysisEngine"]).AnalysisEngine().analyze_path("/does/not/exist")
    Should Be Equal    ${result}    ${None}
    Log    Passed because invalid paths return no report instead of crashing.

Report shows issue breakdown
    [Documentation]    Checks that the report dictionary includes the expected issue summary fields.
    Log    Running report breakdown case.
    ${result}=    Evaluate    __import__("analyzer.report", fromlist=["AnalysisReport"]).AnalysisReport([__import__("analyzer.issue", fromlist=["Issue","IssueLocation","IssueSeverity","IssueType"]).Issue(detector_name="demo", issue_type=__import__("analyzer.issue", fromlist=["IssueType"]).IssueType.RELIABILITY, severity=__import__("analyzer.issue", fromlist=["IssueSeverity"]).IssueSeverity.MEDIUM, title="missing validation", description="demo", location=__import__("analyzer.issue", fromlist=["IssueLocation"]).IssueLocation("app.py", 10))]).to_dict()
    Should Be Equal As Integers    ${result["summary"]["total_issues"]}    1
    Should Be Equal As Integers    ${result["summary"]["warnings"]}    1
    Log    Passed because the report summary counted one warning and one total issue.

Report health score goes down when issues exist
    [Documentation]    Checks that the health score decreases when security and performance issues exist.
    Log    Running health score case.
    ${result}=    Evaluate    __import__("analyzer.report", fromlist=["AnalysisReport"]).AnalysisReport([__import__("analyzer.issue", fromlist=["Issue","IssueLocation","IssueSeverity","IssueType"]).Issue(detector_name="demo", issue_type=__import__("analyzer.issue", fromlist=["IssueType"]).IssueType.SECURITY, severity=__import__("analyzer.issue", fromlist=["IssueSeverity"]).IssueSeverity.HIGH, title="security issue", description="demo", location=__import__("analyzer.issue", fromlist=["IssueLocation"]).IssueLocation("app.py", 1)), __import__("analyzer.issue", fromlist=["Issue","IssueLocation","IssueSeverity","IssueType"]).Issue(detector_name="demo", issue_type=__import__("analyzer.issue", fromlist=["IssueType"]).IssueType.PERFORMANCE, severity=__import__("analyzer.issue", fromlist=["IssueSeverity"]).IssueSeverity.LOW, title="slow issue", description="demo", location=__import__("analyzer.issue", fromlist=["IssueLocation"]).IssueLocation("app.py", 2))]).health_score.to_dict()
    Should Be True    ${result["overall"]} < 100
    Should Be True    ${result["security"]} < 100
    Should Be True    ${result["performance"]} < 100
    Log    Passed because the health score dropped after adding security and performance issues.
