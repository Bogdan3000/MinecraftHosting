import subprocess
import os
import time
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from mcrcon import MCRcon

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