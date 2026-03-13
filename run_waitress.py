import os

from waitress import serve

from wsgi import application


if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8080"))
    threads = int(os.environ.get("APP_THREADS", "8"))
    serve(application, host=host, port=port, threads=threads)
