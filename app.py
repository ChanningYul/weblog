#!/usr/bin/env python3
"""
Web Notepad Application with Authentication
Enhanced version with session-based authentication and file management
"""

import os
import json
import time
import secrets
import socket
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, session, redirect, url_for, render_template_string
from flask_cors import CORS
from werkzeug.exceptions import BadRequest

from file_manager import FileManager, FileManagerPool
from auth_manager import AuthenticationManager

app = Flask(__name__)
app.secret_key = "web_notepad_secret_key_2023_fixed"  # Use a fixed secret key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Set session lifetime to 24 hours
CORS(app)

# Global managers
auth_manager = AuthenticationManager()
file_manager_pool = FileManagerPool()

# Configuration
DEFAULT_FILE = "notes.txt"
UPLOAD_FOLDER = "uploads"
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
USER_FILES_DIR = "user_files"  # Directory for user-specific files

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload folder and user files directory exist
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
Path(USER_FILES_DIR).mkdir(exist_ok=True)

def get_user_file_path(username):
    """Get the file path for a specific user"""
    return os.path.join(USER_FILES_DIR, f"{username}.txt")

# HTML Templates
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登录 - Web记事本</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div class="login-container">
        <div class="login-box">
            <h1>🔐 Web记事本登录</h1>
            <form id="loginForm">
                <div class="form-group">
                    <label for="username">用户名:</label>
                    <input type="text" id="username" name="username" required autocomplete="username">
                </div>
                <div class="form-group">
                    <label for="password">密码:</label>
                    <input type="password" id="password" name="password" required autocomplete="current-password">
                </div>
                <button type="submit" class="btn btn-primary">登录</button>
                <div id="error-message" class="error-message"></div>
            </form>
        </div>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('error-message');
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    // Login successful, redirect to editor
                    window.location.href = '/editor';
                } else {
                    // Login failed
                    errorDiv.textContent = data.message || '登录失败';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = '网络错误，请重试';
                errorDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
"""

EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web Notepad - 编辑器</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📝 Web Notepad</h1>
            <div class="controls">
                <span id="status-indicator" class="status-indicator">●</span>
                <span id="status-text">准备就绪</span>
                <span id="version-info" class="version-info"></span>
                <button id="save-btn" class="btn btn-primary">💾 保存</button>
                <button id="logout-btn" class="btn btn-danger">🚪 注销</button>
            </div>
        </div>
        
        <div class="editor-container">
            <textarea id="editor" placeholder="开始编辑您的内容..."></textarea>
        </div>
        
        <div class="footer">
            <div class="info">
                <span id="char-count">字符数: 0</span>
                <span id="line-count">行数: 0</span>
                <span id="last-modified">最后修改: --</span>
            </div>
        </div>
    </div>

    <script src="/static/js/app.js"></script>
</body>
</html>
"""

# Authentication helpers
def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        # Check session
        if 'user' not in session:
            # For API requests, return JSON with redirect info
            if request.path.startswith('/api/'):
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            # For page requests, redirect to login page
            return redirect('/login')
        
        # Validate session
        user_data = auth_manager.validate_session(session['user'])
        if not user_data:
            # If validation fails, always reload sessions from file
            auth_manager.load_sessions()
            user_data = auth_manager.validate_session(session['user'])
            
            if not user_data:
                session.pop('user', None)
                # For API requests, return JSON with redirect info
                if request.path.startswith('/api/'):
                    return jsonify({'error': '会话已过期', 'redirect': '/login'}), 401
                # For page requests, redirect to login page
                return redirect('/login')
        
        # Add user info to request
        request.user = user_data
        return f(*args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function

# Routes
@app.route('/')
def index():
    """Redirect to login or editor based on session"""
    if 'user' in session:
        user_data = auth_manager.validate_session(session['user'])
        if user_data:
            return redirect('/editor')
        else:
            # Session is invalid, clear it
            session.pop('user', None)
    
    return redirect('/login')

@app.route('/login')
def login_page():
    """Login page"""
    return LOGIN_TEMPLATE

@app.route('/editor')
@require_auth
def editor_page():
    """Editor page"""
    return EDITOR_TEMPLATE

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Logout API endpoint"""
    try:
        if 'user' in session:
            auth_manager.invalidate_session(session['user'])
            session.pop('user', None)
        
        return jsonify({
            'success': True,
            'message': '注销成功',
            'redirect': '/login'
        })
    
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({'success': False, 'message': '注销失败'}), 500

@app.route('/logout')
def logout():
    """Logout endpoint"""
    if 'user' in session:
        auth_manager.invalidate_session(session['user'])
        session.pop('user', None)
    
    return redirect('/login')

# API Routes
@app.route('/api/login', methods=['POST'])
def api_login():
    """Login API endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效的数据'}), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        
        # Verify credentials
        if auth_manager.verify_password(username, password):
            # Create session
            session_id = auth_manager.create_session(username)
            session['user'] = session_id
            session.permanent = True  # Make session permanent
            
            return jsonify({
                'success': True,
                'message': '登录成功',
                'user': {
                    'username': username,
                    'role': auth_manager.get_user_info(username)['role']
                }
            })
        else:
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': '登录失败'}), 500

@app.route('/api/content', methods=['GET', 'HEAD'])
@require_auth
def get_content():
    """Get file content"""
    try:
        # Get user-specific file path
        username = request.user['username']
        user_file = get_user_file_path(username)
        
        file_manager = file_manager_pool.get_manager(user_file)
        
        # For HEAD requests, only return headers without body
        if request.method == 'HEAD':
            return '', 200
        
        content = file_manager.get_content()
        version = file_manager.get_version()
        file_info = file_manager.get_file_info()
        
        return jsonify({
            'success': True,
            'content': content,
            'version': version,
            'file_info': file_info
        })
    
    except Exception as e:
        print(f"Get content error: {e}")
        return jsonify({'success': False, 'message': '获取内容失败'}), 500

@app.route('/api/content', methods=['POST'])
@require_auth
def update_content():
    """Update file content"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效的数据'}), 400

        content = data.get('content', '')
        changes = data.get('changes', [])
        expected_version = data.get('version')

        # Get user-specific file path
        username = request.user['username']
        user_file = get_user_file_path(username)

        file_manager = file_manager_pool.get_manager(user_file)

        # Validate version if provided (for both incremental and full updates)
        if expected_version is not None and not file_manager.validate_version(expected_version):
            return jsonify({
                'success': False,
                'message': '版本冲突，文件已被其他操作修改',
                'error_type': 'version_mismatch',
                'current_version': file_manager.get_version(),
                'current_content': file_manager.get_content()
            }), 409

        # Apply changes if provided, otherwise update full content
        if changes:
            success, message = file_manager.apply_changes(changes, expected_version)

            # Handle version mismatch (should already be caught above, but keep for safety)
            if message == "version_mismatch":
                return jsonify({
                    'success': False,
                    'message': '版本冲突，文件已被其他操作修改',
                    'error_type': 'version_mismatch',
                    'current_version': file_manager.get_version(),
                    'current_content': file_manager.get_content()
                }), 409
        else:
            success = file_manager.update_full_content(content)
        
        if success:
            return jsonify({
                'success': True,
                'message': '保存成功',
                'version': file_manager.get_version(),
                'file_info': file_manager.get_file_info()
            })
        else:
            return jsonify({'success': False, 'message': '保存失败'}), 500
    
    except Exception as e:
        print(f"Update content error: {e}")
        return jsonify({'success': False, 'message': '更新内容失败'}), 500

@app.route('/api/calculate_diff', methods=['POST'])
@require_auth
def calculate_diff():
    """Calculate diff between two contents"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效的数据'}), 400
        
        old_content = data.get('old_content', '')
        new_content = data.get('new_content', '')
        
        # Get user-specific file path
        username = request.user['username']
        user_file = get_user_file_path(username)
        
        file_manager = file_manager_pool.get_manager(user_file)
        changes = file_manager.calculate_diff(old_content, new_content)
        
        return jsonify({
            'success': True,
            'changes': changes
        })
    
    except Exception as e:
        print(f"Calculate diff error: {e}")
        return jsonify({'success': False, 'message': '计算差异失败'}), 500

@app.route('/api/file_info', methods=['GET'])
@require_auth
def get_file_info():
    """Get file information"""
    try:
        # Get user-specific file path
        username = request.user['username']
        user_file = get_user_file_path(username)
        
        file_manager = file_manager_pool.get_manager(user_file)
        file_info = file_manager.get_file_info()
        
        return jsonify({
            'success': True,
            'file_info': file_info
        })
    
    except Exception as e:
        print(f"Get file info error: {e}")
        return jsonify({'success': False, 'message': '获取文件信息失败'}), 500

@app.route('/api/user_info', methods=['GET'])
@require_auth
def get_user_info():
    """Get current user information"""
    try:
        username = request.user['username']
        user_info = auth_manager.get_user_info(username)
        
        return jsonify({
            'success': True,
            'user': user_info
        })
    
    except Exception as e:
        print(f"Get user info error: {e}")
        return jsonify({'success': False, 'message': '获取用户信息失败'}), 500

@app.route('/api/session_info', methods=['GET'])
@require_auth
def get_session_info():
    """Get session information"""
    try:
        session_id = session['user']
        session_info = auth_manager.get_session_info(session_id)
        
        return jsonify({
            'success': True,
            'session': session_info
        })
    
    except Exception as e:
        print(f"Get session info error: {e}")
        return jsonify({'success': False, 'message': '获取会话信息失败'}), 500

@app.route('/debug/session')
def debug_session():
    """Debug session information"""
    try:
        session_data = dict(session)
        return jsonify({
            'success': True,
            'session': session_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/debug/validate_session')
def debug_validate_session():
    """Debug session validation"""
    try:
        if 'user' not in session:
            return jsonify({
                'success': False,
                'error': 'No user in session'
            })
        
        session_id = session['user']
        print(f"Session ID from Flask session: {session_id}")
        
        # Check if session exists in auth_manager
        if session_id in auth_manager.sessions:
            session_data = auth_manager.sessions[session_id]
            print(f"Session data in auth_manager: {session_data}")
        else:
            print(f"Session ID not found in auth_manager sessions")
            print(f"Available sessions in auth_manager: {list(auth_manager.sessions.keys())[:3]}")
        
        user_data = auth_manager.validate_session(session_id)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'user_data': user_data,
            'sessions_in_manager': list(auth_manager.sessions.keys())[:3]  # Show first 3 session IDs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/debug/reload_sessions')
def debug_reload_sessions():
    """Debug endpoint to force reload sessions"""
    try:
        auth_manager.load_sessions()
        return jsonify({
            'success': True,
            'message': 'Sessions reloaded',
            'sessions_count': len(auth_manager.sessions),
            'sessions': list(auth_manager.sessions.keys())[:5]  # Show first 5 session IDs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/debug/auth_manager_sessions')
def debug_auth_manager_sessions():
    """Debug endpoint to check auth_manager sessions"""
    try:
        return jsonify({
            'success': True,
            'sessions_count': len(auth_manager.sessions),
            'sessions': list(auth_manager.sessions.keys())[:5]  # Show first 5 session IDs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': '接口不存在'}), 404
    return redirect('/login')

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': '服务器内部错误'}), 500
    return redirect('/login')

@app.errorhandler(BadRequest)
def bad_request(error):
    """Handle bad request errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': '请求格式错误'}), 400
    return redirect('/login')

# Main function
def create_production_app():
    """Create a production-ready Flask application"""
    # Configure for production
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
    
    # Set secure secret key from environment if available
    secret_key = os.environ.get('FLASK_SECRET_KEY')
    if secret_key:
        app.secret_key = secret_key
    
    # Update user passwords from environment variables
    password_map = os.environ.get('NOTEPAD_PASSWORD_MAP', '')
    if password_map:
        # Parse password map (format: user1:password1,user2:password2)
        pairs = password_map.split(',')
        for pair in pairs:
            if ':' in pair:
                username, password = pair.split(':', 1)
                username = username.strip()
                password = password.strip()
                
                # Update user password
                if username in auth_manager.users:
                    auth_manager.users[username]['password_hash'] = auth_manager.hash_password(password)
                    print(f"Updated password for user: {username}")
                else:
                    # Add new user if not exists
                    auth_manager.users[username] = {
                        'password_hash': auth_manager.hash_password(password),
                        'role': 'user',
                        'created_at': datetime.now().isoformat()
                    }
                    print(f"Added new user: {username}")
        
        # Save updated configuration
        auth_manager.save_config()
    
    return app

if __name__ == '__main__':
    print("Web记事本应用启动中...")
    print(f"用户文件目录: {USER_FILES_DIR}")
    print(f"上传目录: {UPLOAD_FOLDER}")
    print(f"会话超时: {auth_manager.session_timeout}秒")
    print(f"用户列表: {auth_manager.list_users()}")
    
    def _get_int_env(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None:
            return default
        raw = raw.strip()
        if raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        if value < 1 or value > 65535:
            return default
        return value

    def _can_bind(host: str, port: int) -> bool:
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except OSError:
                pass
            s.bind((host, port))
            return True
        except OSError:
            return False
        finally:
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass

    host = os.environ.get("NOTEPAD_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = _get_int_env("NOTEPAD_PORT", 19999)
    debug_env = os.environ.get("NOTEPAD_DEBUG", "").strip().lower()
    debug = True if debug_env == "" else debug_env in {"1", "true", "yes", "y", "on"}

    candidates = [port, 19996, 18080, 5000, 8000, 8080, 8888]
    chosen = port
    if not _can_bind(host, port):
        for p in candidates:
            if p == port:
                continue
            if _can_bind(host, p):
                chosen = p
                break
        if chosen != port:
            print(f"端口 {port} 无法使用，已自动切换到端口 {chosen}")

    app.run(host=host, port=chosen, debug=debug, threaded=True)
