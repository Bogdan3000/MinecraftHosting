import subprocess
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from mcrcon import MCRcon

app = FastAPI()

# Разрешаем CORS, чтобы фронтенд мог отправлять запросы
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Лучше указать конкретный домен фронтенда
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройки RCON
RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PASSWORD = "Bogdan3000"

# Файл логов
LOG_FILE = r"server\logs\latest.log"  # Укажи правильный путь

server_process = None  # Переменная для хранения процесса сервера


def send_command(command: str):
    """Отправляет команду через RCON и возвращает ответ"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
            response = mcr.command(command)
            return response
    except Exception as e:
        return str(e)


@app.get("/")
async def get_index():
    return FileResponse("frontend/index.html")


@app.post("/start")
async def start_server():
    """Запускает сервер в новом окне"""
    global server_process
    if server_process is None:
        server_process = subprocess.Popen(
            [r"server\CustomJAVA\bin\java.exe", "-Xmx1024M", "-Xmx1024M", "-jar", "server.jar", "nogui"],
            cwd="server",
            creationflags=subprocess.CREATE_NEW_CONSOLE  # Открывает в новом окне (Windows)
        )
        return JSONResponse(content={"status": "Сервер запущен в новом окне"})
    else:
        return JSONResponse(content={"status": "Сервер уже работает"}, status_code=400)


import time

@app.post("/stop")
async def stop_server():
    """Останавливает сервер через RCON и удаляет логи"""
    global server_process
    try:
        if server_process:
            send_command("stop")
            server_process.terminate()
            server_process.wait()
            server_process = None
            time.sleep(2)
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
            return JSONResponse(content={"status": "Сервер выключен, логи удалены"})
        else:
            return JSONResponse(content={"status": "Сервер не запущен"}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/restart")
async def restart_server():
    """Перезапускает сервер"""
    await stop_server()
    return await start_server()


@app.post("/command")
async def execute_command(command: str):
    """Выполняет команду через RCON"""
    response = send_command(command)
    return JSONResponse(content={"command": command, "response": response})


@app.get("/logs")
async def get_logs():
    """Возвращает последние 50 строк логов, если файл есть"""
    if not os.path.exists(LOG_FILE):
        return JSONResponse(content={"logs": []})

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()[-50:]

    return JSONResponse(content={"logs": lines})
