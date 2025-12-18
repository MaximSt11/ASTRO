// === НАСТРОЙКИ ===
// Не забудь проверить эту ссылку!
const BACKEND_URL = "https://api.stateofbrain.ru";

const tg = window.Telegram.WebApp;
tg.expand();

let userId = 0;

// API WRAPPER
async function apiRequest(endpoint, method = 'GET', body = null) {
    const config = {
        method: method,
        keepalive: true
    };

    if (body) {
        // Отправляем строку JSON, но БЕЗ заголовка Content-Type
        // Это обманывает браузер, и он не шлет OPTIONS запрос
        config.body = JSON.stringify(body);
    }

    return await fetch(`${BACKEND_URL}${endpoint}`, config);
}

// --- Обновленный initApp ---
async function initApp() {
    createStars();

    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        const user = tg.initDataUnsafe.user;
        userId = user.id;
        setDisplayName(user.first_name);
        if(user.photo_url) {
            document.getElementById('avatar-container').innerHTML = `<img src="${user.photo_url}" style="width:100%;height:100%;">`;
        } else {
            generateAvatar(user.first_name);
        }
    } else {
        userId = 999;
        setDisplayName("Гость");
        generateAvatar("G");
    }

    try {
        // Запрашиваем профиль. Теперь там приедут и кэшированные прогнозы!
        const res = await apiRequest(`/api/get_profile/${userId}`);
        if (res.ok) {
            const data = await res.json();

            // 1. Заполняем профиль
            if(data.full_name) {
                setDisplayName(data.full_name);
                if (!tg.initDataUnsafe?.user?.photo_url) generateAvatar(data.full_name);
            }
            if(data.birth_date) {
                document.getElementById('birth-date-input').value = data.birth_date;
                updateZodiac(data.birth_date);
            }
            if(data.birth_time) document.getElementById('birth-time-input').value = data.birth_time;
            if(data.birth_place) {
                document.getElementById('birth-place-input').value = data.birth_place;
                document.getElementById('widget-place').innerText = data.birth_place;
            }
            if(data.theme) changeTheme(data.theme);

            // 2. ВСТАВЛЯЕМ КЭШ (Сразу показываем данные!)

            // Натальная карта (анализ)
            if (data.natal_analysis) {
                const output = document.getElementById('astro-analysis-text');
                const btn = document.getElementById('btn-analyze-astro');

                output.innerHTML = data.natal_analysis
                    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
                    .replace(/\n/g, '<br>');

                if(btn) btn.innerText = "Получить новый разбор";
            }

            // Нумерология
            if (data.numerology_analysis) {
                renderNumerology(data.numerology_analysis);
            }

            // Совет дня (если есть)
            if (data.daily_advice) {
                 const output = document.getElementById('daily-advice-text');
                 output.innerText = data.daily_advice;
                 output.style.color = "var(--text-main)";
                 // Кнопку не дизейблим навсегда, вдруг юзер захочет еще (хотя логика бэка вернет то же самое)
            } else {
                // Если совета нет, запрашиваем новый (только если это первый заход)
                getDailyAdvice();
            }

            // Аффирмация (если есть)
            if (data.daily_affirmation) {
                const output = document.getElementById('affirmation-text');
                output.innerText = data.daily_affirmation;
            }

        }
    } catch (e) {
        console.error("Ошибка загрузки:", e);
    }
}

async function saveProfile() {
    const statusEl = document.getElementById('save-status');
    statusEl.innerText = "Сохранение...";
    statusEl.style.color = "#ffd700";

    const fullName = document.getElementById('name-input').value;
    const bDate = document.getElementById('birth-date-input').value;
    const bTime = document.getElementById('birth-time-input').value;
    const bPlace = document.getElementById('birth-place-input').value;
    const theme = document.getElementById('theme-select').value;

    setDisplayName(fullName);
    if(bDate) updateZodiac(bDate);
    document.getElementById('widget-place').innerText = bPlace || "—";
    changeTheme(theme);
    astroLoaded = false; // Сбрасываем кэш астрологии, так как дата могла измениться

    try {
        const res = await apiRequest('/api/update_profile', 'POST', {
            user_id: userId,
            full_name: fullName,
            birth_date: bDate || null,
            birth_time: bTime || null,
            birth_place: bPlace || null,
            theme: theme
        });

        if(res.ok) {
            statusEl.innerText = "Успешно!";
            statusEl.style.color = "#4cd964";
            if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
            setTimeout(() => {
                document.getElementById('settings-modal').classList.remove('active');
                statusEl.innerText = "";
            }, 1000);
        } else {
            statusEl.innerText = "Ошибка сервера";
            statusEl.style.color = "var(--error-color)";
            if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('error');
        }
    } catch (e) {
        statusEl.innerText = "Ошибка сети";
        statusEl.style.color = "var(--error-color)";
    }
}

async function getDailyAdvice() {
    const output = document.getElementById('daily-advice-text');
    const btn = document.querySelector('#page-home .card button');

    output.style.opacity = '0.5';
    btn.disabled = true;

    try {
        const res = await apiRequest('/api/daily_advice', 'POST', {
            user_id: userId,
            message: "advice"
        });
        const data = await res.json();

        if (res.ok) {
            output.innerText = data.reply;
            output.style.color = "var(--text-main)";
            if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
        } else {
            throw new Error(data.detail || "Ошибка");
        }
    } catch (error) {
        output.innerText = "Ошибка: " + error.message;
        output.style.color = "var(--error-color)";
        if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('error');
    } finally {
        output.style.opacity = '1';
        btn.disabled = false;
    }
}

// --- УТИЛИТЫ ---
function setDisplayName(name) {
    document.getElementById('display-name').innerText = name;
    document.getElementById('name-input').value = name;
}

function generateAvatar(name) {
    if(document.getElementById('avatar-container').querySelector('img')) return;
    const initial = name ? name.charAt(0).toUpperCase() : "?";
    const container = document.getElementById('avatar-container');
    container.innerHTML = `<span>${initial}</span>`;
    container.style.background = 'linear-gradient(135deg, #FF9A9E 0%, #FECFEF 100%)';
}

function updateZodiac(dateStr) {
    const date = new Date(dateStr);
    const day = date.getDate();
    const month = date.getMonth() + 1;
    let sign = "Козерог";

    if ((month == 1 && day >= 20) || (month == 2 && day <= 18)) sign = "Водолей";
    else if ((month == 2 && day >= 19) || (month == 3 && day <= 20)) sign = "Рыбы";
    else if ((month == 3 && day >= 21) || (month == 4 && day <= 19)) sign = "Овен";
    else if ((month == 4 && day >= 20) || (month == 5 && day <= 20)) sign = "Телец";
    else if ((month == 5 && day >= 21) || (month == 6 && day <= 21)) sign = "Близнецы";
    else if ((month == 6 && day >= 22) || (month == 7 && day <= 22)) sign = "Рак";
    else if ((month == 7 && day >= 23) || (month == 8 && day <= 22)) sign = "Лев";
    else if ((month == 8 && day >= 23) || (month == 9 && day <= 22)) sign = "Дева";
    else if ((month == 9 && day >= 23) || (month == 10 && day <= 22)) sign = "Весы";
    else if ((month == 10 && day >= 23) || (month == 11 && day <= 21)) sign = "Скорпион";
    else if ((month == 11 && day >= 22) || (month == 12 && day <= 21)) sign = "Стрелец";

    document.getElementById('widget-sign').innerText = sign;
}

function changeTheme(t) {
    document.body.removeAttribute('data-theme');
    if(t !== 'default') document.body.setAttribute('data-theme', t);
    const sel = document.getElementById('theme-select');
    if(sel) sel.value = t;
}

function openSettings() { document.getElementById('settings-modal').classList.add('active'); if(tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light'); }
function closeSettings(e) { if(e.target.id === 'settings-modal') document.getElementById('settings-modal').classList.remove('active'); }

function switchTab(pid, el) {
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    document.getElementById('page-'+pid).classList.add('active');
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
    el.classList.add('active');
    if(tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

function createStars() {
    const container = document.getElementById('star-bg');
    if(!container) return;
    container.innerHTML = '';
    // Уменьшили с 60 до 40 для производительности
    for(let i=0; i<40; i++) {
        const star = document.createElement('div');
        star.className = 'star';
        // Упростили размер
        const size = Math.random() * 2 + 1;
        star.style.width = size + 'px';
        star.style.height = size + 'px';
        star.style.top = Math.random() * 100 + '%';
        star.style.left = Math.random() * 100 + '%';
        star.style.animationDuration = (Math.random() * 3 + 2) + 's';
        star.style.animationDelay = Math.random() * 5 + 's';
        container.appendChild(star);
    }
}

// --- ЛОГИКА АСТРОЛОГИИ ---
let astroLoaded = false; // Флаг: загружены ли данные

async function loadAstroData(force = false) {
    // Если уже загружено и мы не требуем принудительного обновления - выходим
    if (astroLoaded && !force) return;

    const container = document.getElementById('astro-list');
    container.innerHTML = '<div style="text-align: center; padding: 20px; opacity: 0.6;">Вычисляем орбиты...</div>';

    try {
        const res = await apiRequest(`/api/get_natal_chart/${userId}`);
        const data = await res.json();

        if (data.status === 'ok') {
            container.innerHTML = '';

            data.planets.forEach(planet => {
                const row = document.createElement('div');
                row.className = 'planet-row'; // (Можно добавить стиль позже)
                row.style.cssText = 'display:flex; align-items:center; justify-content:space-between; padding:12px; background:rgba(255,255,255,0.05); border-radius:12px; margin-bottom:8px;';

                row.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 20px;">${planet.icon}</span>
                        <span style="font-weight: 500;">${planet.name}</span>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: var(--accent); font-weight: 600;">${planet.sign}</div>
                        <div style="font-size: 11px; opacity: 0.5;">${planet.deg}</div>
                    </div>
                `;
                container.appendChild(row);
            });

            astroLoaded = true; // Запоминаем, что загрузили
        } else {
            container.innerHTML = `<div style="text-align: center; color: var(--error-color);">Ошибка: ${data.error || 'Нет данных'}</div>`;
        }
    } catch (e) {
        console.error(e);
        container.innerHTML = '<div style="text-align: center; color: var(--error-color);">Ошибка связи с космосом</div>';
    }
}

// Модифицируем переключение вкладок
const oldSwitchTab = switchTab;
switchTab = function(pid, el) {
    oldSwitchTab(pid, el);
    if (pid === 'astro') {
        loadAstroData(false); // false = не обновлять, если уже есть
    }
}

// --- АНАЛИЗ ЛИЧНОСТИ ---

async function getAstroInterpretation() {
    const output = document.getElementById('astro-analysis-text');
    const btn = document.getElementById('btn-analyze-astro');

    btn.disabled = true;
    btn.innerText = "Считываем энергию...";
    output.style.opacity = '0.5';

    try {
        const res = await apiRequest('/api/analyze_natal_chart', 'POST', {
            user_id: userId,
            message: "analyze"
        });

        const data = await res.json();

        if (res.ok) {
            // УБРАЛИ marked(data.reply), так как библиотека не подключена

            // Используем простой парсер (твои регулярки):
            let formattedText = data.reply
                .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>') // Жирный
                .replace(/\*(.*?)\*/g, '<i>$1</i>')     // Курсив
                .replace(/\n/g, '<br>');                // Переносы строк

            output.innerHTML = formattedText;

            if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
            btn.innerText = "Получить новый разбор";
        } else {
            output.innerText = "Ошибка: " + (data.detail || "Не удалось получить ответ");
            if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('error');
            btn.innerText = "Попробовать снова";
        }
    } catch (e) {
        console.error(e);
        output.innerText = "Ошибка обработки данных."; // Изменил текст, чтобы отличать
        btn.innerText = "Попробовать снова";
    } finally {
        output.style.opacity = '1';
        btn.disabled = false;
    }
}

// --- НУМЕРОЛОГИЯ ---

// --- Вспомогательная функция для отрисовки Нумерологии ---
function renderNumerology(text) {
    let number = "?";
    let content = text;

    // Парсим YOUR_NUMBER:X
    if (content.includes("YOUR_NUMBER:")) {
        const parts = content.split("\n\n");
        const numPart = parts[0];
        number = numPart.split(":")[1];
        content = parts.slice(1).join("\n\n");
    }

    const html = `
        <div style="display:flex; justify-content:center; margin-bottom:20px;">
            <div style="
                width:80px; height:80px;
                border-radius:50%;
                border: 2px solid var(--accent);
                box-shadow: 0 0 15px var(--accent);
                display:flex; align-items:center; justify-content:center;
                font-size: 32px; font-weight:bold; color:white;
                background: rgba(255,255,255,0.1);
            ">${number}</div>
        </div>
        <div style="white-space: pre-wrap; line-height: 1.6;">${
            content.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
                   .replace(/\*(.*?)\*/g, '<i>$1</i>')
        }</div>
    `;

    document.getElementById('numero-result').innerHTML = html;
    // Меняем кнопку, раз данные уже есть
    const btn = document.getElementById('btn-numero');
    if(btn) btn.innerText = "Пересчитать";
}

// --- Обновленный getNumerology (использует helper) ---
async function getNumerology() {
    const container = document.getElementById('numero-content');
    const btn = document.getElementById('btn-numero');

    container.style.opacity = '0.5';
    btn.disabled = true;
    btn.innerText = "Вычисляем матрицу судьбы...";

    try {
        const res = await apiRequest('/api/get_numerology', 'POST', {
            user_id: userId,
            message: "numero"
        });
        const data = await res.json();

        if (res.ok) {
            renderNumerology(data.reply); // ИСПОЛЬЗУЕМ ОБЩУЮ ФУНКЦИЮ
            if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
        } else {
            document.getElementById('numero-result').innerText = data.reply || "Ошибка";
            if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('error');
             btn.innerText = "Попробовать снова";
        }
    } catch (e) {
        console.error(e);
        document.getElementById('numero-result').innerText = "Ошибка связи";
         btn.innerText = "Попробовать снова";
    } finally {
        container.style.opacity = '1';
        btn.disabled = false;
    }
}

// --- ПРАКТИКИ ---

// 1. Аффирмации
async function getAffirmation() {
    const output = document.getElementById('affirmation-text');
    const btn = document.getElementById('btn-affirmation');

    btn.disabled = true;
    output.style.opacity = '0.5';

    try {
        const res = await apiRequest('/api/get_affirmation', 'POST', {
            user_id: userId,
            message: "affirmation"
        });
        const data = await res.json();

        if (res.ok) {
            output.innerText = data.reply;
            if(tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
        } else {
            output.innerText = "Космос молчит...";
        }
    } catch (e) {
        output.innerText = "Ошибка связи";
    } finally {
        output.style.opacity = '1';
        btn.disabled = false;
    }
}

// 2. Дыхание
let breathingInterval;
let isBreathing = false;

function toggleBreathing() {
    const circle = document.getElementById('breath-circle');
    const text = document.getElementById('breath-text');
    const btn = document.getElementById('btn-breath');

    if (isBreathing) {
        // Стоп
        isBreathing = false;
        circle.classList.remove('breathing-active');
        text.innerText = "Начнём?";
        btn.innerText = "Начать практику";
        clearInterval(breathingInterval);
        return;
    }

    // Старт
    isBreathing = true;
    circle.classList.add('breathing-active');
    btn.innerText = "Закончить";

    // Логика текста (синхронно с CSS анимацией 12с)
    // 0-35% (0-4.2с) = Вдох
    // 35-65% (4.2-7.8с) = Задержка
    // 65-100% (7.8-12с) = Выдох

    const runCycle = () => {
        text.innerText = "Вдох...";
        if(tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');

        setTimeout(() => {
            if(!isBreathing) return;
            text.innerText = "Держим...";
        }, 4200);

        setTimeout(() => {
            if(!isBreathing) return;
            text.innerText = "Выдох...";
            if(tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        }, 7800);
    };

    runCycle();
    breathingInterval = setInterval(runCycle, 12000);
}

// Старт
initApp();