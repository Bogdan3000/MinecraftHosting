import subprocess
import os
import time
import httpx
import secrets

from fastapi import HTTPException
from mcrcon import MCRcon
from fastapi import Cookie

from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
app = FastAPI()

# Разрешаем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")
app.mount("/img", StaticFiles(directory="frontend/img"), name="img")

RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PASSWORD = "Bogdan3000"

SERVER_DIR = "server"
LOG_FILE = os.path.join(SERVER_DIR, "logs", "latest.log")
server_process = None

GOOGLE_CLIENT_ID = "940520391101-cbnve2vqv50ia8updtm9uu89447rv96l.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_REDIRECT_URI = "https://minecraft.bohdan.lol/callback"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
state_tokens = {}


def send_command(command: str):
    """Отправляет команду через RCON"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
            return mcr.command(command)
    except Exception as e:
        print(e)
        return "Скорее всего сервер не запущен или возникла проблема связи с сервером"


# @app.on_event("startup")
# async def startup_event():
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
        return JSONResponse({"status": "Сервер выключен"})
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
        return Response(status_code=204)  # Пустой ответ без тела

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()[-50:]

    if not lines:
        return Response(status_code=204)  # Пустой ответ без тела

    return JSONResponse({"logs": lines})

@app.get("/google-login")
async def google_login():
    """Формируем ссылку для входа через Google"""
    state = secrets.token_urlsafe(16)
    state_tokens[state] = True
    url = (
        "https://accounts.google.com/o/oauth2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=email profile"
        f"&state={state}"
    )
    return RedirectResponse(url)

@app.get("/callback")
async def google_callback(code: str, state: str):
    if state not in state_tokens:
        raise HTTPException(status_code=400, detail="Invalid state")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI,
            },
        )
    token_data = response.json()

    if "error" in token_data:
        raise HTTPException(status_code=400, detail=token_data["error"])

    access_token = token_data["access_token"]

    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )

    userinfo = userinfo_response.json()
    print(userinfo["picture"])
    # Сохраняем данные о пользователе в cookie
    response = RedirectResponse(f"https://minecraft.bohdan.lol/")
    response.set_cookie("user_email", userinfo['email'])
    response.set_cookie("user_name", userinfo['name'])
    response.set_cookie("picture", userinfo["picture"])

    return response
