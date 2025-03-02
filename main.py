import os
import asyncio
import subprocess
import secrets
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, EmailStr
from mcrcon import MCRcon

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("api.log")
    ]
)
logger = logging.getLogger("minecraft-server-api")

# Load environment variables
load_dotenv()

# Constants
SERVER_DIR = "server"
LOG_FILE = os.path.join(SERVER_DIR, "logs", "latest.log")
SESSION_LIFETIME = 7  # days
MAX_RECENT_COMMANDS = 10
COMMAND_COOLDOWN = 1  # seconds
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://minecraft.bohdan.lol/")

# Initialize FastAPI app
app = FastAPI(
    title="Minecraft Server Manager",
    description="API for managing a Minecraft server",
    version="2.0.0"
)

# Add session middleware with proper configuration
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", secrets.token_urlsafe(32)),
    max_age=SESSION_LIFETIME * 24 * 60 * 60,  # Convert days to seconds
    same_site="lax",  # Prevent CSRF
    https_only=True  # Ensure secure cookies
)

# CORS configuration
origins = [
    FRONTEND_URL,
    # Add any additional origins as needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files with caching headers
app.mount("/static", StaticFiles(directory="frontend"), name="static")
app.mount("/img", StaticFiles(directory="frontend/img"), name="img")

# Global variables
server_process: Optional[subprocess.Popen] = None
state_tokens: Dict[str, Dict[str, Any]] = {}
recent_commands: List[Dict[str, Any]] = []
last_command_time: Dict[str, datetime] = {}


# ----- Models -----
class CommandRequest(BaseModel):
    command: str


class UserInfo(BaseModel):
    email: EmailStr
    name: str
    picture: str


class UserResponse(BaseModel):
    authenticated: bool
    authorized: bool = False
    name: Optional[str] = None
    email: Optional[str] = None
    picture: Optional[str] = None
    message: Optional[str] = None


# ----- Helper functions -----
def get_authorized_emails() -> List[str]:
    """Get list of authorized email addresses from environment variable."""
    auth_emails = os.getenv("AUTHORIZED_USERS", "")
    if not auth_emails:
        return []
    return [email.strip().lower() for email in auth_emails.split(",")]


async def send_command(command: str) -> str:
    """Send command to Minecraft server via RCON with proper error handling."""
    try:
        host = os.getenv("RCON_HOST", "localhost")
        password = os.getenv("RCON_PASSWORD", "")
        port = int(os.getenv("RCON_PORT", "25575"))

        # Execute in thread pool to avoid blocking
        def execute_rcon():
            with MCRcon(host, password, port) as mcr:
                return mcr.command(command)

        return await asyncio.to_thread(execute_rcon)
    except ConnectionRefusedError:
        logger.error(f"RCON connection refused. Is the server running?")
        return "[Система]: Сервер не принимает RCON-подключения. Возможно, сервер не запущен."
    except TimeoutError:
        logger.error(f"RCON connection timed out")
        return "[Система]: Превышено время ожидания RCON-соединения."
    except Exception as e:
        logger.error(f"RCON error: {str(e)}")
        return f"[Система]: Ошибка RCON: {str(e)}"


async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Check user authorization from session data."""
    if "user" not in request.session:
        return None

    user = request.session["user"]

    # Check if user email is in the list of authorized emails
    authorized_emails = get_authorized_emails()

    # If no authorized emails are specified, consider all users authorized
    if not authorized_emails:
        return user

    if user["email"].lower() in authorized_emails:
        return user

    # If email is not in the list, user is not authorized
    return user  # Return user info but authorization check will be done separately


async def check_command_rate_limit(email: str) -> bool:
    """Check if the user has sent a command too recently."""
    now = datetime.now()
    if email in last_command_time:
        time_since_last = (now - last_command_time[email]).total_seconds()
        if time_since_last < COMMAND_COOLDOWN:
            return False

    last_command_time[email] = now
    return True


async def read_log_file(max_lines: int = 50) -> List[str]:
    """Read the latest log file asynchronously."""
    if not os.path.exists(LOG_FILE):
        return []

    try:
        # Use async file operations to avoid blocking
        def read_logs():
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                return lines[-max_lines:] if lines else []

        return await asyncio.to_thread(read_logs)
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        return [f"[Система]: Ошибка чтения логов: {str(e)}"]


async def clean_expired_tokens():
    """Remove expired state tokens."""
    now = datetime.now()
    expired = [
        token for token, data in state_tokens.items()
        if now - data["created"] > timedelta(minutes=10)
    ]
    for token in expired:
        state_tokens.pop(token, None)


# ----- Routes -----
@app.get("/")
async def get_index():
    """Serve the main page."""
    return FileResponse("frontend/index.html")


@app.get("/api/user")
async def get_user_info(request: Request) -> UserResponse:
    """Return information about the current user."""
    # First check if user exists in session
    if "user" not in request.session:
        return UserResponse(authenticated=False)

    user = request.session["user"]
    authorized_emails = get_authorized_emails()

    # Check if user is authorized
    is_authorized = not authorized_emails or user["email"].lower() in authorized_emails

    # Return appropriate response
    if not is_authorized:
        return UserResponse(
            authenticated=True,
            authorized=False,
            name=user["name"],
            email=user["email"],
            picture=user["picture"],
            message="У вас нет доступа к управлению сервером"
        )

    return UserResponse(
        authenticated=True,
        authorized=True,
        name=user["name"],
        email=user["email"],
        picture=user["picture"]
    )


@app.post("/api/logout")
async def logout_user(request: Request):
    """Log out the user by removing session data."""
    request.session.pop("user", None)
    return JSONResponse({"status": "success", "message": "Вы вышли из системы"})


@app.get("/api/server/status")
async def server_status(request: Request):
    """Check if the server is running."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"authenticated": False}, status_code=401)

    authorized_emails = get_authorized_emails()
    is_authorized = not authorized_emails or user["email"].lower() in authorized_emails
    if not is_authorized:
        return JSONResponse({"status": "Доступ запрещен"}, status_code=403)

    global server_process
    is_running = server_process is not None and server_process.poll() is None

    return JSONResponse({
        "status": "running" if is_running else "stopped",
        "uptime": "Unknown"  # Could be enhanced to track actual uptime
    })


@app.post("/api/server/start")
async def start_server(request: Request):
    """Start the Minecraft server."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"status": "Необходима авторизация"}, status_code=401)

    authorized_emails = get_authorized_emails()
    is_authorized = not authorized_emails or user["email"].lower() in authorized_emails
    if not is_authorized:
        return JSONResponse({"status": "Доступ запрещен"}, status_code=403)

    global server_process

    # Check if server is already running
    if server_process and server_process.poll() is None:
        return JSONResponse({"status": "Сервер уже работает"}, status_code=400)

    try:
        # Java path with more flexible configuration
        java_path = os.getenv("JAVA_PATH", r"server\CustomJAVA\bin\java.exe")
        java_args = os.getenv("JAVA_ARGS", "-Xmx5000M -Xms5000M").split()
        server_jar = os.getenv("SERVER_JAR", "server.jar")

        # Build command line arguments
        cmd = [java_path] + java_args + ["-jar", server_jar, "nogui"]

        # Log the command being executed
        logger.info(f"Starting server with command: {' '.join(cmd)}")

        # Start server process
        server_process = subprocess.Popen(
            cmd,
            cwd=SERVER_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

        # Add to recent commands
        recent_commands.append({
            "user": user["email"],
            "command": "start",
            "timestamp": datetime.now().isoformat(),
            "result": "success"
        })

        return JSONResponse({"status": "Сервер запущен"})
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        return JSONResponse(
            {"status": f"[Система]: Ошибка запуска сервера: {str(e)}"},
            status_code=500
        )


@app.post("/api/server/stop")
async def stop_server(request: Request):
    """Stop the Minecraft server gracefully."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"status": "Необходима авторизация"}, status_code=401)

    authorized_emails = get_authorized_emails()
    is_authorized = not authorized_emails or user["email"].lower() in authorized_emails
    if not is_authorized:
        return JSONResponse({"status": "Доступ запрещен"}, status_code=403)

    global server_process

    if not server_process or server_process.poll() is not None:
        return JSONResponse({"status": "Сервер не запущен"}, status_code=400)

    try:
        # Try to stop server gracefully using RCON
        stop_result = await send_command("stop")
        logger.info(f"RCON stop command result: {stop_result}")

        # Wait for process to terminate (with timeout)
        try:
            server_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.warning("Server didn't stop gracefully, forcing termination")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.error("Server process couldn't be terminated, killing it")
                server_process.kill()

        server_process = None

        # Add to recent commands
        recent_commands.append({
            "user": user["email"],
            "command": "stop",
            "timestamp": datetime.now().isoformat(),
            "result": "success"
        })

        # Optionally clear logs
        if os.path.exists(LOG_FILE) and os.getenv("CLEAR_LOGS_ON_STOP").lower() == "true":
            try:
                os.remove(LOG_FILE)
            except Exception as e:
                logger.error(f"Error removing log file: {str(e)}")

        return JSONResponse({"status": "Сервер выключен"})
    except Exception as e:
        logger.error(f"Error stopping server: {str(e)}")
        return JSONResponse(
            {"status": f"[Система]: Ошибка остановки сервера: {str(e)}"},
            status_code=500
        )


@app.post("/api/server/restart")
async def restart_server(request: Request):
    """Restart the Minecraft server."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"status": "Необходима авторизация"}, status_code=401)

    authorized_emails = get_authorized_emails()
    is_authorized = not authorized_emails or user["email"].lower() in authorized_emails
    if not is_authorized:
        return JSONResponse({"status": "Доступ запрещен"}, status_code=403)

    try:
        # Try to stop server first
        stop_response = await stop_server(request)

        if stop_response.status_code not in (200, 400):
            return stop_response

        # Wait a bit to ensure server process is fully terminated
        await asyncio.sleep(2)

        # Start server again
        start_response = await start_server(request)

        # Add to recent commands
        recent_commands.append({
            "user": user["email"],
            "command": "restart",
            "timestamp": datetime.now().isoformat(),
            "result": "success"
        })

        return start_response
    except Exception as e:
        logger.error(f"Error restarting server: {str(e)}")
        return JSONResponse(
            {"status": f"[Система]: Ошибка перезапуска сервера: {str(e)}"},
            status_code=500
        )


@app.post("/api/server/command")
async def execute_command(command_req: CommandRequest, request: Request):
    """Execute a command on the Minecraft server via RCON."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"status": "Необходима авторизация"}, status_code=401)

    authorized_emails = get_authorized_emails()
    is_authorized = not authorized_emails or user["email"].lower() in authorized_emails
    if not is_authorized:
        return JSONResponse({"status": "Доступ запрещен"}, status_code=403)

    # Check rate limit
    if not await check_command_rate_limit(user["email"]):
        return JSONResponse(
            {"status": "Слишком много команд. Подождите немного."},
            status_code=429
        )

    command = command_req.command.strip()

    # Log the command
    logger.info(f"User {user['email']} executing command: {command}")

    try:
        # Execute command via RCON
        response = await send_command(command)

        # Add to recent commands history
        recent_commands.append({
            "user": user["email"],
            "command": command,
            "timestamp": datetime.now().isoformat(),
            "result": "success"
        })

        # Maintain max length of recent commands
        if len(recent_commands) > MAX_RECENT_COMMANDS:
            recent_commands.pop(0)

        return JSONResponse({
            "command": command,
            "response": response,
            "status": "success"
        })
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": f"[Система]: Ошибка выполнения команды: {str(e)}"},
            status_code=500
        )


@app.get("/api/server/logs")
async def get_logs(request: Request, lines: int = 50 ):
    """Return the latest lines from the server log file."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"status": "Необходима авторизация"}, status_code=401)

    authorized_emails = get_authorized_emails()
    is_authorized = not authorized_emails or user["email"].lower() in authorized_emails
    if not is_authorized:
        return JSONResponse({"status": "Доступ запрещен"}, status_code=403)

    try:
        # Limit maximum lines to prevent abuse
        max_lines = min(lines, 500)
        log_lines = await read_log_file(max_lines)

        if not log_lines:
            return Response(status_code=204)  # No content

        return JSONResponse({"logs": log_lines})
    except Exception as e:
        logger.error(f"Error reading logs: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": f"[Система]: Ошибка чтения логов: {str(e)}"},
            status_code=500
        )


@app.get("/api/server/commands/history")
async def get_command_history(request: Request):
    """Return the history of recent commands."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"status": "Необходима авторизация"}, status_code=401)

    authorized_emails = get_authorized_emails()
    is_authorized = not authorized_emails or user["email"].lower() in authorized_emails
    if not is_authorized:
        return JSONResponse({"status": "Доступ запрещен"}, status_code=403)

    return JSONResponse({"commands": recent_commands})


@app.get("/auth/google")
async def google_login():
    """Create a login URL for Google OAuth."""
    # Clean expired tokens periodically
    await clean_expired_tokens()

    # Generate a secure state token
    state = secrets.token_urlsafe(32)
    state_tokens[state] = {
        "created": datetime.now(),
        "used": False
    }

    # Build the OAuth URL
    client_id = os.getenv("google_client_id")
    redirect_uri = os.getenv("google_redirect_uri")

    if not client_id or not redirect_uri:
        logger.error("Missing Google OAuth configuration")
        raise HTTPException(
            status_code=500,
            detail="OAuth configuration is incomplete"
        )

    url = (
        f"https://accounts.google.com/o/oauth2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=email profile"
        f"&state={state}"
        "&prompt=select_account"  # Force account selection
    )

    return RedirectResponse(url)


@app.get("/auth/callback")
async def google_callback(request: Request, code: str, state: str):
    """Handle the callback from Google OAuth."""
    # Verify state token
    if state not in state_tokens:
        raise HTTPException(status_code=400, detail="Invalid state token")

    # Prevent token reuse
    if state_tokens[state]["used"]:
        raise HTTPException(status_code=400, detail="State token already used")

    # Mark token as used
    state_tokens[state]["used"] = True

    try:
        # Exchange code for access token
        client_id = os.getenv("google_client_id")
        client_secret = os.getenv("google_client_secret")
        redirect_uri = os.getenv("google_redirect_uri")
        token_url = os.getenv("google_token_url")

        if not all([client_id, client_secret, redirect_uri, token_url]):
            logger.error("Missing Google OAuth configuration")
            raise HTTPException(
                status_code=500,
                detail="OAuth configuration is incomplete"
            )

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                timeout=10.0  # Add timeout for safety
            )

        token_data = token_response.json()
        if "error" in token_data:
            logger.error(f"Token error: {token_data['error']}")
            raise HTTPException(
                status_code=400,
                detail=f"Authentication error: {token_data.get('error_description', token_data['error'])}"
            )

        access_token = token_data["access_token"]

        # Get user information
        userinfo_url = os.getenv("google_userinfo_url")
        if not userinfo_url:
            raise HTTPException(
                status_code=500,
                detail="OAuth configuration is incomplete"
            )

        async with httpx.AsyncClient() as client:
            userinfo_response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0
            )

        userinfo = userinfo_response.json()

        # Validate required user info
        required_fields = ["email", "name", "picture"]
        if not all(field in userinfo for field in required_fields):
            logger.error(f"Missing required user info: {userinfo}")
            raise HTTPException(
                status_code=400,
                detail="Incomplete user information received"
            )

        # Save user data in session
        request.session["user"] = {
            "email": userinfo["email"],
            "name": userinfo["name"],
            "picture": userinfo["picture"],
            "login_time": datetime.now().isoformat()
        }

        # Log successful login
        logger.info(f"User logged in: {userinfo['email']}")

        # Redirect to frontend
        return RedirectResponse(FRONTEND_URL)
    except httpx.RequestError as e:
        logger.error(f"Request error during OAuth flow: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to communicate with authentication service"
        )
    except Exception as e:
        logger.error(f"Error during OAuth callback: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Authentication error"
        )


# Legacy routes for backward compatibility
@app.post("/start")
async def legacy_start(request: Request):
    return await start_server(request)


@app.post("/stop")
async def legacy_stop(request: Request):
    return await stop_server(request)


@app.post("/restart")
async def legacy_restart(request: Request):
    return await restart_server(request)


@app.post("/command")
async def legacy_command(command: str, request: Request):
    command_req = CommandRequest(command=command)
    return await execute_command(command_req, request)


@app.get("/logs")
async def legacy_get_logs(request: Request):
    return await get_logs(request)


@app.get("/google-login")
async def legacy_google_login():
    return await google_login()


@app.get("/callback")
async def legacy_callback(request: Request, code: str, state: str):
    return await google_callback(request, code, state)


# Server startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("Server starting up")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Server shutting down")
    global server_process
    if server_process:
        try:
            # Try graceful shutdown first
            await send_command("stop")
            try:
                server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force termination if needed
                server_process.terminate()
        except Exception as e:
            logger.error(f"Error during server shutdown: {str(e)}")