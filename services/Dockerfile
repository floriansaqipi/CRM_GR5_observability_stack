FROM python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home appuser
ARG SERVICE
COPY shared ./shared
COPY ${SERVICE} ./
COPY tests ./tests
COPY gunicorn_conf.py .
USER appuser
EXPOSE 5000
CMD ["gunicorn", "--config", "gunicorn_conf.py", "app:app"]
