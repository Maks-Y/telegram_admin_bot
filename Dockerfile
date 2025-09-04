FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY bot /app/bot

# База/файлы — в /app/data
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data

CMD ["python", "-m", "bot.main"]
