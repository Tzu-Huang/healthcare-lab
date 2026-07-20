from backend.lab_operations import DockerSocketLabOperationAdapter


class FakeHttpResponse:
    """Minimal urllib response double with context-manager semantics."""

    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.body


class FakeDockerSocketLabOperationAdapter(DockerSocketLabOperationAdapter):
    """Deterministic Docker socket double that records requested paths."""

    def __init__(self):
        super().__init__()
        self.requested_paths = []

    def is_available(self) -> bool:
        return True

    def containers_for_service(self, service_name):
        return [{"Id": "container-1", "Names": [f"/{service_name}-1"]}]

    def request(self, method, path):
        self.requested_paths.append(path)
        return 204, b""


class FakeDbCursor:
    """Small DB-API cursor double for controlled external database checks."""

    def __init__(self, rows=None, execute_error=None):
        self.rows = rows or []
        self.execute_error = execute_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=()):
        if self.execute_error:
            raise self.execute_error

    def fetchall(self):
        return self.rows


class FakeDbConnection:
    """DB-API connection double with explicit closure state."""

    def __init__(self, rows=None, execute_error=None):
        self.rows = rows or []
        self.execute_error = execute_error
        self.closed = False

    def cursor(self):
        return FakeDbCursor(self.rows, self.execute_error)

    def close(self):
        self.closed = True
