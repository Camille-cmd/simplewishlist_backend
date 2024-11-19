# Simplewislist Backend

This is the backend of the Simplewishlist project. It is a Django application that provides an API to manage wishlists.

The full instructions to run the application with the frontend can be found [on the docker compose repository](https://github.com/Camille-cmd/simplewishlist-docker-compose).

## Requirements
- Python 3.10 or higher
- package manager uv : https://astral.sh/blog/uv

## Installation
See the installations instructions for both frontend and backend in the root directory README.md file.

### Docker
1. Clone this repository
2. Clone the frontend repository to the root directory:
3. Create the environment file for the backend by copying the `.env.example` file and renaming it to `.env`, available [here](https://github.com/Camille-cmd/simplewishlist-docker-compose).
4. Run the following command to start the application:
    ```bash
    docker build -t simplewishlist_backend .
    docker run simplewishlist_backend
    ```

### Manual Installation

1. Clone the repository

2. Navigate to the project directory:
    ```bash
    cd simplewishlist_backend
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
    uv pip install -r requirements-dev.txt
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

3. Navigate to `http://localhost:8000/admin` in your browser to see the application running.

## API Documentation

You can access the API documentation at the following URL: `http://localhost:8000/api/docs`

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the `LICENSE.md` file for details
