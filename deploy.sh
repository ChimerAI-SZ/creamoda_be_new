
echo "Pulling latest code from Git..."
git pull 

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Stopping old FastAPI process..."
pkill -f "gunicorn"
sleep 2

echo "Starting FastAPI application..."
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 main:app --daemon --access-logfile access.log --error-logfile error.log

echo "Deployment complete!"