#!/bin/bash

# Web Notepad 生产环境管理脚本

PIDFILE="/www/wwwroot/weblog/gunicorn.pid"
LOGFILE="/www/wwwroot/weblog/gunicorn.log"

case "$1" in
    start)
        echo "🚀 Starting Web Notepad in production mode..."
        
        # 设置环境变量
        if [ -f ".env" ]; then
            set -a
            . "./.env"
            set +a
        else
            echo "⚠️  .env not found, using existing environment variables"
        fi
        
        echo "📝 Default file: $NOTEPAD_DEFAULT_FILE"
        echo "🔒 Password mapping: $NOTEPAD_PASSWORD_MAP"
        
        # 检查是否已经在运行
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "⚠️  Web Notepad is already running (PID: $PID)"
                exit 1
            fi
        fi
        
        # 启动gunicorn
        gunicorn --config gunicorn_conf.py "app:create_production_app()" -b 0.0.0.0:19999 --daemon
        echo "✅ Web Notepad started successfully"
        ;;
        
    stop)
        echo "🛑 Stopping Web Notepad..."
        
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                kill "$PID"
                echo "✅ Web Notepad stopped (PID: $PID)"
                rm -f "$PIDFILE"
            else
                echo "⚠️  Web Notepad is not running"
                rm -f "$PIDFILE"
            fi
        else
            echo "⚠️  Web Notepad is not running (no PID file found)"
        fi
        ;;
        
    restart)
        echo "🔄 Restarting Web Notepad..."
        $0 stop
        sleep 2
        $0 start
        ;;
        
    status)
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "✅ Web Notepad is running (PID: $PID)"
            else
                echo "❌ Web Notepad is not running (stale PID file)"
            fi
        else
            echo "❌ Web Notepad is not running"
        fi
        ;;
        
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
