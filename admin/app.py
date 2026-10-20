import os
import asyncio
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import logging

from bot.services.database import db
from bot.services.memory import memory
from bot.config import config
from admin.manager import bot_manager
from aiogram import Bot
import json

# Setup logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Элин Admin Panel")
security = HTTPBasic()

# Mount static and templates
app.mount("/static", StaticFiles(directory="admin/static"), name="static")
templates = Jinja2Templates(directory="admin/templates")

# Admin credentials from .env or defaults
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "elin2024")

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = ADMIN_USERNAME.encode("utf8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = ADMIN_PASSWORD.encode("utf8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.on_event("startup")
async def startup_event():
    await db.init()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(get_current_username)):
    status, pid = bot_manager.get_status()
    
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with conn.execute("SELECT SUM(tokens) FROM users") as cursor:
            total_tokens = (await cursor.fetchone())[0] or 0

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "status": status,
        "pid": pid,
        "total_users": total_users,
        "total_tokens": total_tokens,
        "username": username
    })

@app.post("/bot/start")
async def start_bot(username: str = Depends(get_current_username)):
    bot_manager.start_bot()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/bot/stop")
async def stop_bot(username: str = Depends(get_current_username)):
    bot_manager.stop_bot()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, username: str = Depends(get_current_username)):
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM settings") as cursor:
            settings = await cursor.fetchall()
            
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings,
        "username": username
    })

@app.post("/settings/update")
async def update_setting(
    key: str = Form(...), 
    value: str = Form(...),
    username: str = Depends(get_current_username)
):
    await db.set_setting(key, value)
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, username: str = Depends(get_current_username)):
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 100") as cursor:
            users = await cursor.fetchall()
            
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users,
        "username": username
    })

@app.post("/users/add_tokens")
async def add_user_tokens(
    user_id: int = Form(...), 
    amount: int = Form(...),
    username: str = Depends(get_current_username)
):
    await db.add_tokens(user_id, amount)
    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, username: str = Depends(get_current_username)):
    logs = bot_manager.get_logs(100)
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": logs,
        "username": username
    })

@app.get("/persona", response_class=HTMLResponse)
async def persona_page(request: Request, username: str = Depends(get_current_username)):
    persona_data = await memory.get_elin_persona()
    # Преобразуем JSON в красивую строку для редактирования
    persona_json = json.dumps(persona_data, indent=4, ensure_ascii=False)
    
    return templates.TemplateResponse("persona.html", {
        "request": request,
        "persona_json": persona_json,
        "username": username
    })

@app.post("/persona/update")
async def update_persona(
    persona_json: str = Form(...),
    username: str = Depends(get_current_username)
):
    try:
        # Валидируем JSON перед сохранением
        data = json.loads(persona_json)
        await memory.update_elin_persona(json.dumps(data, ensure_ascii=False))
        return RedirectResponse(url="/persona?success=1", status_code=status.HTTP_303_SEE_OTHER)
    except json.JSONDecodeError:
        return RedirectResponse(url="/persona?error=invalid_json", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request, username: str = Depends(get_current_username)):
    return templates.TemplateResponse("broadcast.html", {
        "request": request,
        "username": username
    })

@app.post("/broadcast/send")
async def send_broadcast(
    message_text: str = Form(...),
    username: str = Depends(get_current_username)
):
    import aiosqlite
    bot = Bot(token=config.telegram_token)
    
    count = 0
    errors = 0
    
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
            
    for user in users:
        try:
            await bot.send_message(chat_id=user['user_id'], text=message_text, parse_mode="HTML")
            count += 1
            # Небольшая пауза чтобы не словить флуд-лимит
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Broadcast error for {user['user_id']}: {e}")
            errors += 1
            
    await bot.session.close()
    return RedirectResponse(url=f"/broadcast?success={count}&errors={errors}", status_code=status.HTTP_303_SEE_OTHER)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
