FROM python:3.12-slim

WORKDIR /srv/control
COPY . /srv/control

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

CMD ["python", "main.py", "--addr", "0.0.0.0:8080", "--data", "/srv/control/var"]

