FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV BOT_TOKEN=""
ENV DB_PATH="/data/reminders.db"

VOLUME ["/data"]

CMD ["python", "bot.py"]
