FROM python:3.12-slim

WORKDIR /app

RUN mkdir -p /data /data/uploads

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY webapp/ ./webapp/
COPY config.example.env .
COPY start.sh /app/start.sh

ENV DATA_DIR=/data
ENV PORT=80
EXPOSE 80

WORKDIR /app/backend
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
