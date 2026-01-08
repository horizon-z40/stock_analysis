#!/bin/bash

# 股票分析项目启动/停止脚本
# 用法: ./start.sh [start|stop|restart|status]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"
LOG_FILE="$SCRIPT_DIR/.server.log"

# Flask 后端配置
FLASK_PORT=8080
FLASK_CMD="python $SCRIPT_DIR/app.py $FLASK_PORT"

# Vue 前端配置
VUE_DIR="$SCRIPT_DIR/vue"
VUE_CMD="cd $VUE_DIR && npm run dev"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 通过端口查找进程
find_process_by_port() {
    local port=$1
    if command -v lsof > /dev/null 2>&1; then
        lsof -ti:$port 2>/dev/null
    elif command -v netstat > /dev/null 2>&1; then
        netstat -tuln 2>/dev/null | grep ":$port " | awk '{print $NF}' | cut -d'/' -f1 | head -1
    else
        # 使用 ps 和 grep 查找
        ps aux | grep -E ":$port|port.*$port" | grep -v grep | awk '{print $2}'
    fi
}

# 杀死进程及其所有子进程
kill_process_tree() {
    local pid=$1
    if [ -z "$pid" ] || ! ps -p "$pid" > /dev/null 2>&1; then
        return
    fi
    
    # 获取所有子进程
    local children=$(pgrep -P "$pid" 2>/dev/null)
    
    # 先杀死子进程
    for child in $children; do
        kill_process_tree "$child"
    done
    
    # 杀死当前进程
    kill "$pid" 2>/dev/null
    sleep 0.5
    if ps -p "$pid" > /dev/null 2>&1; then
        kill -9 "$pid" 2>/dev/null
    fi
}

# 检查进程是否运行
check_process() {
    if [ -f "$PID_FILE" ]; then
        FLASK_PID=$(head -n 1 "$PID_FILE" 2>/dev/null)
        VUE_PID=$(tail -n 1 "$PID_FILE" 2>/dev/null)
        
        if [ -n "$FLASK_PID" ] && ps -p "$FLASK_PID" > /dev/null 2>&1; then
            return 0
        fi
        if [ -n "$VUE_PID" ] && ps -p "$VUE_PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 启动服务
start_services() {
    # 检查端口是否被占用
    FLASK_PORT_IN_USE=$(find_process_by_port $FLASK_PORT)
    VUE_PORT_IN_USE=$(find_process_by_port 3000)
    
    if [ -n "$FLASK_PORT_IN_USE" ] || [ -n "$VUE_PORT_IN_USE" ]; then
        echo -e "${YELLOW}检测到端口被占用，正在清理...${NC}"
        if [ -n "$FLASK_PORT_IN_USE" ]; then
            echo "清理 Flask 端口 $FLASK_PORT..."
            for pid in $FLASK_PORT_IN_USE; do
                kill_process_tree "$pid" 2>/dev/null
            done
        fi
        if [ -n "$VUE_PORT_IN_USE" ]; then
            echo "清理 Vue 端口 3000..."
            for pid in $VUE_PORT_IN_USE; do
                kill_process_tree "$pid" 2>/dev/null
            done
        fi
        sleep 2
    fi
    
    if check_process; then
        echo -e "${YELLOW}服务已经在运行中${NC}"
        show_status
        return 1
    fi
    
    echo -e "${GREEN}正在启动服务...${NC}"
    
    # 启动 Flask 后端
    echo "启动 Flask 后端 (端口: $FLASK_PORT)..."
    cd "$SCRIPT_DIR"
    nohup $FLASK_CMD >> "$LOG_FILE" 2>&1 &
    FLASK_PID=$!
    
    # 等待一下确保 Flask 启动
    sleep 2
    
    # 启动 Vue 前端
    echo "启动 Vue 前端 (端口: 3000)..."
    cd "$VUE_DIR"
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}检测到 node_modules 不存在，正在安装依赖...${NC}"
        npm install
    fi
    nohup bash -c "$VUE_CMD" >> "$LOG_FILE" 2>&1 &
    VUE_PID=$!
    
    # 保存 PID
    echo "$FLASK_PID" > "$PID_FILE"
    echo "$VUE_PID" >> "$PID_FILE"
    
    # 等待服务启动
    sleep 3
    
    if check_process; then
        echo -e "${GREEN}✓ 服务启动成功！${NC}"
        echo ""
        echo "Flask 后端: http://localhost:$FLASK_PORT"
        echo "Vue 前端:   http://localhost:3000"
        echo ""
        echo "日志文件: $LOG_FILE"
        echo "停止服务: ./start.sh stop"
    else
        echo -e "${RED}✗ 服务启动失败，请查看日志: $LOG_FILE${NC}"
        return 1
    fi
}

# 停止服务
stop_services() {
    echo -e "${YELLOW}正在停止服务...${NC}"
    
    # 通过端口查找并停止 Flask
    FLASK_PIDS=$(find_process_by_port $FLASK_PORT)
    if [ -n "$FLASK_PIDS" ]; then
        echo "停止 Flask 后端 (端口: $FLASK_PORT)..."
        for pid in $FLASK_PIDS; do
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "  找到进程 PID: $pid"
                kill_process_tree "$pid"
            fi
        done
    fi
    
    # 通过端口查找并停止 Vue (Vite 开发服务器)
    VUE_PIDS=$(find_process_by_port 3000)
    if [ -n "$VUE_PIDS" ]; then
        echo "停止 Vue 前端 (端口: 3000)..."
        for pid in $VUE_PIDS; do
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "  找到进程 PID: $pid"
                kill_process_tree "$pid"
            fi
        done
    fi
    
    # 如果存在 PID 文件，也尝试停止其中记录的进程
    if [ -f "$PID_FILE" ]; then
        FLASK_PID=$(head -n 1 "$PID_FILE" 2>/dev/null)
        VUE_PID=$(tail -n 1 "$PID_FILE" 2>/dev/null)
        
        if [ -n "$FLASK_PID" ] && ps -p "$FLASK_PID" > /dev/null 2>&1; then
            echo "停止 Flask 后端 (PID: $FLASK_PID)..."
            kill_process_tree "$FLASK_PID"
        fi
        
        if [ -n "$VUE_PID" ] && ps -p "$VUE_PID" > /dev/null 2>&1; then
            echo "停止 Vue 前端 (PID: $VUE_PID)..."
            kill_process_tree "$VUE_PID"
        fi
    fi
    
    # 额外清理：查找并杀死所有相关的 node 和 npm 进程（在 vue 目录下运行的）
    if [ -d "$VUE_DIR" ]; then
        # 查找在 vue 目录下运行的 node 进程
        NODE_PIDS=$(ps aux | grep -E "vite|node.*vue" | grep -v grep | awk '{print $2}')
        if [ -n "$NODE_PIDS" ]; then
            echo "清理残留的 Node.js 进程..."
            for pid in $NODE_PIDS; do
                # 检查进程的工作目录是否在 vue 目录下
                if ps -p "$pid" > /dev/null 2>&1; then
                    PROC_CWD=$(lsof -p "$pid" 2>/dev/null | grep cwd | awk '{print $NF}' | head -1)
                    if [[ "$PROC_CWD" == *"vue"* ]] || [[ "$PROC_CWD" == "$VUE_DIR"* ]]; then
                        echo "  清理进程 PID: $pid"
                        kill_process_tree "$pid"
                    fi
                fi
            done
        fi
    fi
    
    # 等待一下确保进程完全退出
    sleep 1
    
    # 再次检查端口是否被占用
    REMAINING_FLASK=$(find_process_by_port $FLASK_PORT)
    REMAINING_VUE=$(find_process_by_port 3000)
    
    if [ -n "$REMAINING_FLASK" ] || [ -n "$REMAINING_VUE" ]; then
        echo -e "${YELLOW}警告: 仍有进程占用端口，尝试强制清理...${NC}"
        if [ -n "$REMAINING_FLASK" ]; then
            for pid in $REMAINING_FLASK; do
                kill -9 "$pid" 2>/dev/null
            done
        fi
        if [ -n "$REMAINING_VUE" ]; then
            for pid in $REMAINING_VUE; do
                kill -9 "$pid" 2>/dev/null
            done
        fi
        sleep 1
    fi
    
    # 清理 PID 文件
    rm -f "$PID_FILE"
    
    # 最终检查
    FINAL_FLASK=$(find_process_by_port $FLASK_PORT)
    FINAL_VUE=$(find_process_by_port 3000)
    
    if [ -z "$FINAL_FLASK" ] && [ -z "$FINAL_VUE" ]; then
        echo -e "${GREEN}✓ 服务已停止${NC}"
    else
        echo -e "${RED}✗ 警告: 部分进程可能仍在运行，请手动检查${NC}"
        if [ -n "$FINAL_FLASK" ]; then
            echo "  Flask 端口 $FLASK_PORT 仍被占用: $FINAL_FLASK"
        fi
        if [ -n "$FINAL_VUE" ]; then
            echo "  Vue 端口 3000 仍被占用: $FINAL_VUE"
        fi
    fi
}

# 显示状态
show_status() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${RED}服务未运行${NC}"
        return 1
    fi
    
    FLASK_PID=$(head -n 1 "$PID_FILE" 2>/dev/null)
    VUE_PID=$(tail -n 1 "$PID_FILE" 2>/dev/null)
    
    echo "服务状态:"
    echo "---------"
    
    if [ -n "$FLASK_PID" ] && ps -p "$FLASK_PID" > /dev/null 2>&1; then
        echo -e "Flask 后端: ${GREEN}运行中${NC} (PID: $FLASK_PID, 端口: $FLASK_PORT)"
    else
        echo -e "Flask 后端: ${RED}未运行${NC}"
    fi
    
    if [ -n "$VUE_PID" ] && ps -p "$VUE_PID" > /dev/null 2>&1; then
        echo -e "Vue 前端:   ${GREEN}运行中${NC} (PID: $VUE_PID, 端口: 3000)"
    else
        echo -e "Vue 前端:   ${RED}未运行${NC}"
    fi
}

# 重启服务
restart_services() {
    stop_services
    sleep 2
    start_services
}

# 主逻辑
case "${1:-start}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 [start|stop|restart|status]"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动 Flask 后端和 Vue 前端"
        echo "  stop    - 停止所有服务"
        echo "  restart - 重启所有服务"
        echo "  status  - 查看服务状态"
        exit 1
        ;;
esac
