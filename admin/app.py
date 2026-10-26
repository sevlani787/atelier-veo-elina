import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import asyncio

import shutil

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Query, File, UploadFile

from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse

from fastapi.staticfiles import StaticFiles

from fastapi.templating import Jinja2Templates

from fastapi.security import HTTPBasic, HTTPBasicCredentials

from pydantic import BaseModel

from typing import Optional

import secrets

import logging

import aiosqlite

import json

from pathlib import Path

import subprocess



from bot.services.database import db

from bot.services.memory import memory

from bot.config import config

from admin.manager import bot_manager

from admin.boardroom_service import boardroom_service
from admin.auto_qa_service import auto_qa_runner

from aiogram import Bot



logging.basicConfig(level=logging.INFO)



app = FastAPI(title="Atelier VEO | Executive Console")

security = HTTPBasic()



# Статика и шаблоны с абсолютными путями (иммунитет к рабочей директории)

BASE_DIR = Path(__file__).resolve().parent

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))



# Аутентификация администратора

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "VeoAtelier2026!")



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

            detail="Неверный логин или пароль администратора Atelier VEO",

            headers={"WWW-Authenticate": "Basic"},

        )

    return credentials.username



@app.on_event("startup")

async def startup_event():

    await db.init()



@app.get("/", response_class=HTMLResponse)

async def dashboard(request: Request, username: str = Depends(get_current_username)):

    bot_status, pid = bot_manager.get_status()

    

    async with aiosqlite.connect(db.db_path) as conn:

        async with conn.execute("SELECT COUNT(*) FROM users") as cursor:

            total_users = (await cursor.fetchone())[0]

        async with conn.execute("SELECT COUNT(*) FROM users WHERE sub_type = 'premium'") as cursor:

            active_residents = (await cursor.fetchone())[0]

        async with conn.execute("SELECT SUM(tokens) FROM users") as cursor:

            total_credits = (await cursor.fetchone())[0] or 0



    return templates.TemplateResponse(

        request=request,

        name="dashboard.html",

        context={

            "request": request,

            "status": bot_status,

            "pid": pid,

            "total_users": total_users,

            "active_residents": active_residents,

            "total_credits": total_credits,

            "username": username

        }

    )



@app.post("/bot/start")

async def start_bot(username: str = Depends(get_current_username)):

    bot_manager.start_bot()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)



@app.post("/bot/stop")

async def stop_bot(username: str = Depends(get_current_username)):

    bot_manager.stop_bot()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)



@app.post("/bot/restart")

async def restart_bot(username: str = Depends(get_current_username)):

    bot_manager.restart_bot()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)



@app.get("/users", response_class=HTMLResponse)

async def users_page(request: Request, username: str = Depends(get_current_username)):

    async with aiosqlite.connect(db.db_path) as conn:

        conn.row_factory = aiosqlite.Row

        async with conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 100") as cursor:

            users = await cursor.fetchall()

            

    return templates.TemplateResponse(

        request=request,

        name="users.html",

        context={

            "request": request,

            "users": users,

            "username": username

        }

    )



@app.post("/users/add_credits")

async def add_user_credits(

    user_id: int = Form(...), 

    amount: int = Form(...),

    username: str = Depends(get_current_username)

):

    await db.add_tokens(user_id, amount)

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)



@app.post("/users/grant_residency")

async def grant_residency(

    user_id: int = Form(...),

    months: int = Form(1),

    credits: int = Form(1000),

    username: str = Depends(get_current_username)

):

    """Активация статуса резидента Atelier VEO Club с начислением кредитов и 100% Rollover."""

    await db.add_subscription_credits(user_id=user_id, months=months, credits=credits)

    # Гарантируем флагманскую модель Gemini 4 Argon

    await db.set_setting(f"user_model_{user_id}", "google/gemini-4-argon")

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)



@app.post("/users/set_status")

async def set_user_status(

    user_id: int = Form(...),

    sub_type: str = Form(...),

    username: str = Depends(get_current_username)

):

    async with aiosqlite.connect(db.db_path) as conn:

        await conn.execute("UPDATE users SET sub_type = ? WHERE user_id = ?", (sub_type, user_id))

        await conn.commit()

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)



@app.get("/settings", response_class=HTMLResponse)

async def settings_page(request: Request, username: str = Depends(get_current_username)):

    async with aiosqlite.connect(db.db_path) as conn:

        conn.row_factory = aiosqlite.Row

        async with conn.execute("SELECT * FROM settings ORDER BY key ASC") as cursor:

            settings = await cursor.fetchall()

            

    return templates.TemplateResponse(

        request=request,

        name="settings.html",

        context={

            "request": request,

            "settings": settings,

            "username": username

        }

    )



@app.post("/settings/update")

async def update_setting(

    key: str = Form(...), 

    value: str = Form(...),

    username: str = Depends(get_current_username)

):

    await db.set_setting(key, value)

    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)



@app.get("/persona", response_class=HTMLResponse)

async def persona_page(request: Request, username: str = Depends(get_current_username)):

    persona_data = await memory.get_elin_persona()

    persona_json = json.dumps(persona_data, indent=4, ensure_ascii=False)

    

    return templates.TemplateResponse(

        request=request,

        name="persona.html",

        context={

            "request": request,

            "persona_json": persona_json,

            "username": username

        }

    )



@app.post("/persona/update")

async def update_persona(

    persona_json: str = Form(...),

    username: str = Depends(get_current_username)

):

    try:

        data = json.loads(persona_json)

        await memory.update_elin_persona(json.dumps(data, ensure_ascii=False))

        return RedirectResponse(url="/persona?success=1", status_code=status.HTTP_303_SEE_OTHER)

    except json.JSONDecodeError:

        return RedirectResponse(url="/persona?error=invalid_json", status_code=status.HTTP_303_SEE_OTHER)



@app.get("/broadcast", response_class=HTMLResponse)

async def broadcast_page(request: Request, username: str = Depends(get_current_username)):

    return templates.TemplateResponse(

        request=request,

        name="broadcast.html",

        context={

            "request": request,

            "username": username

        }

    )



@app.post("/broadcast/send")

async def send_broadcast(

    message_text: str = Form(...),

    target_audience: str = Form("all"), # "all", "residents", "guests"

    username: str = Depends(get_current_username)

):

    bot = Bot(token=config.telegram_token)

    count = 0

    errors = 0

    

    query = "SELECT user_id FROM users"

    if target_audience == "residents":

        query = "SELECT user_id FROM users WHERE sub_type IN ('premium', 'admin')"

    elif target_audience == "guests":

        query = "SELECT user_id FROM users WHERE sub_type = 'free'"



    async with aiosqlite.connect(db.db_path) as conn:

        conn.row_factory = aiosqlite.Row

        async with conn.execute(query) as cursor:

            users = await cursor.fetchall()

            

    for user in users:

        try:

            await bot.send_message(chat_id=user['user_id'], text=message_text, parse_mode="HTML")

            count += 1

            await asyncio.sleep(0.05)

        except Exception as e:

            logging.error(f"Broadcast error for {user['user_id']}: {e}")

            errors += 1

            

    await bot.session.close()

    return RedirectResponse(url=f"/broadcast?success={count}&errors={errors}", status_code=status.HTTP_303_SEE_OTHER)



@app.get("/logs", response_class=HTMLResponse)

async def logs_page(request: Request, username: str = Depends(get_current_username)):

    logs = bot_manager.get_logs(150)

    return templates.TemplateResponse(

        request=request,

        name="logs.html",

        context={

            "request": request,

            "logs": logs,

            "username": username

        }

    )





# ==========================================

# ATELIER VEO | EXECUTIVE BOARDROOM ROUTES

# ==========================================



class CouncilSendRequest(BaseModel):

    text: str



class ShieldRunRequest(BaseModel):
    media_path: str
    logo_text: str = "SHIKŪMO"
    label_image: Optional[str] = None
    reference_with_label: Optional[str] = None
    y_offset: Optional[float] = None
    x_offset: Optional[float] = None
    scale: float = 1.0
    angle: float = 0.0
    defringe_bottom: int = 0
    geometry: str = "spherical"
    target_folder: Optional[str] = None
    curvature: float = 0.25
    specular: float = 0.75
    factory_mode: Optional[str] = "clean_production"
    kelvin_temp: Optional[int] = 2700

class ShieldPreviewRequest(BaseModel):
    media_path: str
    label_image: Optional[str] = None
    y_offset: float = 0.48
    x_offset: float = 0.50
    scale: float = 1.0
    angle: float = 0.0
    defringe_bottom: int = 2
    specular: float = 0.75
    geometry: str = "spherical"
    target_folder: Optional[str] = None
    factory_mode: Optional[str] = "clean_production"
    kelvin_temp: Optional[int] = 2700

class ExtractLabelRequest(BaseModel):

    image_path: str

    mode: str = "dark_text"

    curvature: float = 0.25



@app.get("/boardroom", response_class=HTMLResponse)

async def boardroom_page(request: Request, username: str = Depends(get_current_username)):

    session = boardroom_service.get_session()

    media_items = boardroom_service.list_media()

    return templates.TemplateResponse(

        request=request,

        name="boardroom.html",

        context={

            "request": request,

            "username": username,

            "session": session,

            "media_items": media_items,
            "tablet_content": boardroom_service.get_tablet_content(),


        }

    )




class TabletSaveRequest(BaseModel):
    text: str

@app.get("/api/boardroom/tablet")
async def boardroom_get_tablet(username: str = Depends(get_current_username)):
    """Возвращает сохраненный текст режиссерского планшета."""
    return JSONResponse(content={"text": boardroom_service.get_tablet_content()})

@app.post("/api/boardroom/tablet")
async def boardroom_save_tablet(payload: TabletSaveRequest, username: str = Depends(get_current_username)):
    """Надежно сохраняет текст режиссерского планшета на диске сервера."""
    boardroom_service.save_tablet_content(payload.text)
    return JSONResponse(content={"status": "success"})

@app.post("/api/boardroom/tablet/clear")
async def boardroom_clear_tablet(username: str = Depends(get_current_username)):
    """Очищает режиссерский планшет по кнопке продюсера."""
    boardroom_service.clear_tablet_content()
    return JSONResponse(content={"status": "cleared"})

@app.post("/api/boardroom/send")

async def boardroom_send(payload: CouncilSendRequest, username: str = Depends(get_current_username)):

    responses = await boardroom_service.execute_council_cycle(payload.text)

    return JSONResponse(content={"status": "success", "responses": responses})



@app.post("/api/boardroom/export_memo")

async def boardroom_export_memo(username: str = Depends(get_current_username)):

    res = boardroom_service.export_session_memo()

    return JSONResponse(content=res)



@app.post("/api/boardroom/reset")

async def boardroom_reset(username: str = Depends(get_current_username)):

    res = boardroom_service.reset_session()

    return JSONResponse(content={"status": "success", "session": res})



@app.get("/api/boardroom/media")

async def boardroom_media(username: str = Depends(get_current_username)):

    items = boardroom_service.list_media()

    return JSONResponse(content={"status": "success", "media": items})



@app.post("/api/boardroom/preview_shield")
async def boardroom_preview_shield(payload: ShieldPreviewRequest, username: str = Depends(get_current_username)):
    """Сверхбыстрый рендер предпросмотра наложения этикетки (<0.5 сек) для интерактивных ползунков"""
    media_path = Path(payload.media_path)
    if not media_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    shield_script = Path("d:/Antigravity/AI_Video_Agency/scripts/identity_shield.py")
    preview_output = Path("D:/campaigns/fast_shield_preview.png")
    
    cmd = [
        "python", str(shield_script),
        "--input", str(media_path),
        "--output", str(preview_output),
        "--y-offset", str(payload.y_offset),
        "--x-offset", str(payload.x_offset),
        "--scale", str(payload.scale),
        "--angle", str(payload.angle),
        "--defringe-bottom", str(payload.defringe_bottom),
        "--specular", str(payload.specular),
        "--geometry", payload.geometry
    ]
    if payload.label_image and Path(payload.label_image).exists():
        cmd.extend(["--label-image", str(payload.label_image)])
    if getattr(payload, 'factory_mode', None):
        cmd.extend(["--factory-mode", payload.factory_mode])
    if getattr(payload, 'kelvin_temp', None):
        cmd.extend(["--kelvin-temp", str(payload.kelvin_temp)])
    
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if proc.returncode == 0 and preview_output.exists():
            import time
            return JSONResponse(content={
                "status": "success",
                "preview_url": f"/media_stream?path={str(preview_output)}&t={int(time.time()*1000)}"
            })
        else:
            return JSONResponse(content={"status": "error", "detail": proc.stderr or proc.stdout})
    except Exception as e:
        return JSONResponse(content={"status": "error", "detail": str(e)})


class AutoQAStartRequest(BaseModel):
    media_path: str
    label_image: Optional[str] = None
    reference_packshot: Optional[str] = None
    y_offset: float = 58.0
    x_offset: float = 0.0
    scale: float = 1.0
    angle: float = 0.0
    defringe_bottom: int = 2
    specular: float = 0.75
    geometry: str = "spherical"
    target_folder: Optional[str] = None
    factory_mode: Optional[str] = "clean_production"
    kelvin_temp: Optional[int] = 2700

@app.post("/api/boardroom/auto_qa/start")
async def boardroom_auto_qa_start(payload: AutoQAStartRequest, username: str = Depends(get_current_username)):
    ref = payload.reference_packshot
    if not ref or not Path(ref).exists():
        fallback_ref = Path("D:/Antigravity/AI_Video_Agency/campaigns/edeniste_pilot/vanille_irresistible_official_clean.jpg")
        if fallback_ref.exists():
            ref = str(fallback_ref)
        else:
            raise HTTPException(status_code=400, detail="Эталон бренда (packshot) не найден на диске")
    
    # Run loop in background
    asyncio.create_task(
        auto_qa_runner.run(
            media_path=payload.media_path,
            label_image=payload.label_image or "",
            reference_packshot=ref,
            target_folder=payload.target_folder,
            factory_mode=payload.factory_mode or "clean_production",
            kelvin_temp=payload.kelvin_temp or 2700,
            initial_params={
                "y_offset": payload.y_offset,
                "x_offset": payload.x_offset,
                "scale": payload.scale,
                "angle": payload.angle,
                "defringe_bottom": payload.defringe_bottom,
                "specular": payload.specular,
                "geometry": payload.geometry
            }
        )
    )
    return JSONResponse(content={"status": "started"})

@app.get("/api/boardroom/auto_qa/status")
async def boardroom_auto_qa_status(username: str = Depends(get_current_username)):
    return JSONResponse(content=auto_qa_runner.get_telemetry())


class SetTargetFolderRequest(BaseModel):
    target_folder: str

@app.get("/api/boardroom/campaign_folders")
async def boardroom_campaign_folders(username: str = Depends(get_current_username)):
    """Возвращает список доступных папок кампаний для интерактивного выбора."""
    roots = [Path("D:/campaigns"), Path("d:/Antigravity/AI_Video_Agency/campaigns")]
    folders = []
    seen = set()
    
    canonical_default = "D:/campaigns/заказ/выбрано/3"
    folders.append(canonical_default)
    seen.add(canonical_default.replace('\\', '/').lower())
    
    for r in roots:
        if r.exists():
            for p in r.glob("**/*"):
                if p.is_dir() and ".git" not in str(p) and "venv" not in str(p) and "__pycache__" not in str(p):
                    norm = str(p).replace('\\', '/')
                    if norm.lower() not in seen:
                        seen.add(norm.lower())
                        folders.append(norm)
                        if len(folders) >= 25:
                            break
    return JSONResponse(content={
        "status": "success",
        "current_target": auto_qa_runner.target_folder,
        "folders": folders
    })

@app.post("/api/boardroom/set_target_folder")
async def boardroom_set_target_folder(payload: SetTargetFolderRequest, username: str = Depends(get_current_username)):
    folder = payload.target_folder.strip()
    if not folder:
        raise HTTPException(status_code=400, detail="Путь к папке не может быть пустым")
    p = Path(folder)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Невозможно создать или открыть папку: {e}")
    
    auto_qa_runner.set_target_folder(str(p))
    return JSONResponse(content={
        "status": "success",
        "target_folder": str(p),
        "message": f"Папка сохранения кампании успешно установлена: {p}"
    })

@app.post("/api/boardroom/auto_qa/stop")
async def boardroom_auto_qa_stop(username: str = Depends(get_current_username)):
    auto_qa_runner.stop()
    return JSONResponse(content={"status": "stopped"})

@app.post("/api/boardroom/run_shield")

async def boardroom_run_shield(payload: ShieldRunRequest, username: str = Depends(get_current_username)):

    media_path = Path(payload.media_path)

    if not media_path.exists():

        raise HTTPException(status_code=404, detail="Медиа-файл не найден на диске")

    

    shield_script = Path("d:/Antigravity/AI_Video_Agency/scripts/identity_shield.py")

    ext = ".mp4" if media_path.suffix.lower() in [".mp4", ".mov", ".webm"] else ".png"

    output_path = media_path.parent / f"shielded_{media_path.stem}{ext}"

    

    cmd = [

        "python", str(shield_script),

        "--input", str(media_path),

        "--output", str(output_path),

        "--logo", payload.logo_text,

        "--curvature", str(payload.curvature),

        "--specular", str(payload.specular)

    ]

    if payload.label_image and os.path.exists(payload.label_image):

        cmd.extend(["--label-image", str(payload.label_image)])

    if payload.reference_with_label and os.path.exists(payload.reference_with_label):

        cmd.extend(["--reference-with-label", str(payload.reference_with_label)])

    if payload.y_offset is not None:

        cmd.extend(["--y-offset", str(payload.y_offset)])

    if payload.scale != 1.0:

        cmd.extend(["--scale", str(payload.scale)])



    try:

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        return JSONResponse(content={

            "status": "success" if proc.returncode == 0 else "error",

            "output_file": output_path.name,

            "output_path": str(output_path),

            "stdout": proc.stdout[-500:] if proc.stdout else "",

            "stderr": proc.stderr[-500:] if proc.stderr else ""

        })

    except Exception as e:

        return JSONResponse(content={"status": "error", "detail": str(e)})



@app.post("/api/boardroom/extract_label")

async def boardroom_extract_label(payload: ExtractLabelRequest, username: str = Depends(get_current_username)):

    input_path = Path(payload.image_path)

    if not input_path.exists():

        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    

    output_dir = input_path.parent / "extracted_labels"

    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"label_{input_path.stem}.png"

    

    script = Path("d:/Antigravity/AI_Video_Agency/scripts/extract_label.py")

    cmd = [

        "python", str(script),

        "--input", str(input_path),

        "--output", str(output_file),

        "--mode", payload.mode,

        "--curvature", str(payload.curvature)

    ]

    try:

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if proc.returncode == 0:

            clean_ref_file = output_dir / f"clean_ref_{input_path.stem}.jpg"

            profile_file = output_dir / f"profile_{input_path.stem}.json"

            profile_data = None

            if profile_file.exists():

                try:

                    profile_data = json.loads(profile_file.read_text(encoding="utf-8"))

                except Exception:

                    pass

            return JSONResponse(content={

                "status": "success",

                "output_file": output_file.name,

                "output_path": str(output_file),

                "preview_url": f"/media_stream?path={str(output_file)}",

                "clean_ref_file": clean_ref_file.name if clean_ref_file.exists() else None,

                "clean_ref_path": str(clean_ref_file) if clean_ref_file.exists() else None,

                "clean_ref_url": f"/media_stream?path={str(clean_ref_file)}" if clean_ref_file.exists() else None,

                "profile_file": profile_file.name if profile_file.exists() else None,

                "profile_path": str(profile_file) if profile_file.exists() else None,

                "profile_data": profile_data,

                "reference_packshot_path": str(input_path),

                "reference_packshot_name": input_path.name

            })

        else:

            return JSONResponse(content={"status": "error", "detail": proc.stderr or proc.stdout})

    except Exception as e:

        return JSONResponse(content={"status": "error", "detail": str(e)})



class VisualQARequest(BaseModel):

    media_path: str



class CompareVariantsRequest(BaseModel):

    media_paths: list[str]



@app.post("/api/boardroom/visual_qa")

async def boardroom_visual_qa(payload: VisualQARequest, username: str = Depends(get_current_username)):

    res = await boardroom_service.execute_visual_qa(payload.media_path)

    return JSONResponse(content=res)



@app.post("/api/boardroom/compare_variants")

async def boardroom_compare_variants(payload: CompareVariantsRequest, username: str = Depends(get_current_username)):

    res = await boardroom_service.execute_variants_comparison(payload.media_paths)

    return JSONResponse(content=res)



@app.post("/api/boardroom/upload")

async def boardroom_upload(

    file: UploadFile = File(...),

    campaign: Optional[str] = Form(None),

    username: str = Depends(get_current_username)

):

    """

    Прием тяжелых видеофайлов (до 2 Гб и более, 4K ProRes) в студийное хранилище.

    Потоковая запись чанками по 16 Мб исключает перегрузку оперативной памяти.

    """

    try:

        base_campaigns = Path("D:/Antigravity/AI_Video_Agency/campaigns")

        target_dir = base_campaigns / (campaign if campaign else "uploads")

        target_dir.mkdir(parents=True, exist_ok=True)

        

        target_path = target_dir / file.filename

        

        with open(target_path, "wb") as buffer:

            shutil.copyfileobj(file.file, buffer, length=1024 * 1024 * 16)

            

        file_size_mb = round(target_path.stat().st_size / (1024 * 1024), 2)

        

        return JSONResponse(content={

            "status": "success",

            "filename": file.filename,

            "path": str(target_path),

            "size_mb": file_size_mb,

            "type": "video" if target_path.suffix.lower() in [".mp4", ".mov", ".webm"] else "image"

        })

    except Exception as e:

        return JSONResponse(content={"status": "error", "detail": str(e)}, status_code=500)



class SaveWinnerRequest(BaseModel):

    winner_path: str

    target_folder: Optional[str] = None

    new_filename: Optional[str] = None



@app.post("/api/boardroom/save_winner")

async def boardroom_save_winner(payload: SaveWinnerRequest, username: str = Depends(get_current_username)):

    src = Path(payload.winner_path)

    if not src.exists() or not src.is_file():

        raise HTTPException(status_code=404, detail="Файл победителя не найден")

    

    target_dir = Path(payload.target_folder) if payload.target_folder else Path("D:/campaigns/заказ/выбрано/3")

    target_dir.mkdir(parents=True, exist_ok=True)

    

    filename = payload.new_filename if payload.new_filename else f"start_frame_{src.name}"

    dst = target_dir / filename

    

    shutil.copy2(src, dst)

    return JSONResponse(content={

        "status": "success",

        "saved_path": str(dst),

        "filename": filename,

        "message": f"Кадр-победитель успешно сохранен в: {dst}"

    })



@app.get("/api/boardroom/download_media")

async def boardroom_download_media(path: str = Query(...), username: str = Depends(get_current_username)):

    p = Path(path)

    if not p.exists() or not p.is_file():

        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(p, filename=p.name)



@app.get("/media_stream")

async def media_stream(path: str = Query(...), username: str = Depends(get_current_username)):

    media_file = Path(path)

    if not media_file.exists() or not media_file.is_file():

        raise HTTPException(status_code=404, detail="Файл не найден")

    

    ext = media_file.suffix.lower()

    media_type = "video/mp4"

    if ext in [".png"]:

        media_type = "image/png"

    elif ext in [".jpg", ".jpeg"]:

        media_type = "image/jpeg"

    elif ext in [".webp"]:

        media_type = "image/webp"

    elif ext in [".mov"]:

        media_type = "video/quicktime"

    elif ext in [".webm"]:

        media_type = "video/webm"

        

    return FileResponse(media_file, media_type=media_type)



if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time

    # Автоматическое открытие Зала в браузере при старте
    def open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open("http://localhost:8080/boardroom")
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    port = int(os.getenv("ADMIN_PORT", 8080))
    reload_mode = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("admin.app:app", host="0.0.0.0", port=port, reload=reload_mode)