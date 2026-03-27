#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RollingWord 核心 HTTP 路由服务
"""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

# 动态加载同级模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import handlers
import database

PORT = 18080
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')

class RollingWordHandler(SimpleHTTPRequestHandler):
    
    def __init__(self, *args, **kwargs):
        # 将静态文件根目录锁定至 frontend
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)
    
    def _send_json_response(self, status_code: int, payload: dict):
        """标准 JSON 响应发送器"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode('utf-8'))

    def do_GET(self):
        """处理 GET 请求与静态文件分发"""
        if self.path == '/api/progress':
            code, resp = handlers.handle_get_progress()
            self._send_json_response(code, resp)
            
        elif self.path == '/api/corrected_words':
            code, resp = handlers.handle_get_corrected_words()
            self._send_json_response(code, resp)
            
        elif self.path.startswith('/api/'):
            # 未知的 API GET 请求直接拦截，防止泄露静态文件
            self._send_json_response(404, {"success": False, "error": "Endpoint Not Found"})
            
        else:
            # 非 /api/ 路径，交由父类处理静态资源请求
            super().do_GET()

    def do_POST(self):
        """处理 POST 请求，统一进行 JSON 解析和路由"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_json_response(400, {"success": False, "error": "请求体不可为空"})
            return

        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send_json_response(400, {"success": False, "error": "非法的 JSON 格式"})
            return

        # 严格路由映射
        routes = {
            '/api/action/mark': handlers.handle_action_mark,
            '/api/action/ui_state': handlers.handle_action_ui_state,
            '/api/correct': handlers.handle_ai_correct,
            '/api/rollback_preview': handlers.handle_rollback_preview,
            '/api/rollback': handlers.handle_rollback
        }

        handler_func = routes.get(self.path)
        
        if handler_func:
            code, resp = handler_func(payload)
            self._send_json_response(code, resp)
        else:
            self._send_json_response(404, {"success": False, "error": f"接口不存在: {self.path}"})

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def main():
    try:
        database.verify_db_exists()
    except Exception as e:
        print(f"\n[启动失败] {e}")
        print("请先执行数据迁移脚本来初始化数据库：")
        print("    python scripts/import_to_sqlite.py\n")
        sys.exit(1)
    
    print(f"Backend running on port {PORT}...")
    print(f"    Local: http://localhost:{PORT}")
    print(f"    Remote: http(s)://<machine-ip-addr>:{PORT}")
    server = HTTPServer(('', PORT), RollingWordHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down.")

if __name__ == "__main__":
    main()