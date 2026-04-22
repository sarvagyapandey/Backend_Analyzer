# Backend Analyzer Project Overview

## Short Version

Backend Analyzer is a desktop app that helps you understand backend code faster.

It does two big jobs:

1. It reads the code and finds static risks.
2. It discovers API endpoints and can test them against a running backend.

In simple terms, it helps answer:

- What does this backend do?
- What looks risky?
- What endpoints exist?
- Do those endpoints actually work when the server is running?

## What The Project Is For

The project is meant to help developers review backend services without relying only on manual code reading.

It is useful when you want to:

- Review a new backend quickly
- Find risky code patterns early
- Check whether endpoints respond correctly
- Understand backend health at a glance
- Explain problems in simple terms to teammates or leads

## How The Tool Works

### 1. You choose a target

The target can be:

- One Python file
- A whole backend folder

### 2. The analyzer scans the code

It looks for things like:

- Error handling issues
- Unsafe parsing
- Weak validation
- Performance problems
- Reliability concerns
- Design smells

### 3. It builds a backend profile

The app tries to infer basic facts about the backend:

- Runtime
- Database type
- API style
- Framework markers
- Endpoint count

### 4. It scores the backend

The app shows scores for:

- Safety
- Speed
- Structure
- Trust

It also combines those into an overall health score.

### 5. It discovers endpoints

If the target exposes routes or GraphQL operations, the app lists them so you can test them.

### 6. It runs live tests

If you give it a base URL for a running backend, it can send requests and inspect the response.

That means it can verify real runtime behavior instead of only reading code.

## What It Tests

### Static checks

Static checks are code-based findings.

Examples:

- Silent exception handling
- Unsafe JSON or data parsing
- Missing input validation
- Large or complicated functions
- Possible SQL or injection-style risks
- Long-running or unbounded operations

### Live API checks

Live checks are runtime tests against a running server.

The app can test:

- REST endpoints
- GraphQL queries and mutations

It checks for:

- Response status
- Response body shape
- GraphQL errors
- Missing data
- Contract mismatches

### Functional findings

Functional findings are the issues discovered from live tests.

These are different from static findings because they come from actual behavior, not code patterns alone.

## What The UI Shows

### Static Review

This is the code review area.

It shows:

- A list of static findings
- The selected finding’s details
- A readable explanation of impact and fix
- The overall health score

### Backend Profile

This gives a fast summary of the backend’s shape.

### API Explorer

This shows discovered endpoints and helps you prepare a request.

### Request Workspace

This is where the request body or GraphQL query lives before a live test.

### Live API Test Runs

This shows every live run the analyzer executes.

### Live Test Result

This shows the details for one selected live run.

### Functional Findings

This shows failures or mismatches found during live testing.

### Functional Diagnosis

This explains why a live test failed and what the next step should be.

### Analysis Log

This streams the analyzer’s progress output while it is working.

## Why This Project Is Useful

The main value is that it combines code review and runtime testing in one place.

That matters because many tools only do one of these:

- Linters mostly catch style or syntax issues
- Security tools catch known risky patterns
- API testers only tell you whether the endpoint responded

Backend Analyzer tries to connect the dots:

- It finds static risk
- It explains the likely production impact
- It shows endpoint behavior
- It helps you decide what to fix first

## Simple Explanation For A Tech Lead

If you need to explain the project in a meeting, you can say:

> Backend Analyzer is a desktop tool that reviews backend code, discovers API endpoints, and runs live checks against a running server. It combines static analysis and runtime testing so we can see both code-level risks and real endpoint behavior in one place. The app summarizes the backend, scores its health, and explains issues in simple language so we can prioritize fixes faster.

## Functional Requirements

The project should:

- Accept a Python file or backend folder
- Scan the target code
- Discover backend metadata
- Find static issues
- Group issues by severity
- Calculate health scores
- Discover endpoints
- Build REST and GraphQL requests
- Run live API tests
- Show live results
- Show functional failures
- Stream progress logs

## Non-Functional Requirements

The project should also be:

- Easy to use
- Responsive while running
- Clear about errors
- Stable when data is missing
- Maintainable for future changes
- Portable on a desktop Qt setup
- Safe about input parsing and error handling

## Project Structure

- `cli.py` is the desktop UI entry point
- `analyzer/` contains the analysis engine and supporting logic
- `USER_MANUAL.md` explains how to use the tool
- `README.md` gives the high-level project intro

## Current Documentation Set

This repository now keeps the docs focused:

- `README.md` for the quick intro
- `USER_MANUAL.md` for hands-on usage
- `PROJECT_OVERVIEW.md` for the project explanation you can share with a tech lead

## Bottom Line

Backend Analyzer is basically a backend review assistant.

It helps you:

- Understand code faster
- Spot risky patterns
- Test endpoints against a running server
- Explain findings in plain English
- Prioritize what needs attention first

