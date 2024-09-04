#!/bin/bash

# Collect static files
echo "Collect static files"
python manage.py collectstatic --noinput

# Apply database migrations
echo "Apply database migrations"
python manage.py migrate

# Start server
echo "Starting server $DJANGO_ENV"
if [ "$DJANGO_ENV" = "production" ]; then
  echo "Running Gunicorn"
  exec gunicorn simplewishlist.asgi:application --bind 0.0.0.0:8000 --workers 4 -k uvicorn.workers.UvicornWorker
else
  echo "Running development server"
  python manage.py runserver 0.0.0.0:8000
fi
