import subprocess
import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from mcrcon import MCRcon
import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
app = FastAPI()

# Разрешаем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройки RCON
RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PASSWORD = "Bogdan3000"
VK_APP_ID = "53155528"
VK_APP_SECRET = "1ISOUachPIBSaQbUumP0"
VK_REDIRECT_URI = "https://minecraft.bohdan.lol/callback"

# Директория сервера и логов
SERVER_DIR = "server"
LOG_FILE = os.path.join(SERVER_DIR, "logs", "latest.log")

server_process = None

def send_command(command: str):
    """Отправляет команду через RCON"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
            return mcr.command(command)
    except Exception as e:
        print(e)
        return "Скорее всего сервер не запущен или возникла проблема связи с сервером"

#@app.on_event("startup")
#async def startup_event():
#    """Автоматически запускает FTP-сервер при старте FastAPI"""
#    ftp_thread = threading.Thread(target=start_ftp_server, daemon=True)
#    ftp_thread.start()

@app.get("/login/vk")
async def login_via_vk():
    """Перенаправляет пользователя на страницу авторизации ВКонтакте"""
    vk_auth_url = (
        f"https://oauth.vk.com/authorize?"
        f"client_id={VK_APP_ID}"
        f"&redirect_uri={VK_REDIRECT_URI}"
        f"&display=page"
        f"&scope=email"
        f"&response_type=code"
        f"&v=5.131"
    )
    return RedirectResponse(url=vk_auth_url)

@app.get("/callback")
async def vk_callback(request: Request):
    """Обрабатывает коллбэк после авторизации через ВК"""
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "Нет кода авторизации"}, status_code=400)

    token_url = (
        f"https://oauth.vk.com/access_token?"
        f"client_id={VK_APP_ID}"
        f"&client_secret={VK_APP_SECRET}"
        f"&redirect_uri={VK_REDIRECT_URI}"
        f"&code={code}"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(token_url)
        data = response.json()

    if "access_token" not in data:
        return JSONResponse({"error": "Ошибка авторизации", "details": data}, status_code=400)

    return JSONResponse(data)  # Здесь будут access_token, user_id, email и т. д.

@app.get("/user")
async def get_user_info(access_token: str):
    """Получает информацию о пользователе из ВК"""
    vk_api_url = f"https://api.vk.com/method/users.get?access_token={access_token}&fields=photo_200,email&v=5.131"

    async with httpx.AsyncClient() as client:
        response = await client.get(vk_api_url)
        data = response.json()

    return JSONResponse(data)

@app.head("/")
async def read_root_head():
    return {}

@app.get("/")
async def get_index():
    return FileResponse("frontend/index.html")

@app.post("/start")
async def start_server():
    """Запускает сервер"""
    global server_process
    if server_process is None:
        server_process = subprocess.Popen(
            [r"server\CustomJAVA\bin\java.exe", "-Xmx5000M", "-Xms5000M", "-jar", "server.jar", "nogui"],
            cwd=SERVER_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        return JSONResponse({"status": "Сервер запущен"})
    return JSONResponse({"status": "Сервер уже работает"}, status_code=400)

@app.post("/stop")
async def stop_server():
    """Останавливает сервер и удаляет логи"""
    global server_process
    if server_process:
        send_command("stop")
        server_process.terminate()
        server_process.wait()
        server_process = None
        time.sleep(2)
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
        return JSONResponse({"status": "Сервер выключен, логи удалены"})
    return JSONResponse({"status": "Сервер не запущен"}, status_code=400)

@app.post("/restart")
async def restart_server():
    """Перезапускает сервер"""
    await stop_server()
    return await start_server()

@app.post("/command")
async def execute_command(command: str):
    """Выполняет команду через RCON"""
    return JSONResponse({"command": command, "response": send_command(command)})

@app.get("/logs")
async def get_logs():
    """Возвращает последние 50 строк логов"""
    if not os.path.exists(LOG_FILE):
        return JSONResponse({"logs": []})

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()[-50:]

    return JSONResponse({"logs": lines})

# ======================== Файловый менеджер через FTP ========================
@app.get("/open_ftp")
async def open_ftp():
    return RedirectResponse(url="ftp://minecraft.bohdan.lol:8001")