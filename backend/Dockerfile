# Можно явно передать уже проверенный локальный Python-образ с зависимостями.
ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бэкенда
COPY . .

# Открываем порт и запускаем uvicorn
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]