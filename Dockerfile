FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN apt update && \
    apt install ffmpeg -y && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN pip install gunicorn

ENV PYTHONPATH=/app

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "src.server:app"]