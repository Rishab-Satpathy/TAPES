"""Test suite to verify authentication refactoring."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
import jwt
from auth_routes import auth_bp
from auth_middleware import require_jwt, validate_jwt_token
from audit_logger import log_auth_event, log_login_attempt
from config import SECRET_KEY, JWT_ALGORITHM


class TestAuthRefactor(unittest.TestCase):
    """Test authentication refactoring."""
    
    def setUp(self):
        """Set up test Flask app."""
        self.app = Flask(__name__)
        self.app.register_blueprint(auth_bp)
        self.client = self.app.test_client()
        self.app.config['TESTING'] = True
    
    def test_centralized_jwt_validation(self):
        """Test that JWT validation is centralized in middleware."""
        # Create a valid token
        token = jwt.encode({"user": 1}, SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        # Test validate_jwt_token function
        payload = validate_jwt_token(token)
        self.assertEqual(payload["user"], 1)
        
        # Test invalid token raises error
        with self.assertRaises(jwt.InvalidTokenError):
            validate_jwt_token("invalid-token")
    
    @patch('auth_routes.authenticate')
    @patch('audit_logger.logger')
    def test_login_with_audit_logging(self, mock_logger, mock_auth):
        """Test login endpoint logs authentication events."""
        mock_auth.return_value = {"id": 1, "name": "admin"}
        
        response = self.client.post('/login', json={
            "username": "admin",
            "password": "password"
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json)
        
        # Verify audit logging was called
        self.assertTrue(mock_logger.info.called or mock_logger.warning.called)
    
    @patch('auth_routes.get_user')
    @patch('audit_logger.logger')
    def test_profile_with_middleware(self, mock_logger, mock_get_user):
        """Test profile endpoint uses centralized middleware."""
        mock_get_user.return_value = {"id": 1, "name": "admin", "role": "admin"}
        
        # Create valid token
        token = jwt.encode({"user": 1}, SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        response = self.client.get('/profile', headers={
            "Authorization": f"Bearer {token}"
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("user_id", response.json)
        
        # Verify audit logging was called
        self.assertTrue(mock_logger.info.called or mock_logger.warning.called)
    
    @patch('audit_logger.logger')
    def test_profile_without_token(self, mock_logger):
        """Test profile endpoint rejects requests without token."""
        response = self.client.get('/profile')
        
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json)
        
        # Verify failure was logged
        self.assertTrue(mock_logger.warning.called)
    
    @patch('audit_logger.logger')
    def test_profile_with_invalid_token(self, mock_logger):
        """Test profile endpoint rejects invalid tokens."""
        response = self.client.get('/profile', headers={
            "Authorization": "Bearer invalid-token"
        })
        
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json)
        
        # Verify failure was logged
        self.assertTrue(mock_logger.warning.called)
    
    def test_backward_compatibility_legacy_endpoint(self):
        """Test legacy endpoint still works for backward compatibility."""
        # Create valid token
        token = jwt.encode({"user": 1}, SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        response = self.client.get('/profile/legacy', headers={
            "Authorization": f"Bearer {token}"
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("user_id", response.json)
    
    def test_legacy_auth_file_untouched(self):
        """Verify legacy_auth.py was not modified."""
        import legacy_auth
        
        # Check that legacy_login function still exists
        self.assertTrue(hasattr(legacy_auth, 'legacy_login'))
        
        # Test it still works as before
        result = legacy_auth.legacy_login("user", "pass")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["token"], "legacy-static-token")
    
    @patch('audit_logger.logger')
    def test_structured_audit_logging(self, mock_logger):
        """Test that audit logging produces structured output."""
        log_auth_event(
            event_type="test_event",
            user_id=1,
            ip_address="127.0.0.1",
            endpoint="/test"
        )
        
        # Verify logger was called
        self.assertTrue(mock_logger.info.called or mock_logger.warning.called)
        
        # Get the call arguments
        call_args = mock_logger.info.call_args or mock_logger.warning.call_args
        if call_args:
            # Verify extra data was passed
            self.assertIn('extra', call_args[1])
            extra_data = call_args[1]['extra']
            self.assertIn('audit_data', extra_data)
    
    @patch('audit_logger.logger')
    def test_login_attempt_logging(self, mock_logger):
        """Test login attempt convenience function."""
        log_login_attempt(
            username="testuser",
            success=True,
            ip_address="127.0.0.1"
        )
        
        # Verify logger was called
        self.assertTrue(mock_logger.info.called)
        
        # Test failed login
        log_login_attempt(
            username="testuser",
            success=False,
            ip_address="127.0.0.1",
            reason="invalid_credentials"
        )
        
        # Verify warning was logged for failure
        self.assertTrue(mock_logger.warning.called)


if __name__ == '__main__':
    print("Running authentication refactoring tests...")
    print("=" * 70)
    unittest.main(verbosity=2)
