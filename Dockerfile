FROM python:3.15-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt
COPY manage.py ./
COPY maritime ./maritime
COPY portal ./portal
COPY templates ./templates
COPY static ./static
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput \
    && useradd --system --uid 10001 --no-create-home maritime
USER 10001
EXPOSE 8000
CMD ["python", "-m", "maritime.serve"]
