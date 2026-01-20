# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = "127.0.0.1:19999"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stdout
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "web-notepad"

# Server mechanics
daemon = False
pidfile = "/www/wwwroot/weblog/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (如果需要的话)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# Production optimizations
# 在生产环境中，建议设置环境变量来传递配置
DEFAULT_FILE = os.environ.get("NOTEPAD_DEFAULT_FILE", "note.txt")
PASSWORD_MAP = os.environ.get("NOTEPAD_PASSWORD_MAP", "username1:usernote1.txt,username2:usernote2.txt")

# 将环境变量转换为应用可以使用的格式
def parse_password_map(password_map_str):
    if not password_map_str:
        return None
    password_file_map = {}
    pairs = password_map_str.split(',')
    for pair in pairs:
        if ':' in pair:
            password, file_path = pair.split(':', 1)
            password_file_map[password.strip()] = file_path.strip()
    return password_file_map

# 应用配置
raw_env = [
    f"NOTEPAD_DEFAULT_FILE={DEFAULT_FILE}",
    f"NOTEPAD_PASSWORD_MAP={PASSWORD_MAP}"
]
