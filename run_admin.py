import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    print("🚀 Запуск админ-панели Элин...")
    print("URL: http://127.0.0.1:8000")
    print("Логин по умолчанию: admin")
    print("Пароль по умолчанию: elin2024 (если не задан в .env)")
    
    uvicorn.run("admin.app:app", host="127.0.0.1", port=8000, reload=True)
