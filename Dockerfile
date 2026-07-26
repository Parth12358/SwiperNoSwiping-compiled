# SwiperNoSwiping — hosted brain + landing page in one service (Railway)
FROM python:3.12-slim

WORKDIR /app

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/
COPY docs/ ./docs/

ENV PORT=8000
WORKDIR /app/server
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
