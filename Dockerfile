# Ambiente isolato per i test deterministici di byte-swarmy.
# Nessun LLM: state/pause.flag blocca gli e2e live dentro il container.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt pyflakes pytest

COPY . .
RUN mkdir -p state && touch state/pause.flag

CMD ["python", "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"]
