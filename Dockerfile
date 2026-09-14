FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 QUANTUMLISTENER_DATA=/var/lib/quantumlistener
WORKDIR /app
RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY app app
COPY data data
COPY scripts scripts
RUN pip install --no-cache-dir . gunicorn==23.0.0 && useradd --create-home --uid 10001 quantumlistener && mkdir -p /var/lib/quantumlistener && chown -R quantumlistener /var/lib/quantumlistener
USER quantumlistener
EXPOSE 8080
CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 app.web.server:application"]
