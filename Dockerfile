# 1. Imagen base liviana de Python
FROM python:3.11-slim

# 2. Evita buffering en la consola para ver los prints/logs en tiempo real
ENV PYTHONUNBUFFERED=1

# 3. Crear directorio de trabajo interno
WORKDIR /app

# 4. Copiar e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar todo el contenido del repositorio al contenedor
COPY . .

# 6. Comando para arrancar en producción usando Gunicorn.
# Usa bind dinámico al puerto inyectado por Cloud Run ($PORT)
CMD exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 0 app:app
