import socket
from typing import Any
from datetime import datetime

import rpc


class Client:
    def __init__(self, server_port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.server_port = server_port

    def start_client(self):
        self.sock.connect(("127.0.0.1", self.server_port))
        print(f"[{datetime.now()}] connection established")
        self.pipe = self.sock.makefile("rwb", True)

    def stop(self):
        self.pipe.close()
        self.sock.close()

    def _round_trip(self, operation_code: int, content: Any) -> Any:
        rpc.write_request(self.pipe, 1, operation_code, content)
        _, response = rpc.read_response(self.pipe)
        print(
            f"[{datetime.now()}] op: {rpc.operation_names[operation_code]}, res: {response}"
        )
        return response

    def create_completion(
        self, response: str, stage: str, error: str, task: int
    ) -> int:
        return self._round_trip(
            rpc.CREATE_COMPLETION_CODE, [response, stage, error, task]
        )

    def delete_completion(self, key: int) -> list | None:
        return self._round_trip(rpc.DELETE_COMPLETION_CODE, [key])

    def get_completions(self) -> list:
        return self._round_trip(rpc.GET_COMPLETIONS_CODE, [])

    def get_completion(self, key: int) -> list | None:
        return self._round_trip(rpc.GET_COMPLETION_CODE, [key])

    def create_task(
        self, parameter: str, session: int, description: str, done: int
    ) -> int:
        return self._round_trip(
            rpc.CREATE_TASK_CODE, [parameter, session, description, done]
        )

    def delete_task(self, key: int) -> list | None:
        return self._round_trip(rpc.DELETE_TASK_CODE, [key])

    def get_tasks(self) -> list:
        return self._round_trip(rpc.GET_TASKS_CODE, [])

    def get_task(self, key: int) -> list | None:
        return self._round_trip(rpc.GET_TASK_CODE, [key])

    def create_session(self, ip: str, locale: str, user_agent: str) -> int:
        return self._round_trip(rpc.CREATE_SESSION_CODE, [ip, locale, user_agent])

    def delete_session(self, key: int) -> list | None:
        return self._round_trip(rpc.DELETE_SESSION_CODE, [key])

    def get_sessions(self) -> list:
        return self._round_trip(rpc.GET_SESSIONS_CODE, [])

    def get_session(self, key: int) -> list | None:
        return self._round_trip(rpc.GET_SESSION_CODE, [key])

    def aggregate(self) -> list:
        return self._round_trip(rpc.AGGREGATE_CODE, [])


if __name__ == "__main__":
    c = Client(8080)
    c.start_client()

    c.get_completions()
    session_key = c.create_session("7.8.8.8", "ru", "conputer")
    session_key_for_removal = c.create_session("1.1.1.1", "en", "androd")
    c.get_sessions()
    c.delete_session(session_key_for_removal)
    c.get_sessions()

    task_key = c.create_task("param", session_key, "no desc", 55)
    task_key_for_removal = c.create_task("prara", session_key, "desc", 56)
    c.get_tasks()
    c.delete_task(task_key_for_removal)
    c.get_tasks()

    completion_key = c.create_completion(
        "response", "planning", "no error", task_key)
    completion_key_for_removal = c.create_completion(
        "response", "planning", "no error", task_key
    )
    c.get_completions()
    c.delete_completion(completion_key)
    c.get_completions()

    c.aggregate()

    c.stop()
