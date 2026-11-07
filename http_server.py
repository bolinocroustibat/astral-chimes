import socket

from servos import SERVOS, strike

HTTP_PORT = 80
MAX_HTTP_TIMES = 5  # strikes allowed in one HTTP call


def parse_strike(request_line: str) -> tuple[str, int | None, int]:
    """Read a request line like "GET /strike?servo=1&times=2 HTTP/1.1".

    Return the HTTP status line, then the servo number and the number of
    strikes. The servo number is None when nothing should ring.
    """
    parts = request_line.split()
    if len(parts) < 2 or parts[0] != "GET":
        return "404 Not Found", None, 0
    path_and_query = parts[1].split("?", 1)
    if path_and_query[0] != "/strike":
        return "404 Not Found", None, 0
    params = {}
    if len(path_and_query) == 2:
        for pair in path_and_query[1].split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                params[key] = value
    try:
        servo = int(params["servo"])
        times = int(params.get("times", "1"))
    except (KeyError, ValueError):
        return "400 Bad Request", None, 0
    if servo not in SERVOS or not 1 <= times <= MAX_HTTP_TIMES:
        return "400 Bad Request", None, 0
    return "200 OK", servo, times


def start_http_server() -> socket.socket:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", HTTP_PORT))
    server.listen(2)
    server.setblocking(False)  # accept() returns at once when nobody is calling
    return server


def handle_http(server: socket.socket) -> None:
    """Answer one pending HTTP call, if any, then strike the requested servo."""
    try:
        client, _ = server.accept()
    except OSError:  # nobody is calling
        return
    servo, times = None, 0
    try:
        client.settimeout(2)
        request_line = client.readline().decode()
        # Read the headers too: closing with unread data would reset the connection.
        for _ in range(30):
            line = client.readline()
            if not line or line == b"\r\n":
                break
        status, servo, times = parse_strike(request_line)
        body = "ok" if servo else "usage: /strike?servo=N&times=K"
        client.send(f"HTTP/1.0 {status}\r\nContent-Type: text/plain\r\n\r\n{body}\n".encode())
    except Exception as e:
        print("http error:", e)
    finally:
        client.close()  # before striking, so the caller gets its answer at once
    if servo:
        print("http strike", servo, times)
        strike(SERVOS[servo], times)
