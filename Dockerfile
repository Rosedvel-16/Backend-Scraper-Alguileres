# Usar una imagen base de Python
FROM python:3.13-slim

# Instalar Chromium y ChromeDriver para Selenium Headless
# Esto es crucial para que create_driver() funcione
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libxrandr2 \
    libxcomposite1 \
    libxi6 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxss1 \
    libgtk-3-0 \
    libfontconfig1 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Establecer la carpeta de trabajo
WORKDIR /app

# Copiar archivos de requirements y Procfile
COPY requirements.txt .
COPY Procfile .

# Instalar dependencias de Python (Selenium, Flask, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Comando de inicio del servidor web (usa el Procfile si está presente)
# Gunicorn es el servidor web
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]