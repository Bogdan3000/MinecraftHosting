const API_URL = "https://minecraft.bohdan.lol:443";
let userInfo = null; // Хранение данных о пользователе

async function sendCommand(command) {
    let endpoint = "";
    if (command === "/start") endpoint = "/start";
    if (command === "/stop") endpoint = "/stop";
    if (command === "/restart") endpoint = "/restart";
    if (!endpoint) return;

    // Добавляем эффект нажатия кнопки
    const buttonMap = {
        "/start": document.querySelector(".start"),
        "/stop": document.querySelector(".stop"),
        "/restart": document.querySelector(".restart")
    };

    // Анимация нажатия
    const button = buttonMap[command];
    if (button) {
        button.classList.add("pressed");
        setTimeout(() => button.classList.remove("pressed"), 300);
    }

    try {
        updateConsole(`[Система]: Отправка команды ${command.substring(1)}...`);

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

    // Анимация нажатия кнопки
    const button = document.querySelector(".send-btn");
    button.classList.add("pressed");
    setTimeout(() => button.classList.remove("pressed"), 300);

    try {
        updateConsole(`> ${cmd}`);

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
        updateConsole(data.response);

        // Очищаем поле ввода после успешной отправки
        document.getElementById("command-input").value = "";
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

    // Добавляем анимацию для новых сообщений
    const messageElement = document.createElement("div");
    messageElement.className = "console-message";
    messageElement.textContent = message;
    messageElement.style.opacity = "0";

    // Добавляем сообщение с сохранением формата переноса строк
    consoleOutput.innerText += `\n${message}`;

    // Прокручиваем вниз с плавной анимацией
    consoleOutput.scrollTo({
        top: consoleOutput.scrollHeight,
        behavior: "smooth"
    });
}

function googleLogin() {
    // Анимация нажатия
    const loginBtn = document.querySelector(".login-btn");
    loginBtn.classList.add("pressed");
    setTimeout(() => {
        window.location.href = `${API_URL}/google-login`;
    }, 300);
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
            document.getElementById('user-info').style.display = 'flex'; // Изменено на flex для улучшения выравнивания
            greetingText.innerText = `Привет, ${data.name}!`;

            // Если пользователь авторизован, но не в списке разрешенных
            if (!data.authorized) {
                updateConsole(`[Система]: ${data.message || "У вас нет доступа к управлению сервером. Обратитесь к bohdan.lol."}`);
                disableControls();
            } else {
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

    // Используем класс вместо inline стиля для плавной анимации
    if (logoutButton.classList.contains('visible')) {
        logoutButton.classList.remove('visible');
    } else {
        logoutButton.classList.add('visible');
    }
}

// Закрывать меню при клике за его пределами
document.addEventListener('click', function(event) {
    const userPicture = document.getElementById('user-picture');
    const logoutBtn = document.getElementById('logout-btn');

    if (event.target !== userPicture && event.target !== logoutBtn) {
        logoutBtn.classList.remove('visible');
    }
});

// Функция для выхода через API
async function logout() {
    try {
        const logoutBtn = document.getElementById('logout-btn');
        logoutBtn.classList.add('pressed');

        await fetch(`${API_URL}/api/logout`, {
            method: "POST",
            credentials: "include"
        });

        // Добавляем небольшую задержку для анимации
        setTimeout(() => {
            // Обновляем отображение
            checkUserLogin();
            // Сбрасываем консоль
            document.getElementById("console-output").innerText = "[Система]: Вы вышли из системы. Авторизуйтесь снова для управления сервером.";
            // Скрываем кнопку выхода
            logoutBtn.classList.remove('visible');
        }, 300);
    } catch (error) {
        console.error("Ошибка при выходе:", error);
    }
}

// Обработчик для отправки команды по нажатию Enter
document.getElementById('command-input').addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
        sendCustomCommand();
    }
});

// Добавляем анимацию при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Установим начальный текст консоли
    document.getElementById("console-output").innerText = "[Система]: Консоль загружается...";
});

setInterval(loadLogs, 2000);
loadLogs();
checkUserLogin();