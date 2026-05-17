"""Tests for auth routes."""
def test_login_success():
    from auth_routes import login
    result, code = login("admin", "admin123")
    assert code == 200

def test_login_missing_credentials():
    from auth_routes import login
    result, code = login("", "")
    assert code == 400

def test_login_invalid():
    from auth_routes import login
    result, code = login("admin", "wrong")
    assert code == 401

def test_profile():
    from auth_routes import get_profile
    result, code = get_profile(1)
    assert code == 200
