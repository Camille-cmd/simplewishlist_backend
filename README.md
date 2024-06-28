
# Simplewishlist

## Description

This is a Python project using Django-ninja.

## Setup and Installation

### Prerequisites

- Python 3.8 or higheru
- package manager uv : https://astral.sh/blog/uv

### Installation

1. Clone the repository:
    ```bash
    git clone git@github.com:Camille-cmd/simplewishlist_backend_v2.git
    ```

2. Navigate to the project directory:
    ```bash
    cd simplewishlist_backend_v2
    ```

3. Create a virtual environment using uv:
    ```bash
    uv venv
    ```

4. Activate the virtual environment:
    - On Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    - On Unix or MacOS:
        ```bash
        source .venv/bin/activate
        ```

5. Install the required dependencies:
    ```bash
    uv pip install -r requirements.txt
    ```

## Running the Application

1. Apply the migrations:
    ```bash
    python manage.py migrate
    ```

2. Run the server:
    ```bash
    python manage.py runserver
    ```

Now, you can navigate to `http://127.0.0.1:8000/` in your browser to see the application running.

## Testing

To run the tests, use the following command:
```bash
python manage.py test
```

## API Documentation

The API documentation is available at the following URL:
http://localhost:8000/api/docs

## Before you commit

Before you commit, make sure to run the following commands:
```bash
# Make sure coverage is higher than 80% and tests pass
coverage run ./manage.py test
# Make sure the code is formatted correctly
uv run ruff check
```

## License

This project is licensed under the MIT License - see the `LICENSE.md` file for details
