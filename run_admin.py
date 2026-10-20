import uvicorn
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

if __name__ == "__main__":
    host = os.getenv("ADMIN_HOST", "0.0.0.0")
    port = int(os.getenv("ADMIN_PORT", 8080))
    user = os.getenv("ADMIN_USERNAME", "admin")
    
    print("✦ Atelier VEO Club | Executive Console")
    print(f"URL: http://{host}:{port}")
    print(f"Пользователь: {user}")
    print("Статус: Готов к приему запросов управления")
    
    uvicorn.run("admin.app:app", host=host, port=port, reload=False)
