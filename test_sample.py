"""
Sample backend code with various issues for testing the analyzer.
"""


def get_user_salary(user_id):
    # Missing input validation
    user = db.users.find_one({"id": user_id})
    
    # Large unstructured logic
    salary = user['salary']
    taxes = salary * 0.15
    deductions = 0
    
    if user['marital_status'] == 'married':
        deductions += user['dependents'] * 500
    
    if user['state'] == 'california':
        deductions += salary * 0.10
    
    if user['state'] == 'new_york':
        deductions += salary * 0.08
    
    # Missing validation, potential security risk
    query = f"SELECT * FROM users WHERE name = '{user['name']}'"
    result = db.execute(query)
    
    # Dangerous function use
    config = eval(request.args.get('config', '{}'))
    
    return salary - taxes - deductions


def process_large_dataset(items):
    # N+1 query pattern
    for item in items:
        for sub_item in item['children']:
            # Database query in nested loop
            details = db.query(f"SELECT * FROM details WHERE id = {sub_item['id']}")
            process_details(details)


def api_handler():
    # Large request handler
    try:
        data = request.json
        user = create_user(data)
        transaction = create_transaction(user)
        notification = send_notification(user, transaction)
        log_event(user, transaction, notification)
        audit_log(user, transaction, notification)
        cache_result(user, transaction)
        return {"status": "ok", "user": user}
    except:
        pass  # Swallow exceptions
