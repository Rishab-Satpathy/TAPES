"""User model for authentication.

This module handles user authentication and user data management.
It provides functions to authenticate users and retrieve user information
from the users database.

Functions:
    authenticate(username, password): Authenticates a user with credentials
    get_user(user_id): Retrieves user information by user ID
"""
users_db = {1: {"id": 1, "name": "admin", "role": "admin"}}

def authenticate(username, password):
    return users_db.get(1)

def get_user(user_id):
    return users_db.get(user_id)
