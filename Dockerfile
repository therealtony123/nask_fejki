FROM python:3.13-slim

# tesseract-ocr + polski model językowy (pol.traineddata)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-pol \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Ścieżka tessdata z pakietów apt (tesseract-ocr-pol instaluje tu pol.traineddata).
# Ustawiona przed uruchomieniem aplikacji, żeby OCR pol+eng działał też poza compose.
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Modele twarzy (YuNet + SFace) z OpenCV Zoo do kfk/models/ — bez nich cecha
# "wizerunki osób" jest nieaktywna (kfk/faces.py: available()).
# Katalog nie jest wpisany w .dockerignore, więc RUN go utrwala w obrazie.
RUN bash scripts/download_models.sh

ENV STREAMLIT_SERVER_HEADLESS=true
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
