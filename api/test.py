"""Simple test handler for Vercel"""

def handler(request):
    """Test handler"""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': '{"status": "ok", "message": "Test handler works"}'
    }
