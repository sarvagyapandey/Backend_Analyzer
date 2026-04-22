"""
Test file showing framework-agnostic risks detected.
(Works with any framework: Django, FastAPI, Flask, etc.)
"""

# Django view
def get_user_profile(request):
    """Django endpoint - detects all risks regardless of Django."""
    user_id = request.GET.get('id')
    
    # Gets data without validation
    user = User.objects.filter(id=user_id).first()
    
    # N+1 problem (works with any DB)
    orders = Order.objects.filter(user_id=user.id)
    for order in orders:
        items = OrderItem.objects.filter(order_id=order.id)
        order.items = items
    
    # Silent error handling (framework agnostic)
    try:
        return JsonResponse(user.to_json())
    except:
        pass


# FastAPI endpoint (different framework, same risks)
async def get_user_fastapi(user_id: str):
    """FastAPI endpoint - same risks detected."""
    
    # Direct I/O - hard to test
    user = await db.users.find_one({'_id': user_id})
    
    # N+1 query pattern (any DB)
    async for order in db.orders.find({'user_id': user_id}):
        items = await db.items.find({'order_id': order['id']}).to_list(None)
        order['items'] = items
    
    # Unsafe JSON parsing
    try:
        return user.json()
    except:
        return {'error': 'failed'}


# GraphQL resolver (different framework, same risks)
def resolve_user_posts(user, info):
    """GraphQL resolver - same problem patterns."""
    
    # N+1 in GraphQL (very common issue)
    posts = []
    for comment in user.comments:
        # Database call inside loop
        author = Author.objects.get(id=comment.author_id)
        posts.append(author)
    
    return posts


# Functions that are hard to unit test
def process_payment(payment_data):
    """Directly calls external services - can't mock."""
    # Direct I/O - hard to test
    response = requests.post('https://payment-api.com/charge', json=payment_data)
    
    # Missing validation
    transaction_id = response['transaction_id']
    
    # Database call - can't mock without hitting real DB
    Payment.objects.create(
        transaction_id=transaction_id,
        user_id=payment_data['user_id'],
        amount=payment_data['amount']
    )
    
    return transaction_id


# Code that uses randomness
import random

def generate_api_key():
    """Uses randomness - tests will be flaky."""
    # Non-deterministic - will pass sometimes, fail sometimes
    random_part = random.randint(0, 1000000)
    return f"API_{random_part}"


# SQL injection with string formatting
def search_users(search_term):
    """Works with any database + any library."""
    # SQL injection (with any DB library)
    query = f"SELECT * FROM users WHERE name = '{search_term}'"
    return db.execute(query)


# Missing pagination
def get_all_posts():
    """Could return millions of records."""
    # No limit/pagination
    posts = Post.objects.all()  # Django
    return JsonResponse(list(posts), safe=False)


# Transaction without error handling
def transfer_funds(from_user, to_user, amount):
    """Database transaction without rollback."""
    db.begin_transaction()
    
    # No try-except - if error happens, locks stay
    from_user.balance -= amount
    from_user.save()
    
    to_user.balance += amount
    to_user.save()
    
    db.commit()


# Inconsistent response format
def create_item(name, description):
    """Returns different formats from different paths."""
    if not name:
        return {'error': 'Name required'}  # Error format 1
    
    if not description:
        return {'status': 'error', 'message': 'Description required'}  # Error format 2
    
    item = Item.objects.create(name=name, description=description)
    return {'data': item.to_dict()}  # Success format (different!)


# Resource leak
def backup_database():
    """File opened without guarantee of closing."""
    # File opened without 'with' statement
    backup_file = open('backup.sql')
    
    # If error happens here, file never closes
    sql_dump = db.dump()
    backup_file.write(sql_dump)
    
    backup_file.close()  # Only called if no error above
