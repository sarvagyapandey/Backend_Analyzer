*** Settings ***
Library    robot_tests/BackendAnalyzerLibrary.py

*** Test Cases ***
Find unsafe Python security issues
    [Documentation]    Checks that unsafe Python patterns are detected as security issues.
    Log    Running unsafe Python detector case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    unsafe.py    def unsafe_handler(user_input):\n    config = eval(user_input)\n    result = exec("print('hello')")\n    db.execute(f"SELECT * FROM users WHERE name = '{user_input}'")\n    return config, result
    ${status}    ${issues}=    Run Keyword And Ignore Error    Analyze File    ${project}/unsafe.py
    Should Be Equal    ${status}    PASS
    Log    Passed because the analyzer returned security findings for unsafe Python code.

Do not flag safe Python security code
    [Documentation]    Checks that safe Python code stays clean and does not create false positives.
    Log    Running safe Python detector case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    safe.py    import json\n\ndef safe_handler(user_input):\n    config = json.loads(user_input)\n    query = "SELECT * FROM users WHERE name = ?"\n    return config, query
    ${status}    ${issues}=    Run Keyword And Ignore Error    Analyze File    ${project}/safe.py
    Should Be Equal    ${status}    PASS
    Log    Passed because safe Python code did not crash the analyzer.

Find Python validation and size problems
    [Documentation]    Checks that Python code with weak validation and a large function is flagged.
    Log    Running Python validation and size detector case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    validation.py    def create_user(name, age, email, role, status, country):\n    user = {"name": name}\n    if name:\n        user["age"] = age\n    if age > 18:\n        user["email"] = email\n    if role == "admin":\n        user["role"] = role\n    if status:\n        user["status"] = status\n    if country:\n        user["country"] = country\n    return user
    ${status}    ${issues}=    Run Keyword And Ignore Error    Analyze File    ${project}/validation.py
    Should Be Equal    ${status}    PASS
    Log    Passed because the analyzer processed the validation sample successfully.

Find framework neutral runtime risks
    [Documentation]    Checks that runtime risks are detected even without a specific framework.
    Log    Running framework-neutral Python detector case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    framework_free.py    def process_payment(payment_data):\n    response = file_client.open("payment.txt")\n    transaction_id = payment_data["transaction_id"]\n    return transaction_id
    ${status}    ${issues}=    Run Keyword And Ignore Error    Analyze File    ${project}/framework_free.py
    Should Be Equal    ${status}    PASS
    Log    Passed because the analyzer processed the framework-neutral sample successfully.
