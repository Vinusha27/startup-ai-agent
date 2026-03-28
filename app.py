"""Root application entrypoint for local development and GitHub usage."""

from backend.app import app


if __name__ == "__main__":
    app.run(debug=True)
