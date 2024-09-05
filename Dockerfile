FROM python:3.12.0-alpine

# Set the working directory
WORKDIR /app

# Copy the requirements.txt file from the project directory to the current working directory inside the Docker container
COPY requirements-dev.txt /app/requirements.txt

# Install psycopg2-binary
RUN apk add build-base libpq libpq-dev && apk add libffi-dev

RUN pip install uv

# Install all the dependencies listed in requirements.txt using the pip install
RUN uv pip install --no-cache-dir -r requirements.txt

RUN apk update \
    && apk upgrade \
    && apk add --no-cache libpq

# Copy the entire project directory to the current working directory inside the Docker container
COPY ./ /app

# Inform Docker that the application will listen on port 8000
EXPOSE 8000

# Default command to run when the Docker container is launched
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
