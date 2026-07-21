from http.server import ThreadingHTTPServer

from config import PORT
from db import init_database
from handlers import Handler


if __name__ == "__main__":
    init_database()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Prompt Admin is running on port {PORT}")
    server.serve_forever()
