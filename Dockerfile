FROM python:3.11

WORKDIR /opt/app

COPY requirements.txt .
RUN apt update && \
    apt install ffmpeg -y && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

COPY . .

ENV PYTHONPATH=/opt/app

RUN mkdir -p /data/downloads /data/jsons && \
    echo '{}' > /data/jsons/api_keys.json && \
    echo '{}' > /data/jsons/tasks.json

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "src.server:app"]