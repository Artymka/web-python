import socket
import threading
from typing import Callable, Dict
from datetime import datetime

import model
import rpc


operation_funcs = {
    rpc.CREATE_COMPLETION_CODE: model.create_completion,
    rpc.DELETE_COMPLETION_CODE: model.delete_completion,
    rpc.GET_COMPLETIONS_CODE: model.get_completions,
    rpc.GET_COMPLETION_CODE: model.get_completion,
    rpc.CREATE_TASK_CODE: model.create_task,
    rpc.DELETE_TASK_CODE: model.delete_task,
    rpc.GET_TASKS_CODE: model.get_tasks,
    rpc.GET_TASK_CODE: model.get_task,
    rpc.CREATE_SESSION_CODE: model.create_session,
    rpc.DELETE_SESSION_CODE: model.delete_session,
    rpc.GET_SESSIONS_CODE: model.get_sessions,
    rpc.GET_SESSION_CODE: model.get_session,
    rpc.AGGREGATE_CODE: model.aggregate,
}


def gen_validate_func(types: list) -> Callable[[list], bool]:
    def validate_func(params: list) -> bool:
        if len(types) != len(params):
            return False
        for t, p in zip(types, params):
            if not isinstance(p, t):
                return False
        return True

    return validate_func


validation_funcs: Dict[int, Callable] = {
    rpc.CREATE_COMPLETION_CODE: gen_validate_func([str, str, str, int]),
    rpc.DELETE_COMPLETION_CODE: gen_validate_func([int]),
    rpc.GET_COMPLETIONS_CODE: gen_validate_func([]),
    rpc.GET_COMPLETION_CODE: gen_validate_func([int]),
    rpc.CREATE_TASK_CODE: gen_validate_func([str, int, str, int]),
    rpc.DELETE_TASK_CODE: gen_validate_func([int]),
    rpc.GET_TASKS_CODE: gen_validate_func([]),
    rpc.GET_TASK_CODE: gen_validate_func([int]),
    rpc.CREATE_SESSION_CODE: gen_validate_func([str, str, str]),
    rpc.DELETE_SESSION_CODE: gen_validate_func([int]),
    rpc.GET_SESSIONS_CODE: gen_validate_func([]),
    rpc.GET_SESSION_CODE: gen_validate_func([int]),
    rpc.AGGREGATE_CODE: gen_validate_func([]),
}


class Server:
    def __init__(self, port: int):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.port = port

    def start_server(self):
        self.server_sock.bind(("127.0.0.1", self.port))
        self.server_sock.listen(5)

        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

        print(f"[{datetime.now()}] start serving...")
        while not self._stop_event.is_set():
            client_sock, address = self.server_sock.accept()
            print(f"[{datetime.now()}] have a new client: {address}")

            t = threading.Thread(
                target=self._serve_client, args=(client_sock, address[1])
            )
            t.daemon = True
            self._threads.append(t)
            t.start()

    def stop(self):
        self._stop_event.set()
        try:
            self.server_sock.close()  # wakes accept()
        except OSError:
            pass
        for t in self._threads:
            t.join(timeout=2)

    def _serve_client(self, client_sock: socket.socket, id: int):
        try:
            with client_sock.makefile("rwb", True) as pipe:
                while not self._stop_event.is_set():
                    try:
                        _, operation_code, content = rpc.read_request(pipe)
                        print(
                            f"[{datetime.now()}] ({id}) op: {rpc.operation_names[operation_code]}, content: {content}"
                        )

                        if operation_code not in operation_funcs:
                            rpc.write_response(
                                pipe, operation_code, "invalid operation"
                            )
                            continue

                        if not isinstance(content, list):
                            rpc.write_response(
                                pipe, operation_code, "wrong content type"
                            )
                            continue

                        if not validation_funcs[operation_code](content):
                            rpc.write_response(
                                pipe, operation_code, "wrong params types"
                            )
                            continue

                        res = operation_funcs[operation_code](*content)
                        rpc.write_response(pipe, operation_code, res)
                    except (ConnectionError, OSError):
                        print(f"[{datetime.now()}] client disconnected: {id}")
                        break
        finally:
            client_sock.close()


if __name__ == "__main__":
    s = Server(8080)
    s.start_server()
