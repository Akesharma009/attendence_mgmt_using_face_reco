FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-python-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir dlib-bin Click numpy Pillow \
    && pip install --no-cache-dir --no-deps face_recognition==1.3.0 \
    && pip install --no-cache-dir git+https://github.com/ageitgey/face_recognition_models \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p instance app/static/uploads/students app/static/uploads/unknown

ENV FLASK_DEBUG=0
EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --timeout 120 run:app
