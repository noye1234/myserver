import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from math import factorial
from urllib.parse import urlparse, parse_qs
import operator

# ---------- Calculator core ----------
stack = []
history = []
request_counter = 0  # 1‑based counter, incremented per request

OPERATIONS = {
    "plus": (2, operator.add),
    "minus": (2, operator.sub),
    "times": (2, operator.mul),
    "divide": (2, lambda x, y: x // y),
    "pow": (2, pow),
    "abs": (1, abs),
    "fact": (1, factorial),
}


def perform_operation(name, args):
    """Executes a calculator operation and returns (result, error‑msg, http‑code)."""
    op = name.lower()

    if op not in OPERATIONS:
        return None, f"Error: unknown operation: {name}", 409

    expected, func = OPERATIONS[op]

    if len(args) < expected:
        return None, f"Error: Not enough arguments to perform the operation {name}", 409
    if len(args) > expected:
        return None, f"Error: Too many arguments to perform the operation {name}", 409

    try:
        args = [int(arg) for arg in args]
    except ValueError:
        return None, "Error: Arguments must be numeric (integers)", 409

    if op == "divide" and args[1] == 0:
        return None, "Error while performing operation Divide: division by 0", 409
    if op == "fact" and args[0] < 0:
        return None, "Error while performing operation Factorial: not supported for the negative number", 409

    try:
        result = func(*args)
        return result, None, 200
    except Exception as exc:
        return None, f"Error while performing operation {name}: {str(exc)}", 409



# ---------- Logging setup (fixed!) ----------
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # ← כאן נמצא server.py
LOG_DIR  = os.path.join(BASE_DIR, "logs")              # logs ליד הקובץ
os.makedirs(LOG_DIR, exist_ok=True)

DATEFMT = "%Y-%m-%d %H:%M:%S"

def _build_logger(name: str,
                  filename: str,
                  level: int,
                  to_stdout: bool = False) -> logging.Logger:
    """
    יוצר Logger שׁכותב תמיד אל BASE_DIR/logs/<filename>,
    בלי קשר לאיפה מריצים את python.
    """
    logger = logging.getLogger(name)
    logger.handlers.clear()         # שלא יהיו כפילויות אם מרעננים קוד
    logger.setLevel(level)
    logger.propagate = False

    fmt = "%(asctime)s %(levelname)s: %(message)s | request #%(request_num)s"
    formatter = logging.Formatter(fmt, datefmt=DATEFMT)

    file_path   = os.path.join(LOG_DIR, filename)
    file_handler = logging.FileHandler(file_path, mode="a", encoding="utf-8", delay=False)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if to_stdout:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        logger.addHandler(console)

    # תן לשורה לוג תמיד request_num (גם אם extra לא הגיע)
    class _ReqFilter(logging.Filter):
        def filter(self, record):
            if not hasattr(record, "request_num"):
                record.request_num = 0
            return True

    logger.addFilter(_ReqFilter())

    # --- הדפס נתיב מלא פעם אחת לנוחות דיבאג ---
    if not getattr(logger, "_path_printed", False):
        print(f"[LOGGER] {name} → {file_path}")
        logger._path_printed = True

    return logger


REQUEST_LOGGER = _build_logger("request-logger", "requests.log", logging.INFO, to_stdout=True)
STACK_LOGGER = _build_logger("stack-logger", "stack.log", logging.INFO)
INDEPENDENT_LOGGER = _build_logger("independent-logger", "independent.log", logging.DEBUG)

ALL_LOGGERS = {
    "request-logger": REQUEST_LOGGER,
    "stack-logger": STACK_LOGGER,
    "independent-logger": INDEPENDENT_LOGGER,
}


# ---------- HTTP handler ----------
class SimpleHandler(BaseHTTPRequestHandler):
    def _set_json(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def _set_text(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def _handle_request(self, method_handler):
        global request_counter
        request_counter += 1
        self.request_num = request_counter
        start = time.perf_counter()

        REQUEST_LOGGER.info(
            f"Incoming request | #{self.request_num} | resource: {self.path} | HTTP Verb {self.command}",
            extra={"request_num": self.request_num},
        )

        try:
            method_handler()
        except Exception as exc:
            msg = f"Server encountered an unexpected error ! message: {str(exc)}"
            REQUEST_LOGGER.error(msg, extra={"request_num": self.request_num})
            self._set_json(500)
            self.wfile.write(json.dumps({"errorMessage": msg}).encode())
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            REQUEST_LOGGER.debug(
                f"request #{self.request_num} duration: {duration_ms}ms",
                extra={"request_num": self.request_num},
            )

    def do_GET(self):
        self._handle_request(self._do_GET_impl)

    def do_POST(self):
        self._handle_request(self._do_POST_impl)

    def do_PUT(self):
        self._handle_request(self._do_PUT_impl)

    def do_DELETE(self):
        self._handle_request(self._do_DELETE_impl)

    def _do_GET_impl(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/calculator/health":
            self._set_text(200)
            self.wfile.write(b"OK")
            return

        if path == "/calculator/stack/size":
            STACK_LOGGER.info(
                f"Stack size is {len(stack)}",
                extra={"request_num": self.request_num},
            )
            STACK_LOGGER.debug(
                f"Stack content (first == top): [{', '.join(map(str, reversed(stack)))}]",
                extra={"request_num": self.request_num},
            )
            self._set_json()
            self.wfile.write(json.dumps({"result": len(stack)}).encode())
            return

        if path == "/calculator/stack/operate":
            operation = qs.get("operation", [None])[0]
            if not operation or operation.lower() not in OPERATIONS:
                msg = f"Error: unknown operation: {operation}"
                self._fail_stack(msg)
                return

            arg_cnt = OPERATIONS[operation.lower()][0]
            if len(stack) < arg_cnt:
                msg = (f"Error: cannot implement operation {operation}. "
                       f"It requires {arg_cnt} arguments and the stack has only {len(stack)} arguments")
                self._fail_stack(msg)
                return

            args = [stack.pop() for _ in range(arg_cnt)]
            result, error, code = perform_operation(operation, args)
            if error:
                for v in reversed(args):
                    stack.append(v)
                self._fail_stack(error)
                return

            history.append({"flavor": "STACK", "operation": operation,
                            "arguments": args, "result": result})
            STACK_LOGGER.info(
                f"Performing operation {operation}. Result is {result} | stack size: {len(stack)}",
                extra={"request_num": self.request_num},
            )
            STACK_LOGGER.debug(
                f"Performing operation: {operation}({', '.join(map(str, args))}) = {result}",
                extra={"request_num": self.request_num},
            )
            self._set_json()
            self.wfile.write(json.dumps({"result": result}).encode())
            return

        if path == "/calculator/history":
            flavor = qs.get("flavor", [None])[0]
            if flavor == "STACK":
                filtered = [h for h in history if h["flavor"] == "STACK"]
            elif flavor == "INDEPENDENT":
                filtered = [h for h in history if h["flavor"] == "INDEPENDENT"]
            else:
                filtered = history

            if flavor == "STACK" or flavor is None:
                stack_actions = len([h for h in history if h["flavor"] == "STACK"])
                STACK_LOGGER.info(
                    f"History: So far total {stack_actions} stack actions",
                    extra={"request_num": self.request_num},
                )
            if flavor == "INDEPENDENT" or flavor is None:
                indep_actions = len([h for h in history if h["flavor"] == "INDEPENDENT"])
                INDEPENDENT_LOGGER.info(
                    f"History: So far total {indep_actions} independent actions",
                    extra={"request_num": self.request_num},
                )

            self._set_json()
            self.wfile.write(json.dumps({"result": filtered}).encode())
            return

        if path == "/logs/level":
            logger_name = qs.get("logger-name", [None])[0]
            logger = ALL_LOGGERS.get(logger_name)
            if not logger:
                self._set_text(404)
                self.wfile.write(f"Logger '{logger_name}' not found".encode())
                return
            level_name = logging.getLevelName(logger.level)
            self._set_text(200)
            self.wfile.write(level_name.encode())
            return

        self._set_json(404)
        self.wfile.write(json.dumps({"errorMessage": "Not Found"}).encode())

    def _do_POST_impl(self):
        if self.path != "/calculator/independent/calculate":
            self._set_json(404)
            self.wfile.write(json.dumps({"errorMessage": "Not Found"}).encode())
            return

        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length))
        operation = data.get("operation")
        args = data.get("arguments", [])

        result, error, code = perform_operation(operation, args)
        if error:
            self._fail_independent(error, code)
            return

        history.append({"flavor": "INDEPENDENT", "operation": operation,
                        "arguments": args, "result": result})
        INDEPENDENT_LOGGER.info(
            f"Performing operation {operation}. Result is {result}",
            extra={"request_num": self.request_num},
        )
        INDEPENDENT_LOGGER.debug(
            f"Performing operation: {operation}({', '.join(map(str, args))}) = {result}",
            extra={"request_num": self.request_num},
        )
        self._set_json()
        self.wfile.write(json.dumps({"result": result}).encode())

    def _do_PUT_impl(self):
        if self.path == "/calculator/stack/arguments":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            args = data.get("arguments", [])

            size_before = len(stack)
            stack.extend(args)
            STACK_LOGGER.info(
                f"Adding total of {len(args)} argument(s) to the stack | Stack size: {len(stack)}",
                extra={"request_num": self.request_num},
            )
            STACK_LOGGER.debug(
                f"Adding arguments: {', '.join(map(str, args))} | Stack size before {size_before} | stack size after {len(stack)}",
                extra={"request_num": self.request_num},
            )
            self._set_json()
            self.wfile.write(json.dumps({"result": len(stack)}).encode())
            return

        if self.path.startswith("/logs/level"):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            logger_name = qs.get("logger-name", [None])[0]
            logger_level = qs.get("logger-level", [None])[0]

            logger = ALL_LOGGERS.get(logger_name)
            if logger is None:
                self._set_text(404)
                self.wfile.write(f"Logger '{logger_name}' not found".encode())
                return
            if logger_level not in {"ERROR", "INFO", "DEBUG"}:
                self._set_text(400)
                self.wfile.write("Invalid logger level".encode())
                return

            logger.setLevel(getattr(logging, logger_level))
            self._set_text(200)
            self.wfile.write(logger_level.encode())
            return

        self._set_json(404)
        self.wfile.write(json.dumps({"errorMessage": "Not Found"}).encode())

    def _do_DELETE_impl(self):
        parsed = urlparse(self.path)
        if parsed.path != "/calculator/stack/arguments":
            self._set_json(404)
            self.wfile.write(json.dumps({"errorMessage": "Not Found"}).encode())
            return

        qs = parse_qs(parsed.query)
        count = int(qs.get("count", ["0"])[0])
        if count > len(stack):
            msg = f"Error: cannot remove {count} from the stack. It has only {len(stack)} arguments"
            self._fail_stack(msg)
            return

        for _ in range(count):
            stack.pop()
        STACK_LOGGER.info(
            f"Removing total {count} argument(s) from the stack | Stack size: {len(stack)}",
            extra={"request_num": self.request_num},
        )
        self._set_json()
        self.wfile.write(json.dumps({"result": len(stack)}).encode())

    def _fail_stack(self, msg, code=409):
        STACK_LOGGER.error(
            f"Server encountered an error ! message: {msg}",
            extra={"request_num": self.request_num},
        )
        self._set_json(code)
        self.wfile.write(json.dumps({"errorMessage": msg}).encode())

    def _fail_independent(self, msg, code=409):
        INDEPENDENT_LOGGER.error(
            f"Server encountered an error ! message: {msg}",
            extra={"request_num": self.request_num},
        )
        self._set_json(code)
        self.wfile.write(json.dumps({"errorMessage": msg}).encode())


# ---------- bootstrap ----------
def run(port=8496):
    server = HTTPServer(("", port), SimpleHandler)
    print(f"Serving on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    run()


