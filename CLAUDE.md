# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web Notepad - A Flask-based web application for text editing with user authentication. Users have their own private text files stored in `user_files/{username}.txt`.

## Development Commands

**Start development server:**
```bash
python app.py
```
Auto-selects an available port (tries 19999, 19996, 18080, 5000, 8000, 8080, 8888).

**Run as module:**
```bash
python -m flask run --host 0.0.0.0 --port 19999
```

## Production Deployment

**Management script (Linux):**
```bash
bash manage.sh {start|stop|restart|status}
```
Uses gunicorn on port 19999, PID file at `/www/wwwroot/weblog/gunicorn.pid`.

**Environment Variables:**
- `NOTEPAD_HOST` - Server host (default: 0.0.0.0)
- `NOTEPAD_PORT` - Server port (default: 19999)
- `NOTEPAD_DEBUG` - Enable debug mode
- `NOTEPAD_PASSWORD_MAP` - User credentials (format: `user1:pass1,user2:pass2`)
- `NOTEPAD_DEFAULT_FILE` - Default file name
- `FLASK_SECRET_KEY` - Flask secret key for sessions

## Architecture

**Main Application (`app.py`):**
- Flask app factory: `create_production_app()` returns configured production app
- Routes defined directly on `app` object (not blueprint-based)
- Built-in HTML templates: `LOGIN_TEMPLATE` and `EDITOR_TEMPLATE`
- Session-based auth via custom `@require_auth` decorator

**Authentication (`auth_manager.py`):**
- `AuthenticationManager` class manages users and sessions
- Users stored in `auth_config.json` (SHA-256 hashed passwords)
- Sessions stored in `sessions.json` with 1-hour timeout
- Session IDs are `secrets.token_urlsafe(32)` stored in Flask's signed session cookie

**File Management (`file_manager.py`):**
- `FileManager` - Per-file operations with version tracking and diff calculation
- `FileManagerPool` - Singleton pattern for reusing FileManager instances per file path
- Simple diff algorithm: finds common prefix/suffix and creates replace operation

**Request Flow:**
1. Unauthenticated request → redirect to `/login`
2. POST `/api/login` → validates credentials → creates session → returns JSON
3. Authenticated request → `@require_auth` decorator validates session ID
4. Each user gets their own file: `user_files/{username}.txt`

## Data Files

- `auth_config.json` - User accounts (passwords hashed)
- `sessions.json` - Active sessions
- `user_files/` - User-specific text files
- `static/` - CSS and JS assets

## Dependencies

Flask 2.3.x, Flask-CORS 4.0.x, gunicorn 21.x (production only)
