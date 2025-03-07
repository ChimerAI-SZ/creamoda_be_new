#!/bin/bash

VENV_DIR="venv"
APP_NAME="creamoda_be"
PORT="8000"

# 获取环境变量，默认为test
ENV=${APP_ENV:-test}
echo "Deploying application in $ENV environment..."

echo "Pulling latest code from Git..."
git pull 

if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at $VENV_DIR."
else
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"

    if [ $? -eq 0 ]; then
        echo "Virtual environment created successfully at $VENV_DIR."
    else
        echo "Failed to create virtual environment."
        exit 1
    fi
fi

# 切换到虚拟环境
echo "Activating virtual environment..."
source venv/bin/activate

if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "You are now in the virtual environment."
else
    echo "Failed to activate virtual environment."
    exit 1
fi

echo "Installing dependencies..."
pdm install

if [ $? -eq 0 ]; then
    echo "Dependencies installed successfully."
else
    echo "Failed to install dependencies."
    exit 1
fi  

echo "Stopping old FastAPI process..."
# 查找使用指定端口的进程
PORT_PID=$(lsof -t -i:$PORT)
if [ ! -z "$PORT_PID" ]; then
    echo "Found process $PORT_PID using port $PORT. Stopping it..."
    kill $PORT_PID
    sleep 2
    # 如果进程仍然存在，强制终止
    if ps -p $PORT_PID > /dev/null; then
        echo "Process did not terminate gracefully. Forcing termination..."
        kill -9 $PORT_PID
        sleep 1
    fi
else
    echo "No process found using port $PORT."
fi

echo "Starting FastAPI application in $ENV environment..."
echo "APP_ENV=$ENV"
pdm run gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT main:app --daemon --name $APP_NAME

# 验证应用是否成功启动
sleep 3
NEW_PID=$(lsof -t -i:$PORT)
if [ ! -z "$NEW_PID" ]; then
    echo "Application started successfully with PID $NEW_PID."
else
    echo "Failed to start application. Check logs in $LOG_DIR directory."
    exit 1
fi

echo "Deployment complete!"