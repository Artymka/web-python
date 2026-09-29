"""Model-Based Testing (MBT) для RPC-сервера на hypothesis.

Идея: рядом с реальной системой (сервер + ``model``) живёт упрощённая
Python-модель состояния (обычные словари). Правила, сгенерированные
hypothesis, одновременно дёргают и систему, и модель, а инварианты
сравнивают их после каждого шага.

Покрываются все 13 операций RPC:
    CREATE/DELETE/GET(S)_COMPLETION, CREATE/DELETE/GET(S)_TASK,
    CREATE/DELETE/GET(S)_SESSION и AGGREGATE.
"""

import os
import time
from io import BytesIO
from unittest.mock import patch

import hypothesis.strategies as st
import rpc
from client import Client
from hypothesis import HealthCheck, assume, given, settings
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)

import model as server_model

RECENT_WINDOW = 7 * 60
KEY_STRATEGY = st.integers(min_value=0, max_value=1 << 31)
ORPHAN_TASK = -1


def _strip(record: list) -> list:
    """Убирает непредсказуемое поле datetime (индекс 1) из записи."""
    return [record[0], *record[2:]]


def _records_match(expected: list | None, actual: list | None) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    return _strip(expected) == _strip(actual)


def _lists_match(expected: list, actual: list) -> bool:
    if len(expected) != len(actual):
        return False
    exp = sorted((_strip(r) for r in expected), key=repr)
    got = sorted((_strip(r) for r in actual), key=repr)
    return exp == got


def _multiset(rows: list) -> list:
    return sorted((tuple(r) for r in rows), key=repr)


class RpcStateMachine(RuleBasedStateMachine):
    """Сравнивает реальный RPC-сервер с простой моделью в памяти."""

    def __init__(self) -> None:
        super().__init__()

        server_model.reset_state()

        self.client = Client(int(os.environ["RPC_TEST_PORT"]))
        self.client.start_client()

        self.sessions: dict[int, list] = {}
        self.tasks: dict[int, list] = {}
        self.completions: dict[int, list] = {}

    @initialize()
    def seed(self) -> None:
        """Создаём базовые записи, чтобы заведомо покрыть все ветви join'а.

        hypothesis в режиме swarm может отключать часть правил в каждом
        примере, поэтому гарантируем наличие связанных/несвязанных записей
        прямо на старте:
          * задача с completion'ом  -> matched-ветка ``_merge``;
          * задача без completion'а -> ветка ``_append_unmatched``;
          * completion без задачи   -> ветка ``task is None``.
        """
        session = self._add_session("127.0.0.1", "ru", "seed")
        task = self._add_task("seed-param", session, "seed-desc", 0)
        self._add_completion("seed-resp", "seed-stage", "seed-err", task)

        self._add_task("unused-param", session, "unused-desc", 1)

        self._add_completion(
            "orphan-resp", "orphan-stage", "orphan-err", ORPHAN_TASK
        )

    def teardown(self) -> None:
        self.client.stop()

    def _add_session(self, ip, locale, user_agent) -> int:
        key = self.client.create_session(ip, locale, user_agent)
        assert key not in self.sessions
        self.sessions[key] = [key, int(time.time()), ip, locale, user_agent]
        return key

    def _add_task(self, parameter, session, description, done) -> int:
        key = self.client.create_task(parameter, session, description, done)
        assert key not in self.tasks
        self.tasks[key] = [
            key,
            int(time.time()),
            parameter,
            session,
            description,
            done,
        ]
        return key

    def _add_completion(self, response, stage, error, task) -> int:
        key = self.client.create_completion(response, stage, error, task)
        assert key not in self.completions
        self.completions[key] = [
            key,
            int(time.time()),
            response,
            stage,
            error,
            task,
        ]
        return key

    @rule(
        ip=st.text(min_size=1, max_size=15),
        locale=st.text(max_size=8),
        user_agent=st.text(max_size=32),
    )
    def create_session(self, ip, locale, user_agent) -> None:
        self._add_session(ip, locale, user_agent)

    @rule()
    def get_sessions(self) -> None:
        got = self.client.get_sessions()
        assert _lists_match(list(self.sessions.values()), got)

    @precondition(lambda self: bool(self.sessions))
    @rule(data=st.data())
    def get_session(self, data) -> None:
        key = data.draw(st.sampled_from(list(self.sessions)))
        assert _records_match(self.sessions[key], self.client.get_session(key))

    @rule(key=KEY_STRATEGY)
    def get_session_unknown(self, key) -> None:
        if key in self.sessions:
            return
        assert self.client.get_session(key) is None

    @precondition(lambda self: bool(self.sessions))
    @rule(data=st.data())
    def delete_session(self, data) -> None:
        key = data.draw(st.sampled_from(list(self.sessions)))
        expected = self.sessions.pop(key)
        assert _records_match(expected, self.client.delete_session(key))

    @rule(key=KEY_STRATEGY)
    def delete_session_unknown(self, key) -> None:
        if key in self.sessions:
            return
        assert self.client.delete_session(key) is None

    @precondition(lambda self: bool(self.sessions))
    @rule(
        data=st.data(),
        parameter=st.text(max_size=16),
        description=st.text(max_size=32),
        done=st.integers(),
    )
    def create_task(self, data, parameter, description, done) -> None:
        session = data.draw(st.sampled_from(list(self.sessions)))
        self._add_task(parameter, session, description, done)

    @rule()
    def get_tasks(self) -> None:
        got = self.client.get_tasks()
        assert _lists_match(list(self.tasks.values()), got)

    @precondition(lambda self: bool(self.tasks))
    @rule(data=st.data())
    def get_task(self, data) -> None:
        key = data.draw(st.sampled_from(list(self.tasks)))
        assert _records_match(self.tasks[key], self.client.get_task(key))

    @rule(key=KEY_STRATEGY)
    def get_task_unknown(self, key) -> None:
        if key in self.tasks:
            return
        assert self.client.get_task(key) is None

    @precondition(lambda self: bool(self.tasks))
    @rule(data=st.data())
    def delete_task(self, data) -> None:
        key = data.draw(st.sampled_from(list(self.tasks)))
        expected = self.tasks.pop(key)
        assert _records_match(expected, self.client.delete_task(key))

    @rule(key=KEY_STRATEGY)
    def delete_task_unknown(self, key) -> None:
        if key in self.tasks:
            return
        assert self.client.delete_task(key) is None

    @precondition(lambda self: bool(self.tasks))
    @rule(
        data=st.data(),
        response=st.text(max_size=32),
        stage=st.text(max_size=16),
        error=st.text(max_size=16),
    )
    def create_completion(self, data, response, stage, error) -> None:
        task = data.draw(st.sampled_from(list(self.tasks)))
        self._add_completion(response, stage, error, task)

    @rule(
        response=st.text(max_size=32),
        stage=st.text(max_size=16),
        error=st.text(max_size=16),
        task=KEY_STRATEGY,
    )
    def create_completion_orphan(self, response, stage, error, task) -> None:
        """Completion на несуществующую задачу (ветка task is None)."""
        if task in self.tasks:
            return
        self._add_completion(response, stage, error, task)

    @rule()
    def get_completions(self) -> None:
        got = self.client.get_completions()
        assert _lists_match(list(self.completions.values()), got)

    @precondition(lambda self: bool(self.completions))
    @rule(data=st.data())
    def get_completion(self, data) -> None:
        key = data.draw(st.sampled_from(list(self.completions)))
        assert _records_match(
            self.completions[key], self.client.get_completion(key)
        )

    @rule(key=KEY_STRATEGY)
    def get_completion_unknown(self, key) -> None:
        if key in self.completions:
            return
        assert self.client.get_completion(key) is None

    @precondition(lambda self: bool(self.completions))
    @rule(data=st.data())
    def delete_completion(self, data) -> None:
        key = data.draw(st.sampled_from(list(self.completions)))
        expected = self.completions.pop(key)
        assert _records_match(expected, self.client.delete_completion(key))

    @rule(key=KEY_STRATEGY)
    def delete_completion_unknown(self, key) -> None:
        if key in self.completions:
            return
        assert self.client.delete_completion(key) is None

    def _expected_aggregate(self) -> list:
        threshold = int(time.time()) - RECENT_WINDOW
        recent = [c for c in self.completions.values() if c[1] >= threshold]

        join: list = []
        used_task_ids = set()
        for completion in recent:
            task = self.tasks.get(completion[5])
            if task is None:
                join.append([completion[2], None, None])
                continue
            join.append([completion[2], task[4], task[2]])
            used_task_ids.add(task[0])

        for task in self.tasks.values():
            if task[0] not in used_task_ids:
                join.append([None, task[4], task[2]])
        return join

    @rule()
    def aggregate(self) -> None:
        got = self.client.aggregate()
        assert _multiset(self._expected_aggregate()) == _multiset(got)

    def _raw_call(self, operation_code: int, content) -> object:
        rpc.write_request(self.client.pipe, 1, operation_code, content)
        _, response = rpc.read_response(self.client.pipe)
        return response

    @rule(
        content=st.one_of(
            st.integers(),
            st.text(),
            st.none(),
            st.dictionaries(st.text(), st.integers()),
        )
    )
    def request_wrong_content_type(self, content) -> None:
        response = self._raw_call(rpc.GET_SESSIONS_CODE, content)
        assert response == "wrong content type"

    @rule()
    def request_wrong_params_types(self) -> None:
        response = self._raw_call(rpc.CREATE_SESSION_CODE, [1, 2, 3])
        assert response == "wrong params types"

    @rule()
    def request_wrong_params_count(self) -> None:
        response = self._raw_call(rpc.CREATE_SESSION_CODE, ["a", "b"])
        assert response == "wrong params types"

    @invariant()
    def sessions_consistent(self) -> None:
        got = self.client.get_sessions()
        assert _lists_match(list(self.sessions.values()), got)

    @invariant()
    def tasks_consistent(self) -> None:
        got = self.client.get_tasks()
        assert _lists_match(list(self.tasks.values()), got)

    @invariant()
    def completions_consistent(self) -> None:
        got = self.client.get_completions()
        assert _lists_match(list(self.completions.values()), got)

    @invariant()
    def aggregate_consistent(self) -> None:
        got = self.client.aggregate()
        assert _multiset(self._expected_aggregate()) == _multiset(got)


TEST_SETTINGS = settings(
    max_examples=50,
    stateful_step_count=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def test_rpc_model_based(rpc_port) -> None:
    assert rpc_port > 0
    run_state_machine_as_test(RpcStateMachine, settings=TEST_SETTINGS)


@given(
    version=st.integers(min_value=0, max_value=255),
    operation=st.integers(min_value=0, max_value=2**16 - 1),
    content=st.lists(st.integers()),
)
def test_request_roundtrip(version, operation, content) -> None:
    buffer = BytesIO()
    rpc.write_request(buffer, version, operation, content)
    buffer.seek(0)
    assert rpc.read_request(buffer) == (version, operation, content)


@given(
    operation=st.integers(min_value=0, max_value=2**16 - 1),
    content=st.lists(st.integers()),
)
def test_response_roundtrip(operation, content) -> None:
    buffer = BytesIO()
    rpc.write_response(buffer, operation, content)
    buffer.seek(0)
    assert rpc.read_response(buffer) == (operation, content)


@given(operation=st.integers(min_value=0, max_value=2**16 - 1))
def test_read_response_empty_payload(operation) -> None:

    buffer = BytesIO(b"\x00\x00\x00\x00" + operation.to_bytes(2, "big"))
    assert rpc.read_response(buffer) == (operation, [])


@given(
    existing=st.integers(min_value=0, max_value=1 << 31),
    fresh=st.integers(min_value=0, max_value=1 << 31),
)
def test_base_create_avoids_key_collision(existing, fresh) -> None:
    assume(existing != fresh)
    source = [[existing, 0]]
    with patch.object(
        server_model.random, "randint", side_effect=[existing, fresh]
    ):
        key = server_model.base_create(source)
    assert key == fresh
    assert [row[0] for row in source] == [existing, fresh]
