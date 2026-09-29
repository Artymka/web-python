"""Общие фикстуры для тестов RPC-сервера."""

import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from src.client import Client
from src.server import Server


STARTUP_TIMEOUT = 5.0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _serve(server: Server) -> None:
    """Обёртка, чтобы закрытие сокета при остановке не пугало pytest."""
    try:
        server.start_server()
    except OSError:
        pass


def _wait_until_ready(port: int) -> None:
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.01)
    raise RuntimeError(f"server did not start on port {port}")


def _shutdown(server: Server, port: int, thread: threading.Thread) -> None:
    """Аккуратно гасим сервер, позволяя циклам завершиться по stop_event."""
    server._stop_event.set()
    try:
        probe = Client(port)
        probe.start_client()
        probe.get_sessions()
        probe.stop()
    except OSError:
        pass
    thread.join(timeout=STARTUP_TIMEOUT)
    server.stop()


@pytest.fixture(scope="session")
def rpc_port() -> int:
    """Поднимает один сервер на всю сессию и отдаёт его порт.

    Сервер выполняется в том же процессе, что и тесты, поэтому глобальные
    списки ``model`` общие. Между примерами hypothesis состояние сбрасывается
    вызовом ``model.reset_state()`` (см. test_mbt) — перезапуск не нужен.
    """
    port = _free_port()
    server = Server(port)
    thread = threading.Thread(target=_serve, args=(server,), daemon=True)
    thread.start()
    _wait_until_ready(port)

    os.environ["RPC_TEST_PORT"] = str(port)
    try:
        yield port
    finally:
        _shutdown(server, port, thread)
