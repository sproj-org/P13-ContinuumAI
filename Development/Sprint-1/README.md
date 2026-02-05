root folder: Code

backend:

cd .\backend\
python -m venv .venv

.venv\Scripts\Activate.ps1

Copy-Item env.example .env

edit env with your variables(gemini api key, secretkey,frontend origins, db?)

pip install -r requirements.txt

uvicorn app.main:app --reload


frontend:
cd .\Frontend\
npm install
npm run dev
