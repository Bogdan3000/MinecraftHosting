const API_URL = "https://minecraft.bohdan.lol:443";
let userInfo = null; // Хранение данных о пользователе

async function sendCommand(command) {
    let endpoint = "";
    if (command === "/start") endpoint = "/start";
    if (command === "/stop") endpoint = "/stop";
    if (command === "/restart") endpoint = "/restart";
    if (!endpoint) return;

    try {
        const response = await fetch(API_URL + endpoint, { method: "POST" });
        const data = await response.json();
        updateConsole(`[Система]: ${data.status}`);
    } catch (error) {
        updateConsole("[Ошибка]: Сервер недоступен");
    }
}

async function sendCustomCommand() {
    let cmd = document.getElementById("command-input").value.trim();
    if (!cmd) return alert("Введите команду!");

    try {
        const response = await fetch(`${API_URL}/command?command=${encodeURIComponent(cmd)}`, { method: "POST" });
        const data = await response.json();
        updateConsole(`> ${cmd}\n${data.response}`);
    } catch (error) {
        updateConsole("[Ошибка]: Команда не отправлена");
    }
}

let logErrorShown = false; // Флаг, чтобы не спамить ошибку

async function loadLogs() {
    try {
        const response = await fetch(API_URL + "/logs");
        if (!response.ok) throw new Error("Сервер вернул ошибку");

        const data = await response.json();
        updateConsole(data.logs ? data.logs.join("\n") : "Логи пусты");

        logErrorShown = false; // Сбрасываем флаг, если логи загрузились
    } catch (error) {
        if (!logErrorShown) {
            updateConsole("[Система]: Сервер выключен или не удалось загрузить логи");
            logErrorShown = true; // Устанавливаем флаг, чтобы не спамить
        }
    }
}

function updateConsole(message) {
    const consoleOutput = document.getElementById("console-output");
    consoleOutput.innerText += `\n${message}`;
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

function googleLogin() {
    window.location.href = `${API_URL}/google-login`;
}

async function checkUserLogin() {
    // Извлекаем данные из cookies
    const email = getCookie('user_email');
    const name = getCookie('user_name');

    if (email && name) {
        userInfo = { email, name };
        document.getElementById('user-email').innerText = `Вход выполнен как: ${name} (${email})`;
        document.getElementById('google-login').style.display = 'none';
        document.getElementById('user-info').style.display = 'block';
    } else {
        document.getElementById('google-login').style.display = 'block';
        document.getElementById('user-info').style.display = 'none';
    }
}

// Функция для получения значения cookie по имени
function getCookie(name) {
    let match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : null;
}


function logout() {
    document.cookie = "user_email=; max-age=0; path=/";
    document.cookie = "user_name=; max-age=0; path=/";
    userInfo = null;
    window.location.href = "/"; // Перезагрузка страницы
}


setInterval(loadLogs, 2000);
loadLogs();
checkUserLogin();
