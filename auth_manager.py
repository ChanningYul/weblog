#!/usr/bin/env python3
"""
Authentication Manager Module
Handles password authentication and session management
"""

import os
import json
import hashlib
import secrets
import time
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta

class AuthenticationManager:
    """Manages user authentication and sessions"""
    
    def __init__(self, config_path: str = "auth_config.json", session_file: str = "sessions.json"):
        self.config_path = Path(config_path)
        self.session_file = session_file
        self.users: Dict[str, dict] = {}
        self.sessions: Dict[str, dict] = {}
        self.session_timeout = 3600  # 1 hour in seconds
        self.load_config()
        self.load_sessions()
    
    def load_config(self):
        """Load authentication configuration"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.users = config.get('users', {})
                    self.session_timeout = config.get('session_timeout', 3600)
            else:
                # Create default configuration
                self.create_default_config()
        except Exception as e:
            print(f"Error loading auth config: {e}")
            self.create_default_config()
    
    def create_default_config(self):
        """Create default authentication configuration"""
        # Default users with hashed passwords
        default_users = {
            'user1': {
                'password_hash': self.hash_password('user1123'),
                'role': 'user',
                'created_at': datetime.now().isoformat()
            },
            'user2': {
                'password_hash': self.hash_password('user2123'),
                'role': 'user',
                'created_at': datetime.now().isoformat()
            }
        }
        
        config = {
            'users': default_users,
            'session_timeout': self.session_timeout,
            'created_at': datetime.now().isoformat()
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.users = default_users
        except Exception as e:
            print(f"Error creating default config: {e}")
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def verify_password(self, username: str, password: str) -> bool:
        """Verify username and password"""
        if username not in self.users:
            return False
        
        expected_hash = self.users[username]['password_hash']
        return self.hash_password(password) == expected_hash
    
    def load_sessions(self):
        """Load sessions from file"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    self.sessions = json.load(f)
                # Clean up expired sessions
                self.cleanup_expired_sessions()
        except Exception as e:
            print(f"Error loading sessions: {e}")
            self.sessions = {}
    
    def save_sessions(self):
        """Save sessions to file"""
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving sessions: {e}")
    
    def create_session(self, username: str) -> str:
        """Create a new session for user"""
        session_id = secrets.token_urlsafe(32)
        session_data = {
            'username': username,
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'role': self.users[username]['role']
        }
        
        self.sessions[session_id] = session_data
        self.save_sessions()  # Save sessions to file
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[dict]:
        """Validate session and return user info if valid"""
        if not session_id or session_id not in self.sessions:
            return None
        
        session_data = self.sessions[session_id]
        
        # Check session timeout
        last_activity = datetime.fromisoformat(session_data['last_activity'])
        if datetime.now() - last_activity > timedelta(seconds=self.session_timeout):
            # Session expired
            del self.sessions[session_id]
            self.save_sessions()  # Save sessions to file
            return None
        
        # Update last activity
        session_data['last_activity'] = datetime.now().isoformat()
        self.save_sessions()  # Save sessions to file
        return session_data
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session (logout)"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.save_sessions()  # Save sessions to file
            return True
        return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, session_data in self.sessions.items():
            last_activity = datetime.fromisoformat(session_data['last_activity'])
            if current_time - last_activity > timedelta(seconds=self.session_timeout):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            self.save_sessions()  # Save sessions to file if any were removed
    
    def get_user_info(self, username: str) -> Optional[dict]:
        """Get user information"""
        if username in self.users:
            user_data = self.users[username].copy()
            user_data.pop('password_hash', None)  # Remove password hash
            return user_data
        return None
    
    def list_users(self) -> List[str]:
        """List all users"""
        return list(self.users.keys())
    
    def add_user(self, username: str, password: str, role: str = "user") -> bool:
        """Add a new user"""
        if username in self.users:
            return False
        
        self.users[username] = {
            'password_hash': self.hash_password(password),
            'role': role,
            'created_at': datetime.now().isoformat()
        }
        
        self.save_config()
        return True
    
    def remove_user(self, username: str) -> bool:
        """Remove a user"""
        if username not in self.users:
            return False
        
        del self.users[username]
        self.save_config()
        
        # Invalidate all sessions for this user
        sessions_to_remove = [
            session_id for session_id, session_data in self.sessions.items()
            if session_data['username'] == username
        ]
        
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
        
        return True
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        if not self.verify_password(username, old_password):
            return False
        
        self.users[username]['password_hash'] = self.hash_password(new_password)
        self.save_config()
        
        # Invalidate all sessions for this user
        sessions_to_remove = [
            session_id for session_id, session_data in self.sessions.items()
            if session_data['username'] == username
        ]
        
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
        
        return True
    
    def save_config(self):
        """Save configuration to file"""
        try:
            config = {
                'users': self.users,
                'session_timeout': self.session_timeout,
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Get session information"""
        if session_id in self.sessions:
            session_data = self.sessions[session_id].copy()
            session_data['session_id'] = session_id
            return session_data
        return None
    
    def get_active_sessions(self) -> List[dict]:
        """Get list of active sessions"""
        self.cleanup_expired_sessions()
        
        active_sessions = []
        for session_id, session_data in self.sessions.items():
            session_info = session_data.copy()
            session_info['session_id'] = session_id
            active_sessions.append(session_info)
        
        return active_sessions

# Example usage
if __name__ == "__main__":
    # Create authentication manager
    auth_manager = AuthenticationManager()
    
    # Test authentication
    print("Testing authentication...")
    print(f"Admin login: {auth_manager.verify_password('admin', 'admin123')}")
    print(f"User login: {auth_manager.verify_password('user', 'user123')}")
    print(f"Wrong password: {auth_manager.verify_password('admin', 'wrong')}")
    
    # Test sessions
    print("\nTesting sessions...")
    session_id = auth_manager.create_session('admin')
    print(f"Created session: {session_id}")
    
    session_info = auth_manager.validate_session(session_id)
    print(f"Session info: {session_info}")
    
    # Test logout
    print(f"Logout success: {auth_manager.invalidate_session(session_id)}")
    print(f"Session after logout: {auth_manager.validate_session(session_id)}")
    
    # Test user management
    print("\nTesting user management...")
    print(f"Add new user: {auth_manager.add_user('testuser', 'testpass')}")
    print(f"List users: {auth_manager.list_users()}")
    
    # Test password change
    print(f"Change password: {auth_manager.change_password('testuser', 'testpass', 'newpass')}")
    print(f"Login with new password: {auth_manager.verify_password('testuser', 'newpass')}")
    
    # Cleanup
    auth_manager.remove_user('testuser')