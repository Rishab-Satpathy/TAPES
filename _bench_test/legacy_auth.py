"""Protected legacy auth."""
def legacy_login(username, password):
    # None validation
    if username is None or password is None:
        return {"error": "Missing credentials"}, 400
    
    # Type validation
    if not isinstance(username, str) or not isinstance(password, str):
        return {"error": "Invalid credential types"}, 400
    
    # Input sanitization - check for null bytes and SQL injection patterns
    if '\x00' in username or '\x00' in password:
        return {"error": "Invalid characters in credentials"}, 400
    
    # Check for common SQL injection patterns
    sql_patterns = ["'", '"', '--', ';', '/*', '*/', 'xp_', 'sp_', 'DROP', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'UNION', 'OR 1=1', 'OR 1 = 1']
    username_upper = username.upper()
    password_upper = password.upper()
    
    for pattern in sql_patterns:
        if pattern.upper() in username_upper or pattern.upper() in password_upper:
            return {"error": "Invalid characters in credentials"}, 400
    
    return {"status": "ok", "token": "legacy-static-token"}
