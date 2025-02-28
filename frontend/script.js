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

// Функция для получения значения cookie по имени
function getCookie(name) {
    let match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : null;
}


// Функция для проверки, если пользователь авторизован
async function checkUserLogin() {
    const email = getCookie('user_email');
    const name = getCookie('user_name');
    const picture = getCookie('picture');
    if (email && name && picture) {
        userInfo = { email, name, picture };
        const cleanPictureUrl = picture.replace(/"/g, '');
        document.getElementById('user-email').innerText = `Привет, ${name}`; // Используем только имя
        document.getElementById('user-picture').src = cleanPictureUrl;
        document.getElementById('google-login').style.display = 'none';
        document.getElementById('user-info').style.display = 'block';
    } else {
        document.getElementById('google-login').style.display = 'block';
        document.getElementById('user-info').style.display = 'none';
    }
}

// Функция для отображения кнопки "Выйти" при клике на фото пользователя
function toggleLogoutButton() {
    const logoutButton = document.getElementById('logout-btn');
    if (logoutButton.style.display === 'none') {
        logoutButton.style.display = 'block';
    } else {
        logoutButton.style.display = 'none';
    }
}

// Функция для выхода
function logout() {
    document.cookie = "user_name=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
    document.cookie = "user_email=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
    document.cookie = "picture=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
    checkUserLogin(); // Обновляем отображение
}



setInterval(loadLogs, 2000);
loadLogs();
checkUserLogin();
