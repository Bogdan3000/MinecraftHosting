const API_URL = "https://minecraft.bohdan.lol:443";
let userInfo = null; // Хранение данных о пользователе

async function sendCommand(command) {
    let endpoint = "";
    if (command === "/start") endpoint = "/start";
    if (command === "/stop") endpoint = "/stop";
    if (command === "/restart") endpoint = "/restart";
    if (!endpoint) return;

    try {
        const response = await fetch(API_URL + endpoint, {
            method: "POST",
            credentials: "include" // Важно для отправки cookie сессии
        });

        if (response.status === 401 || response.status === 403) {
            // Если пользователь не авторизован или у него нет доступа
            updateConsole("[Система]: Доступ запрещен. Авторизуйтесь с помощью разрешенного аккаунта Google.");
            return;
        }

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
        const response = await fetch(`${API_URL}/command?command=${encodeURIComponent(cmd)}`, {
            method: "POST",
            credentials: "include" // Важно для отправки cookie сессии
        });

        if (response.status === 401 || response.status === 403) {
            // Если пользователь не авторизован или у него нет доступа
            updateConsole("[Система]: Доступ запрещен. Авторизуйтесь с помощью разрешенного аккаунта Google.");
            return;
        }

        const data = await response.json();
        updateConsole(`> ${cmd}\n${data.response}`);
    } catch (error) {
        updateConsole("[Ошибка]: Команда не отправлена");
    }
}

let logErrorShown = false; // Флаг, чтобы не спамить ошибку

async function loadLogs() {
    try {
        const response = await fetch(API_URL + "/logs", {
            credentials: "include" // Важно для отправки cookie сессии
        });

        if (response.status === 401 || response.status === 403) {
            // Если пользователь не авторизован или у него нет доступа - просто не показываем логи
            if (!logErrorShown) {
                updateConsole("[Система]: Авторизуйтесь с помощью разрешенного аккаунта Google для просмотра логов.");
                logErrorShown = true;
            }
            return;
        }

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

// Функция для проверки, если пользователь авторизован через API
async function checkUserLogin() {
    try {
        const response = await fetch(`${API_URL}/api/user`, {
            credentials: "include" // Важно для отправки cookie сессии
        });

        const data = await response.json();
        const greetingText = document.getElementById('greeting-text');

        if (data.authenticated) {
            userInfo = {
                email: data.email,
                name: data.name,
                picture: data.picture,
                authorized: data.authorized
            };

            document.getElementById('user-picture').src = data.picture;
            document.getElementById('google-login').style.display = 'none';
            document.getElementById('user-info').style.display = 'block';
            greetingText.innerText = `Привет, ${data.name}`;

            // Если пользователь авторизован, но не в списке разрешенных
            if (!data.authorized) {
                updateConsole(`[Система]: ${data.message || "У вас нет доступа к управлению сервером. Обратитесь к bohdan.lol."}`);

                // Можно также отключить кнопки для неавторизованных пользователей
                disableControls();
            } else {

                // Включаем элементы управления
                enableControls();
            }
        } else {
            document.getElementById('google-login').style.display = 'block';
            document.getElementById('user-info').style.display = 'none';
            greetingText.innerText = 'Привет, пользователь!';

            // Отключаем элементы управления для неавторизованных пользователей
            disableControls();
        }
    } catch (error) {
        console.error("Ошибка при проверке авторизации:", error);
        document.getElementById('google-login').style.display = 'block';
        document.getElementById('user-info').style.display = 'none';
        disableControls();
    }
}

// Функция для отключения элементов управления
function disableControls() {
    const buttons = document.querySelectorAll('.button-group button, .send-btn');
    buttons.forEach(button => {
        button.disabled = true;
        button.style.opacity = '0.5';
        button.style.cursor = 'not-allowed';
    });
    document.getElementById('command-input').disabled = true;
}

// Функция для включения элементов управления
function enableControls() {
    const buttons = document.querySelectorAll('.button-group button, .send-btn');
    buttons.forEach(button => {
        button.disabled = false;
        button.style.opacity = '1';
        button.style.cursor = 'pointer';
    });
    document.getElementById('command-input').disabled = false;
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

// Функция для выхода через API
async function logout() {
    try {
        await fetch(`${API_URL}/api/logout`, {
            method: "POST",
            credentials: "include"
        });

        // Обновляем отображение
        checkUserLogin();
    } catch (error) {
        console.error("Ошибка при выходе:", error);
    }
}

setInterval(loadLogs, 2000);
loadLogs();
checkUserLogin();