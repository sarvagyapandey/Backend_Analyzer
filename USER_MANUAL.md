# Backend Analyzer Studio User Manual

## What This Tool Does

Backend Analyzer Studio is a desktop tool for reviewing backend codebases and checking how they behave in practice.

It starts with static analysis, which means it inspects the source code without running the backend. That lets it find risky design patterns, missing error handling, unsafe data handling, and other code-level problems before any endpoint is executed.

The project can inspect Python and Java backend source trees for discovery, profiling, and static review. Live testing is framework-agnostic because it talks to the running service over HTTP.

It combines three kinds of analysis:

1. Static code review
2. API discovery
3. Live endpoint testing

The goal is to help you understand:

- What the backend is made of
- What risks exist in the code
- What endpoints were discovered
- How those endpoints behave when exercised against a running server
- What should be fixed first

The tool presents the results in a GUI so you can inspect findings, scores, and test output without leaving the app.

## Main Features

- File and folder selection for backend projects
- Static analysis of backend source code
- Source-based detection of bad design patterns, missing error handling, weak validation, and other code smells without running the backend
- Discovery of backend framework markers, runtime hints, databases, and endpoints across Python and Java projects
- Health scoring across safety, speed, structure, and trust
- Issue browsing by severity
- Live API test execution for REST and GraphQL endpoints
- Detailed live response inspection
- Analysis log streaming during long runs

## What It Tests

### 1. Static Code Findings

These are findings discovered from code inspection only. The analyzer reads the source code and looks for problems without executing the backend.

The analyzer looks for patterns such as:

- Error handling issues
- Unsafe data handling
- Validation gaps
- Performance concerns
- Design and maintainability issues
- Reliability risks

Examples of static findings include:

- Swallowed or hidden exceptions
- Unsafe parsing or decoding
- Functions that do too much
- Missing validation
- Long-running operations without guardrails
- Large queries without paging

This is the first layer of analysis. It is designed to catch likely problems early, even before the service is running.

### 2. Backend Discovery

The analyzer tries to infer basic backend characteristics from source files, such as:

- Runtime
- Database type
- API style
- Framework markers
- Discovered endpoints
- Whether the codebase looks Python, Java, or mixed

This helps you understand what kind of backend you are looking at before you run tests.

### 3. Live API Tests

If endpoints are discovered and you provide a running base URL, the tool can run live checks against the backend.

It supports:

- REST requests
- GraphQL requests and mutations

Live tests can verify things like:

- Whether a route responds
- Whether the status code matches expectations
- Whether GraphQL returns errors
- Whether response data is present
- Whether the request shape matches the endpoint’s expected input

### 4. Functional Findings

Functional findings are the problems discovered from live tests.

These are different from static findings because they are based on actual runtime behavior.

Examples include:

- Endpoint not reachable
- Unexpected HTTP status code
- GraphQL response contains errors
- Missing response data
- Request contract mismatch

## How To Use It

### Step 1: Choose a Target

Open the application and select either:

- A Python file
- A backend folder

The target should be part of the backend you want to inspect.

### Step 2: Run Analysis

Click the analyze button.

The tool will:

- Scan the target code without running it
- Discover backend details from Python and Java source files
- Build the static issue list
- Calculate health scores
- Populate the endpoint explorer when route or GraphQL hints are found

### Step 3: Review Static Findings

Use the static review area to inspect:

- All findings
- A selected finding’s explanation
- The overall health score
- Issues grouped by severity

This section is for code review and architecture feedback. It is the main place to review problems like missing error handling, poor function design, unsafe parsing, unsafe database access, and other source-level risks. These findings come from reading the code, not from executing it.

### Step 4: Inspect Backend Profile

The backend profile section helps you see:

- Runtime
- Database
- API style
- Endpoint count
- Detected frameworks
- Whether the project appears to be Python, Java, or both

This is useful when you want a fast overview of what the analyzer thinks the project is.

### Step 5: Pick an Endpoint

If endpoints are discovered, select one from the API explorer.

The request workspace will populate with:

- A sample request body for REST
- A GraphQL query or mutation if relevant
- GraphQL variables if needed

### Step 6: Run a Live Test

Provide the running base URL for the backend, such as:

- `http://localhost:8000`

Then click the live test button.

The analyzer will send the request to the running service and display:

- The selected test
- HTTP status
- Request and response data
- Response headers
- Failures or mismatches

Live testing is separate from static analysis. You only run it after the static review if you want to validate a real endpoint.

### Step 7: Inspect Functional Findings

If the live request fails or behaves unexpectedly, the functional findings section will show the diagnosis.

This is the place to look for:

- Why the request failed
- What the mismatch means
- What action to take next

## UI Sections Explained

### Static Review

This section is for code review output from static analysis, before the backend is run.

It contains:

- A list of static findings
- A detail pane for one selected finding
- Overall score summary

Use this area to understand design issues, missing validation, hidden errors, unsafe parsing, and other code-level risks before running the backend.

### Backend Profile

This section summarizes what the analyzer discovered about the project.

### API Explorer

This section lists discovered endpoints and helps you prepare live requests.

It is populated from source analysis, so it can show routes or GraphQL hints before any live test is run.

### Request Workspace

This area is where you edit or review the request payload before sending a live test. It does not affect static analysis.

### Live API Test Runs

This section shows each live execution result.

### Live Test Result

This is the detailed view for one selected live test run.

### Functional Findings

This section lists runtime failures or mismatches discovered by live checks.

### Functional Diagnosis

This section explains why a live test failed and what to do next.

### Analysis Log

This shows streaming output from the analyzer while it works.

## Functional Requirements

The tool shall:

1. Accept a Python file or backend folder as input.
2. Analyze the selected target and generate a report without executing the backend.
3. Discover backend metadata such as runtime, database, API style, frameworks, and endpoint hints.
4. Detect and list static code findings.
5. Group findings by severity.
6. Calculate and display overall and category-based health scores.
7. Show a readable explanation for each selected finding.
8. Discover API endpoints when possible.
9. Populate a request workspace for selected endpoints.
10. Support REST live tests.
11. Support GraphQL live tests.
12. Send live requests to a user-provided backend base URL.
13. Display live test responses and metadata.
14. Show functional findings generated from live checks.
15. Stream analyzer logs while work is running.
16. Prevent duplicate work when an analysis is already in progress.
17. Support backend discovery for Python and Java source trees.

## Non-Functional Requirements

### Usability

- The interface should make it easy to move from code review to live testing.
- Static review should be understandable on its own, even if live tests are never run.
- Findings should be readable without needing the user to inspect raw analyzer output.
- The UI should clearly separate static issues from runtime failures.

### Responsiveness

- Long-running analysis should run in the background.
- The GUI should remain responsive while analysis is in progress.
- The log view should update as output arrives.

### Reliability

- The app should handle missing or malformed input with clear errors.
- The app should avoid crashing when no endpoints or findings are discovered.
- Live test execution should fail gracefully when the backend is unavailable.

### Maintainability

- Static findings, functional findings, and request-building logic should stay clearly separated in the code.
- The UI should be organized so future layout changes are easy to make.

### Portability

- The tool should work in a local desktop Qt environment.
- The app should report when the GUI cannot open because dependencies or display support are missing.

### Security

- The tool should not assume live endpoint input is trustworthy.
- JSON parsing should be validated before use.
- Error messages should avoid exposing unnecessary internal details.

## Input Expectations

### Valid Targets

- A Python file
- A backend source folder

### Valid Live Test Inputs

- A discovered endpoint
- A valid base URL for the running server
- A valid JSON request body when the endpoint expects one
- Valid GraphQL query or variables when testing GraphQL

## Output Expectations

The tool may display:

- Overall health score
- Issue counts by severity
- Backend profile data
- Discovered endpoints
- Static finding details
- Live API execution results
- Functional failure diagnostics
- Analysis logs

## Common Use Cases

### Code Review

Use the tool to scan a backend before a release and get a prioritized list of risks.

### API Exploration

Use the tool to discover endpoints and infer how the backend is structured.

### Smoke Testing

Use live testing to verify that an endpoint responds as expected while the backend is running.

### Debugging

Use functional findings to understand why a route, mutation, or request flow is failing.

## Limitations

- The tool can only test endpoints it can discover or build from the selected target.
- Live testing depends on a running backend server.
- Static analysis is still an analyzer, not a full human code review.
- Some frameworks or patterns may not be discovered if they are highly custom.

## Troubleshooting

### No GUI Opens

Check that:

- PySide6 is installed
- You have a desktop session available
- Required Qt system packages are present on Linux

### No Endpoints Found

This can happen if:

- The project does not expose obvious routes
- The backend uses a custom or unusual routing style
- The selected target does not include the relevant source files

### Live Tests Fail Immediately

Check that:

- The backend server is running
- The base URL is correct
- The selected endpoint is valid
- The request body or GraphQL payload is valid

### No Findings Appear

This can mean:

- The target is small
- The code is simple
- The analyzer did not detect anything risky

## Suggested Workflow

1. Run static analysis first to inspect the code without running the backend.
2. Review the overall score and static findings.
3. Check the backend profile and discovered endpoints.
4. Pick a discovered endpoint if you want to test runtime behavior.
5. Run a live test against the local backend.
6. Review the functional findings and refine the request if needed.

## Notes

- The tool is designed for backend review and validation.
- The static and live parts are intentionally separate because they answer different questions.
- Static findings explain code risk before execution.
- Functional findings explain runtime behavior.
- The project supports discovery across Python and Java backend source trees.
