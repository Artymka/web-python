import json
import socket
from typing import BinaryIO, Tuple, Any


def write_request(f: BinaryIO, proto_version: int, operation_code: int, content: Any):
    res = bytearray()
    res.extend(proto_version.to_bytes(1))
    res.extend(operation_code.to_bytes(2))

    raw_content = json.dumps(content).encode()
    res.extend(len(raw_content).to_bytes(3))
    res.extend(raw_content)

    f.write(bytes(res))


def read_request(f: BinaryIO) -> Tuple[int, int, Any]:
    version = int.from_bytes(f.read(1))
    operation = int.from_bytes(f.read(2))
    content_size = int.from_bytes(f.read(3))

    if content_size == 0:
        return (version, operation, [])

    content = json.loads(f.read(content_size).decode())
    return (version, operation, content)


def write_response(f: BinaryIO, operation: int, content: Any):
    raw_content = json.dumps(content).encode()
    res = bytearray()

    res.extend(len(raw_content).to_bytes(4))
    res.extend(operation.to_bytes(2))
    res.extend(raw_content)

    f.write(bytes(res))


def read_response(f: BinaryIO) -> Tuple[int, Any]:
    content_size = int.from_bytes(f.read(4))
    operation = int.from_bytes(f.read(2))

    if content_size == 0:
        return (operation, [])

    raw_content = f.read(content_size)
    content = json.loads(raw_content)
    return (operation, content)


# operation codes
CREATE_COMPLETION_CODE = 0
DELETE_COMPLETION_CODE = 1
GET_COMPLETIONS_CODE = 2
GET_COMPLETION_CODE = 3
CREATE_TASK_CODE = 4
DELETE_TASK_CODE = 5
GET_TASKS_CODE = 6
GET_TASK_CODE = 7
CREATE_SESSION_CODE = 8
DELETE_SESSION_CODE = 9
GET_SESSIONS_CODE = 10
GET_SESSION_CODE = 11
AGGREGATE_CODE = 12

operation_names = {
    CREATE_COMPLETION_CODE: "CREATE_COMPLETION",
    DELETE_COMPLETION_CODE: "DELETE_COMPLETION",
    GET_COMPLETIONS_CODE: "GET_COMPLETIONS",
    GET_COMPLETION_CODE: "GET_COMPLETION",
    CREATE_TASK_CODE: "CREATE_TASK",
    DELETE_TASK_CODE: "DELETE_TASK",
    GET_TASKS_CODE: "GET_TASKS",
    GET_TASK_CODE: "GET_TASK",
    CREATE_SESSION_CODE: "CREATE_SESSION",
    DELETE_SESSION_CODE: "DELETE_SESSION",
    GET_SESSIONS_CODE: "GET_SESSIONS",
    GET_SESSION_CODE: "GET_SESSION",
    AGGREGATE_CODE: "AGGREGATE",
}
