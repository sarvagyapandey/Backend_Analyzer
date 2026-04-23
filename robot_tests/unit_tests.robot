*** Settings ***
Library    robot_tests/BackendAnalyzerLibrary.py
Suite Setup    Initialize Unit Test Data
Suite Teardown    Clean Up Unit Test Data

*** Variables ***
${PYTHON_SAFE_CODE}    import json\n\ndef safe_handler(user_input):\n    config = json.loads(user_input)\n    query = "SELECT * FROM users WHERE name = ?"\n    return config, query
${PYTHON_UNSAFE_CODE}    def unsafe_handler(user_input):\n    config = eval(user_input)\n    result = exec("print('hello')")\n    db.execute(f"SELECT * FROM users WHERE name = '{user_input}'")\n    return config, result
${JAVA_SAFE_CODE}    package demo;\n\nimport org.springframework.web.bind.annotation.GetMapping;\nimport org.springframework.web.bind.annotation.RestController;\n\n@RestController\nclass HealthController {\n    @GetMapping("/health")\n    public String health() {\n        return "ok";\n    }\n}
${JAVA_UNSAFE_CODE}    package demo;\n\nimport org.springframework.web.bind.annotation.PostMapping;\nimport org.springframework.web.bind.annotation.RequestBody;\nimport org.springframework.web.bind.annotation.RestController;\n\n@RestController\nclass UserController {\n    @PostMapping("/users")\n    public String createUser(@RequestBody UserRequest request) {\n        try {\n            return service.create(request);\n        } catch (Exception ex) {\n        }\n    }\n}

*** Test Cases ***
Find unsafe Python code
    [Documentation]    Checks that unsafe Python code is flagged for security problems.
    Log    Running unsafe Python unit test.
    ${issues}=    Analyze Python Code    ${PYTHON_UNSAFE_CODE}    unsafe.py
    Issue Titles Should Contain    ${issues}    eval()
    Issue Titles Should Contain    ${issues}    exec()
    Issue Titles Should Contain    ${issues}    Database query using string formatting

Do not flag safe Python code
    [Documentation]    Checks that safe Python code does not create false positives.
    Log    Running safe Python unit test.
    ${issues}=    Analyze Python Code    ${PYTHON_SAFE_CODE}    safe.py
    Issue Titles Should Not Contain    ${issues}    eval()
    Issue Titles Should Not Contain    ${issues}    exec()

Find Java controller problems
    [Documentation]    Checks that risky Java controller code is flagged.
    Log    Running Java controller unit test.
    ${issues}=    Analyze Java Code    ${JAVA_UNSAFE_CODE}    UserController.java
    Issue Titles Should Contain    ${issues}    accepts input without obvious validation
    Issue Titles Should Contain    ${issues}    swallows exceptions

Do not flag safe Java code
    [Documentation]    Checks that safe Java code stays clean.
    Log    Running safe Java unit test.
    ${issues}=    Analyze Java Code    ${JAVA_SAFE_CODE}    HealthController.java
    Issue Titles Should Not Contain    ${issues}    swallows exceptions

Find backend details from a sample project
    [Documentation]    Checks that backend discovery works on a small sample project.
    Log    Running backend discovery unit test.
    ${project}=    Create Sample Project
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python
    Should Be Equal    ${discovery.api_style}    REST
    [Teardown]    Cleanup Sample Project

*** Keywords ***
Initialize Unit Test Data
    No Operation

Clean Up Unit Test Data
    No Operation
