@echo off
echo === Smart Traffic Development Setup (Windows) ===
if not exist .env copy .env.example .env

echo Installing backend dependencies...
cd backend
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
cd ..

echo Installing ML dependencies (PyTorch CUDA recommended)...
cd ml
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
cd ..

echo Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo Setup complete! Run scripts\create_admin_user.py after starting DB.
