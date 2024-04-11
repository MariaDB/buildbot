# Use an official Python runtime as a parent image
FROM python:3.12.3-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apk update \
    && apk add --no-cache \
        gcc \
        libc-dev \
        mariadb-dev \
    && rm -rf /var/cache/apk/*

# Install python dependencies
COPY requirements.txt /app
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY ./crossreference /app/

# Add and run as non-root user
RUN adduser --disabled-password --gecos '' cr
USER cr

# Run gunicorn
CMD ["bash", "-c", "python manage.py collectstatic --noinput && exec gunicorn crossreference.wsgi:application --bind 0.0.0.0:25432"]