# Прогрес Monitor-AI

## ✅ Зроблено
- Створено структуру папок проекту
- Створено глобальний CLAUDE.md (про розробника)
- Створено проектний CLAUDE.md (про проект)
- Створено docs/architecture.md
- Встановлено Superpowers плагін
- Створено docs/progress.md
- requirements.txt — Flask, psutil, pytest
- app.py — Flask сервер + збір даних через psutil
- tests/test_app.py — 8 тестів (всі PASSED)
- templates/index.html — HTML структура дашборду
- static/css/style.css — темна тема (#0a0a0a / #00ff88)
- static/js/main.js — живі графіки Chart.js, оновлення кожну секунду

## 🔄 Зараз робимо
- Злиття feature/monitor-ai-core в main

## 📋 Далі по порядку
- [ ] Тестування в браузері і порівняння з Windows Task Manager

## 🐛 Проблеми і рішення
- (записуємо по ходу)

## 💡 Рішення які прийняли і чому
- Flask обрали бо простий для початківця
- Chart.js бо мінімум налаштувань
- Темна тема бо моніторинг — це термінальний стиль
- Git worktree для ізоляції роботи в окремій гілці
