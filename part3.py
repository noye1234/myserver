import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from math import factorial
import operator
from urllib.parse import urlparse, parse_qs

stack = []
history = []

OPERATIONS = {
    "plus": (2, operator.add),
    "minus": (2, operator.sub),
    "times": (2, operator.mul),
    "divide": (2, lambda x, y: x // y),
    "pow": (2, pow),
    "abs": (1, abs),
    "fact": (1, factorial)
}

def perform_operation(name, args):
    op_key = name.lower()
    if op_key not in OPERATIONS:
        return None, f"Error: unknown operation: {name}", 409
    expected_args, func = OPERATIONS[op_key]
    if len(args) < expected_args:
        return None, f"Error: Not enough arguments to perform the operation {name}", 409
    if len(args) > expected_args:
        return None, f"Error: Too many arguments to perform the operation {name}", 409
    if op_key == "divide" and args[1] == 0:
        return None, "Error while performing operation Divide: division by 0", 409
    if op_key == "fact" and args[0] < 0:
        return None, "Error while performing operation Factorial: not supported for the negative number", 409
    try:
        result = func(*args)
        return result, None, 200
    except Exception as e:
        return None, str(e), 409

class SimpleHandler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/calculator/health":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        elif path == "/calculator/stack/size":
            self._set_headers()
            self.wfile.write(json.dumps({"result": len(stack)}).encode())
        elif path == "/calculator/stack/operate":
            operation = query.get("operation", [None])[0]
            if not operation:
                self._set_headers(409)
                self.wfile.write(json.dumps({"errorMessage": "Error: unknown operation: None"}).encode())
                return
            op_key = operation.lower()
            if op_key not in OPERATIONS:
                self._set_headers(409)
                self.wfile.write(json.dumps({"errorMessage": f"Error: unknown operation: {operation}"}).encode())
                return
            arg_count = OPERATIONS[op_key][0]
            if len(stack) < arg_count:
                msg = f"Error: cannot implement operation {operation}. It requires {arg_count} arguments and the stack has only {len(stack)} arguments"
                self._set_headers(409)
                self.wfile.write(json.dumps({"errorMessage": msg}).encode())
                return
            args = [stack.pop() for _ in range(arg_count)]
            result, error, code = perform_operation(operation, args)
            if error:
                for v in reversed(args):
                    stack.append(v)
                self._set_headers(code)
                self.wfile.write(json.dumps({"errorMessage": error}).encode())
            else:
                history.append({"flavor": "STACK", "operation": operation, "arguments": args, "result": result})
                self._set_headers()
                self.wfile.write(json.dumps({"result": result}).encode())
        elif path == "/calculator/history":
            flavor = query.get("flavor", [None])[0]
            if flavor == "STACK":
                filtered = [h for h in history if h["flavor"] == "STACK"]
            elif flavor == "INDEPENDENT":
                filtered = [h for h in history if h["flavor"] == "INDEPENDENT"]
            else:
                stack_h = [h for h in history if h["flavor"] == "STACK"]
                ind_h = [h for h in history if h["flavor"] == "INDEPENDENT"]
                filtered = stack_h + ind_h
            self._set_headers()
            self.wfile.write(json.dumps({"result": filtered}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"errorMessage": "Not Found"}).encode())

    def do_POST(self):
        if self.path == "/calculator/independent/calculate":
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            data = json.loads(body)
            operation = data.get("operation")
            args = data.get("arguments", [])
            result, error, code = perform_operation(operation, args)
            self._set_headers(code)
            if error:
                self.wfile.write(json.dumps({"errorMessage": error}).encode())
            else:
                history.append({"flavor": "INDEPENDENT", "operation": operation, "arguments": args, "result": result})
                self.wfile.write(json.dumps({"result": result}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"errorMessage": "Not Found"}).encode())

    def do_PUT(self):
        if self.path == "/calculator/stack/arguments":
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            data = json.loads(body)
            args = data.get("arguments", [])
            stack.extend(args)
            self._set_headers()
            self.wfile.write(json.dumps({"result": len(stack)}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"errorMessage": "Not Found"}).encode())

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/calculator/stack/arguments":
            count = int(query.get("count", [0])[0])
            if count > len(stack):
                msg = f"Error: cannot remove {count} from the stack. It has only {len(stack)} arguments"
                self._set_headers(409)
                self.wfile.write(json.dumps({"errorMessage": msg}).encode())
                return
            for _ in range(count):
                stack.pop()
            self._set_headers()
            self.wfile.write(json.dumps({"result": len(stack)}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"errorMessage": "Not Found"}).encode())

def run(server_class=HTTPServer, handler_class=SimpleHandler, port=8496):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Serving on port {port}')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
