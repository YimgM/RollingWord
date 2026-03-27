#!/bin/bash

# 定义配置文件路径和日志路径
PLIST_PATH="$HOME/Library/LaunchAgents/com.taritsu.rollingword.plist"
LOG_OUT="$HOME/Library/Logs/rollingword.log"
LOG_ERR="$HOME/Library/Logs/rollingword.err"

# 检查传入的操作指令
case "$1" in
    start)
        echo "正在启动 RollingWord 后端..."
        launchctl load -w "$PLIST_PATH"
        echo "服务已启动"
        ;;
    stop)
        echo "正在停止 RollingWord 后端..."
        launchctl unload "$PLIST_PATH" 2>/dev/null
        echo "服务已完全停止，可以进行维护/数据库操作"
        ;;
    restart)
        echo "正在重启 RollingWord 后端..."
        launchctl unload "$PLIST_PATH" 2>/dev/null
        sleep 1
        launchctl load -w "$PLIST_PATH"
        echo "服务重启完成"
        ;;
    logs)
        echo "正在实时查看运行日志 (按 Ctrl+C 退出)..."
        echo "------------------------------------------------"
        tail -f "$LOG_OUT" "$LOG_ERR"
        ;;
    update)
        echo "正在从 Git 拉取最新代码并重启..."
        # 假设你使用 git 管理代码
        git pull origin main 
        launchctl unload "$PLIST_PATH" 2>/dev/null
        sleep 1
        launchctl load -w "$PLIST_PATH"
        echo "代码更新并重启完成"
        ;;
    *)
        echo "使用说明: ./manage.sh {start|stop|restart|logs|update}"
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务 (维护数据库时使用)"
        echo "  restart - 重启服务 (修改后端代码后使用)"
        echo "  logs    - 实时查看运行和报错日志"
        echo "  update  - 拉取代码并自动重启"
        exit 1
        ;;
esac
