*** Settings ***
Library    robot_tests/BackendAnalyzerLibrary.py
Suite Setup    Start Functional Server
Suite Teardown    Stop Functional Server

*** Test Cases ***
Passes healthy REST endpoint
    [Documentation]    Checks that a healthy REST endpoint passes validation.
    Log    Running healthy REST functional case.
    ${tests}=    Evaluate    [{"name": "health ok", "kind": "rest", "url": "${BASE_URL}/health", "expect": {"status": 200, "json_paths": {"status": "not_null", "error": "null"}}}]
    ${summary}=    Run Functional Tests    ${tests}
    Should Be Equal As Integers    ${summary.failed}    0
    Should Be Equal As Integers    ${summary.passed}    1
    Log    Passed because the health endpoint returned the expected status and JSON body.

Fails broken REST endpoint
    [Documentation]    Checks that a broken REST endpoint is marked as failed.
    Log    Running broken REST functional case.
    ${tests}=    Evaluate    [{"name": "broken rest response", "kind": "rest", "url": "${BASE_URL}/broken", "expect": {"status": 200, "json_paths": {"data": "not_null", "error": "null"}}}]
    ${summary}=    Run Functional Tests    ${tests}
    Should Be Equal As Integers    ${summary.failed}    1
    Log    Passed because the broken REST endpoint was detected as a failing contract.

Passes healthy GraphQL query
    [Documentation]    Checks that a healthy GraphQL query passes validation.
    Log    Running healthy GraphQL functional case.
    ${tests}=    Evaluate    [{"name": "graphql data present", "kind": "graphql", "url": "${BASE_URL}/graphql", "query": "query($id: ID!) { user(id: $id) { id name } }", "variables": {"id": "1"}, "expect": {"status": 200, "data_not_null": True, "no_errors": True, "json_paths": {"data.user.name": "Ada"}}}]
    ${summary}=    Run Functional Tests    ${tests}
    Should Be Equal As Integers    ${summary.failed}    0
    Should Be Equal As Integers    ${summary.passed}    1
    Log    Passed because the GraphQL query returned data without errors.

Fails broken GraphQL query
    [Documentation]    Checks that a broken GraphQL query is marked as failed.
    Log    Running broken GraphQL functional case.
    ${tests}=    Evaluate    [{"name": "broken graphql response", "kind": "graphql", "url": "${BASE_URL}/graphql", "query": "query($id: ID!) { user(id: $id) { id name } }", "variables": {"id": "broken"}, "expect": {"status": 200, "data_not_null": True, "no_errors": True}}]
    ${summary}=    Run Functional Tests    ${tests}
    Should Be Equal As Integers    ${summary.failed}    1
    Log    Passed because the broken GraphQL query was detected as a failing contract.
