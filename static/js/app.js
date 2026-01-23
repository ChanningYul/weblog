/**
 * Web Notepad Application - Enhanced
 * Main application logic for the notepad editor
 */

class NotepadApp {
    constructor() {
        // 安全地获取DOM元素，添加空值检查
        this.editor = document.getElementById('editor');
        this.saveBtn = document.getElementById('save-btn');
        this.logoutBtn = document.getElementById('logout-btn');
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');
        this.versionInfo = document.getElementById('version-info');
        this.charCount = document.getElementById('char-count');
        this.lineCount = document.getElementById('line-count');
        this.lastModified = document.getElementById('last-modified');
        
        // 检查关键元素是否存在
        if (!this.editor || !this.logoutBtn || !this.saveBtn) {
            console.error('Critical DOM elements not found. This may not be the editor page.');
            console.log('Elements found:', {
                editor: !!this.editor,
                saveBtn: !!this.saveBtn,
                logoutBtn: !!this.logoutBtn,
                statusIndicator: !!this.statusIndicator,
                statusText: !!this.statusText
            });
            return;
        }
        
        this.currentContent = '';
        this.currentVersion = 0;
        this.lastSavedContent = '';
        this.autoSaveInterval = null;
        this.isConnected = false;
        this.isSaving = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }

    async init() {
        // 如果关键元素不存在，直接返回
        if (!this.editor || !this.logoutBtn || !this.saveBtn) {
            return;
        }
        
        try {
            this.setupEventListeners();
            this.setupAutoSave();
            this.updateStats();
            
            // 检查认证状态
            const isAuthenticated = await this.checkAuthentication();
            if (!isAuthenticated) {
                this.redirectToLogin();
                return;
            }
            
            // 加载内容
            await this.loadContent();
            
            // 开始自动保存
            this.startAutoSave();
            
        } catch (error) {
            console.error('Initialization failed:', error);
            if (this.statusIndicator && this.statusText) {
                this.setStatus('error', '初始化失败');
            }
            
            // 如果是网络错误，不要重定向，而是显示错误状态
            if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                this.setStatus('error', '网络连接失败');
                this.isConnected = false;
                this.scheduleReconnect();
            }
        }
    }

    setupEventListeners() {
        // 保存按钮
        if (this.saveBtn) {
            this.saveBtn.addEventListener('click', () => this.saveContent());
        } else {
            console.error('Save button not found');
        }
        
        // 注销按钮
        if (this.logoutBtn) {
            this.logoutBtn.addEventListener('click', () => this.logout());
        } else {
            console.error('Logout button not found');
        }
        
        // 编辑器事件
        if (this.editor) {
            this.editor.addEventListener('input', () => this.handleContentChange());
            this.editor.addEventListener('keydown', (e) => this.handleKeyDown(e));
        } else {
            console.error('Editor not found');
        }
        
        // 窗口事件
        window.addEventListener('beforeunload', (e) => this.handleBeforeUnload(e));
        window.addEventListener('blur', () => this.handleWindowBlur());
        window.addEventListener('focus', () => this.handleWindowFocus());
        
        // 键盘快捷键
        document.addEventListener('keydown', (e) => this.handleGlobalKeyDown(e));
        
        // 定期连接检查
        setInterval(() => this.checkConnection(), 30000);
    }

    setupAutoSave() {
        // 自动保存间隔：30秒
        this.autoSaveInterval = setInterval(() => {
            if (this.hasUnsavedChanges() && this.isConnected && !this.isSaving) {
                this.saveContent();
            }
        }, 30000);
    }

    async checkAuthentication() {
        try {
            const response = await fetch('/api/content', { method: 'HEAD' });
            
            if (response.status === 401) {
                return false;
            }
            
            return response.ok;
        } catch (error) {
            console.error('Authentication check failed:', error);
            // 如果是网络错误，不要重定向，而是返回false让调用方处理
            if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                // 网络错误，不要重定向
                return false;
            }
            return false;
        }
    }

    redirectToLogin() {
        // 在反向代理环境下，使用相对路径重定向
        window.location.href = '/login';
    }

    async loadContent() {
        try {
            this.setStatus('loading', '加载中...');
            
            const response = await fetch('/api/content');
            
            if (response.status === 401) {
                this.redirectToLogin();
                return;
            }
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.currentContent = data.content || '';
            this.currentVersion = data.version || 0;
            this.lastSavedContent = this.currentContent;
            
            this.editor.value = this.currentContent;
            this.updateStats();
            this.setStatus('connected', '已连接');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            
            console.log('Content loaded successfully');
            
        } catch (error) {
            console.error('Failed to load content:', error);
            this.setStatus('error', '加载失败');
            this.isConnected = false;
            
            // 如果是网络错误，不要重定向，而是尝试重新连接
            if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                this.setStatus('error', '网络连接失败');
                this.scheduleReconnect();
            } else if (error.message.includes('HTTP 401')) {
                // 401错误已经在上面处理了
                return;
            } else {
                // 其他错误，尝试重新连接
                this.scheduleReconnect();
            }
        }
    }

    handleContentChange() {
        // 添加空值检查
        if (!this.editor) {
            return;
        }
        
        this.currentContent = this.editor.value;
        this.updateStats();
        
        // 实时显示保存状态
        if (this.hasUnsavedChanges()) {
            this.setStatus('saving', '有未保存的更改');
        } else {
            this.setStatus('connected', '已保存');
        }
    }

    handleKeyDown(e) {
        // Tab键处理
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.editor.selectionStart;
            const end = this.editor.selectionEnd;
            this.editor.value = this.editor.value.substring(0, start) + '    ' + this.editor.value.substring(end);
            this.editor.selectionStart = this.editor.selectionEnd = start + 4;
            this.handleContentChange();
        }
        
        // Ctrl+S 保存
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            this.saveContent();
        }
    }

    handleGlobalKeyDown(e) {
        // Ctrl+S 全局保存
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            this.saveContent();
        }
    }

    async saveContent() {
        if (!this.hasUnsavedChanges() || this.isSaving || !this.isConnected) {
            return;
        }
        
        try {
            this.isSaving = true;
            this.setStatus('saving', '保存中...');
            
            // 计算差异
            const changes = await this.calculateChanges(this.lastSavedContent, this.currentContent);
            
            let response;
            if (changes.length > 0 && changes.length < 10) {
                // 小量更改使用增量更新
                response = await fetch('/api/content', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        operation: 'incremental',
                        changes: changes,
                        version: this.currentVersion
                    })
                });
            } else {
                // 大量更改使用全量更新
                response = await fetch('/api/content', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        operation: 'full',
                        content: this.currentContent,
                        version: this.currentVersion
                    })
                });
            }
            
            if (response.status === 401) {
                this.redirectToLogin();
                return;
            }
            
            if (response.status === 409) {
                // 版本冲突，处理冲突
                const data = await response.json();
                console.warn('Version conflict detected:', data);
                
                // 重新加载内容
                await this.loadContent();
                
                // 显示冲突提示
                this.showNotification('文件已被其他操作修改，已重新加载最新内容', 'warning');
                
                return;
            }
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.currentVersion = data.version;
            this.lastSavedContent = this.currentContent;
            
            this.setStatus('connected', '已保存');
            this.updateLastModified();
            
            console.log('Content saved successfully');
            
        } catch (error) {
            console.error('Failed to save content:', error);
            this.setStatus('error', '保存失败');
            
            // 显示错误提示
            this.showNotification('保存失败，请重试', 'error');
            
        } finally {
            this.isSaving = false;
        }
    }

    async calculateChanges(oldContent, newContent) {
        try {
            const response = await fetch('/api/calculate_diff', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    old_content: oldContent,
                    new_content: newContent
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            return data.changes || [];
            
        } catch (error) {
            console.error('Failed to calculate changes:', error);
            return [];
        }
    }

    async logout() {
        try {
            // 安全地设置状态，添加额外的空值检查
            if (this.statusIndicator && this.statusText) {
                this.setStatus('saving', '注销中...');
            }
            
            const response = await fetch('/api/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                // 清除自动保存
                if (this.autoSaveInterval) {
                    clearInterval(this.autoSaveInterval);
                }
                
                // 跳转到登录页
                window.location.href = '/login';
            } else {
                throw new Error('Logout failed');
            }
            
        } catch (error) {
            console.error('Logout failed:', error);
            // 安全地显示通知
            if (typeof this.showNotification === 'function' && document.body) {
                this.showNotification('注销失败，请重试', 'error');
            } else {
                alert('注销失败，请重试');
            }
        }
    }

    hasUnsavedChanges() {
        // 添加空值检查
        if (!this.editor) {
            return false;
        }
        return this.currentContent !== this.lastSavedContent;
    }

    updateStats() {
        // 添加空值检查
        if (!this.editor || !this.charCount || !this.lineCount) {
            return;
        }
        
        const content = this.editor.value;
        const charCount = content.length;
        const lineCount = content.split('\n').length;
        
        this.charCount.textContent = `字符数: ${charCount}`;
        this.lineCount.textContent = `行数: ${lineCount}`;
        
        if (this.versionInfo && this.currentVersion > 0) {
            this.versionInfo.textContent = `版本: ${this.currentVersion}`;
        }
    }

    updateLastModified() {
        // 添加空值检查
        if (!this.lastModified) {
            return;
        }
        
        const now = new Date();
        const timeString = now.toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        this.lastModified.textContent = `最后修改: ${timeString}`;
    }

    setStatus(type, message) {
        // 添加空值检查
        if (!this.statusIndicator || !this.statusText) {
            console.warn('Status elements not found');
            return;
        }
        
        this.statusIndicator.className = `status-indicator ${type}`;
        this.statusText.textContent = message;
        
        // 设置状态指示器颜色
        switch (type) {
            case 'connected':
                this.statusIndicator.textContent = '●';
                this.statusIndicator.style.color = '#4CAF50';
                break;
            case 'saving':
                this.statusIndicator.textContent = '●';
                this.statusIndicator.style.color = '#ff9800';
                break;
            case 'error':
                this.statusIndicator.textContent = '●';
                this.statusIndicator.style.color = '#f44336';
                break;
            case 'loading':
                this.statusIndicator.textContent = '⟳';
                this.statusIndicator.style.color = '#2196F3';
                break;
            default:
                this.statusIndicator.textContent = '●';
                this.statusIndicator.style.color = '#666';
        }
    }

    showNotification(message, type = 'info') {
        // 添加空值检查
        if (!document.body) {
            console.warn('Document body not found');
            return;
        }
        
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // 设置样式
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            z-index: 1000;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            max-width: 300px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        `;
        
        // 设置颜色
        switch (type) {
            case 'success':
                notification.style.background = 'linear-gradient(135deg, #4CAF50 0%, #45a049 100%)';
                break;
            case 'error':
                notification.style.background = 'linear-gradient(135deg, #f44336 0%, #d32f2f 100%)';
                break;
            case 'warning':
                notification.style.background = 'linear-gradient(135deg, #ff9800 0%, #f57c00 100%)';
                break;
            default:
                notification.style.background = 'linear-gradient(135deg, #2196F3 0%, #1976D2 100%)';
        }
        
        document.body.appendChild(notification);
        
        // 显示动画
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);
        
        // 自动隐藏
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    async checkConnection() {
        if (!this.isConnected) {
            return;
        }
        
        try {
            const response = await fetch('/api/content', { method: 'HEAD' });
            
            if (response.status === 401) {
                this.redirectToLogin();
                return;
            }
            
            if (!response.ok) {
                throw new Error('Connection check failed');
            }
            
        } catch (error) {
            console.error('Connection check failed:', error);
            this.isConnected = false;
            
            // 如果是网络错误，显示特定消息
            if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                this.setStatus('error', '网络连接失败');
            } else {
                this.setStatus('error', '连接失败');
            }
            
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.setStatus('error', '连接失败，请刷新页面');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(1000 * this.reconnectAttempts, 10000); // 指数退避
        
        this.setStatus('loading', `重新连接中... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.loadContent();
        }, delay);
    }

    handleBeforeUnload(e) {
        if (this.hasUnsavedChanges()) {
            e.preventDefault();
            e.returnValue = '您有未保存的更改，确定要离开吗？';
            return e.returnValue;
        }
    }

    handleWindowBlur() {
        // 窗口失去焦点时保存（如果有未保存的更改）
        if (this.hasUnsavedChanges() && this.isConnected && !this.isSaving) {
            this.saveContent();
        }
    }

    handleWindowFocus() {
        // 窗口获得焦点时检查连接
        if (!this.isConnected) {
            this.checkConnection();
        }
    }

    startAutoSave() {
        // 已经在初始化时设置
    }

    stopAutoSave() {
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
            this.autoSaveInterval = null;
        }
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.notepadApp = new NotepadApp();
});