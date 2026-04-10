FROM python:3.11-slim

WORKDIR /bot

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

RUN useradd -m -u 1001 botuser && chown -R botuser:botuser /bot
USER botuser

CMD ["python", "bot.py"]
