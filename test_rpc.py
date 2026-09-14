# test_client.py
import time
from collections import defaultdict
import threading

import hypothesis.strategies as st
from hypothesis import settings, note
from hypothesis.stateful import (
    RuleBasedStateMachine,
    rule,
    invariant,
    initialize,
    run_state_machine_as_test,
)

from client import Client
from server import Server


# ---------- вспомогательные сравнения ----------


def strip_time(record: list) -> list:
    """Убирает поле datetime (индекс 1) из записи, т.к. его нельзя предсказать."""
    return [record[0], *record[2:]]


def records_equal(a: list | None, b: list | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return strip_time(a) == strip_time(b)


def sessions_equal(a: list, b: list) -> bool:
    """Сравнение двух списков сессий/задач/завершений без учёта времени,
    но с учётом порядка ключей."""
    if len(a) != len(b):
        return False
    a_sorted = sorted(a, key=lambda r: r[0])
    b_sorted = sorted(b, key=lambda r: r[0])
    for x, y in zip(a_sorted, b_sorted):
        if strip_time(x) != strip_time(y):
            return False
    return True


# ---------- сама машина ----------


class ClientStateMachine(RuleBasedStateMachine):
    """
    Модель данных:
      sessions:    key -> [key, datetime, ip, locale, user_agent]
      tasks:       key -> [key, datetime, parameter, session, description, done]
      completions: key -> [key, datetime, response, stage, error, task]
    """

    def __init__(self):
        super().__init__()
        self.server_port = 8081

    @initialize()
    def setup(self):
        import model

        model.reset_state()

        self.server = Server(self.server_port)
        self.t = threading.Thread(target=self.server.start_server)
        self.t.start()

        self.client = Client(self.server_port)
        self.client.start_client()

        self.server_port += 1

        self.sessions: dict[int, list] = {}
        self.tasks: dict[int, list] = {}
        self.completions: dict[int, list] = {}

    def teardown(self):
        self.client.stop()
        self.server.stop()
        self.t.join()

    # ---------- sessions ----------

    @rule(
        ip=st.text(min_size=1, max_size=15),
        locale=st.text(min_size=0, max_size=8),
        user_agent=st.text(min_size=0, max_size=32),
    )
    def create_session(self, ip, locale, user_agent):
        key = self.client.create_session(ip, locale, user_agent)
        note(f"create_session -> {key}")
        assert key not in self.sessions
        now = int(time.time())
        self.sessions[key] = [key, now, ip, locale, user_agent]

    @rule(key=st.integers(min_value=0, max_value=2**31))
    def get_session_existing(self, key):
        # get по случайному ключу — просто проверяем, что не падает
        # и что ответ согласован с моделью
        expected = self.sessions.get(key)
        got = self.client.get_session(key)
        assert records_equal(expected, got), (expected, got)

    @rule(data=st.data())
    def get_session_from_model(self, data):
        if not self.sessions:
            return
        key = data.draw(st.sampled_from(list(self.sessions.keys())))
        got = self.client.get_session(key)
        assert records_equal(self.sessions[key], got)

    @rule()
    def get_sessions(self):
        got = self.client.get_sessions()
        assert sessions_equal(list(self.sessions.values()), got)

    @rule(data=st.data())
    def delete_session_existing(self, data):
        if not self.sessions:
            return
        key = data.draw(st.sampled_from(list(self.sessions.keys())))
        removed = self.sessions.pop(key)
        got = self.client.delete_session(key)

        # удаляем связанные tasks и completions, т.к. сервер их не каскадит,
        # но модель должна оставаться консистентной: на сервере они остались.
        # Поэтому мы НЕ удаляем их из модели tasks/completions,
        # а просто фиксируем, что session больше нет.
        assert records_equal(removed, got)

    @rule()
    def delete_session_nonexistent(self):
        # ключ, которого нет ни в модели, ни на сервере
        existing = set(self.sessions.keys())
        candidate = 0
        while candidate in existing:
            candidate += 1
        got = self.client.delete_session(candidate)
        assert got is None

    # ---------- tasks ----------

    @rule(
        data=st.data(),
        parameter=st.text(max_size=16),
        description=st.text(max_size=32),
        done=st.integers(),
    )
    def create_task(self, data, parameter, description, done):
        if not self.sessions:
            return
        session_key = data.draw(st.sampled_from(list(self.sessions.keys())))
        key = self.client.create_task(parameter, session_key, description, done)
        note(f"create_task -> {key} for session {session_key}")
        assert key not in self.tasks
        now = int(time.time())
        self.tasks[key] = [key, now, parameter, session_key, description, done]

    @rule(data=st.data())
    def get_task_from_model(self, data):
        if not self.tasks:
            return
        key = data.draw(st.sampled_from(list(self.tasks.keys())))
        got = self.client.get_task(key)
        assert records_equal(self.tasks[key], got)

    @rule(key=st.integers(min_value=0, max_value=2**31))
    def get_task_random(self, key):
        expected = self.tasks.get(key)
        got = self.client.get_task(key)
        assert records_equal(expected, got)

    @rule()
    def get_tasks(self):
        got = self.client.get_tasks()
        assert sessions_equal(list(self.tasks.values()), got)

    @rule(data=st.data())
    def delete_task_existing(self, data):
        if not self.tasks:
            return
        key = data.draw(st.sampled_from(list(self.tasks.keys())))
        removed = self.tasks.pop(key)
        got = self.client.delete_task(key)
        assert records_equal(removed, got)

    @rule()
    def delete_task_nonexistent(self):
        existing = set(self.tasks.keys())
        candidate = 0
        while candidate in existing:
            candidate += 1
        got = self.client.delete_task(candidate)
        assert got is None

    # ---------- completions ----------

    @rule(
        data=st.data(),
        response=st.text(max_size=32),
        stage=st.text(max_size=16),
        error=st.text(max_size=16),
    )
    def create_completion(self, data, response, stage, error):
        if not self.tasks:
            return
        task_key = data.draw(st.sampled_from(list(self.tasks.keys())))
        key = self.client.create_completion(response, stage, error, task_key)
        note(f"create_completion -> {key} for task {task_key}")
        assert key not in self.completions
        now = int(time.time())
        self.completions[key] = [key, now, response, stage, error, task_key]

    @rule(data=st.data())
    def get_completion_from_model(self, data):
        if not self.completions:
            return
        key = data.draw(st.sampled_from(list(self.completions.keys())))
        got = self.client.get_completion(key)
        assert records_equal(self.completions[key], got)

    @rule(key=st.integers(min_value=0, max_value=2**31))
    def get_completion_random(self, key):
        expected = self.completions.get(key)
        got = self.client.get_completion(key)
        assert records_equal(expected, got)

    @rule()
    def get_completions(self):
        got = self.client.get_completions()
        assert sessions_equal(list(self.completions.values()), got)

    @rule(data=st.data())
    def delete_completion_existing(self, data):
        if not self.completions:
            return
        key = data.draw(st.sampled_from(list(self.completions.keys())))
        removed = self.completions.pop(key)
        got = self.client.delete_completion(key)
        assert records_equal(removed, got)

    @rule()
    def delete_completion_nonexistent(self):
        existing = set(self.completions.keys())
        candidate = 0
        while candidate in existing:
            candidate += 1
        got = self.client.delete_completion(candidate)
        assert got is None

    # ---------- aggregate ----------

    @rule()
    def aggregate(self):
        """
        Ожидаемый результат:
          join = [[t, c] for t in tasks for c in completions if t[0] == c[5]]
          proj = [[c[2], t[4], t[2]] for t, c in join]
        Но сервер фильтрует completion'ы по времени (>= now - 7*60).
        Все наши записи созданы только что, поэтому попадают.
        Сортировка результата не гарантируется, поэтому сравниваем как мультимножества.
        """
        expected = []
        for t in self.tasks.values():
            for c in self.completions.values():
                if t[0] == c[5]:
                    expected.append([c[2], t[4], t[2]])

        got = self.client.aggregate()

        # сравниваем как мультимножества
        def key_fn(x):
            return tuple(x)

        assert sorted(map(key_fn, expected)) == sorted(map(key_fn, got)), (
            expected,
            got,
        )

    # ---------- инварианты ----------

    @invariant()
    def sessions_consistent(self):
        got = self.client.get_sessions()
        assert sessions_equal(list(self.sessions.values()), got)

    @invariant()
    def tasks_consistent(self):
        got = self.client.get_tasks()
        assert sessions_equal(list(self.tasks.values()), got)

    @invariant()
    def completions_consistent(self):
        got = self.client.get_completions()
        assert sessions_equal(list(self.completions.values()), got)


# ---------- запуск ----------


def test_client_stateful():
    run_state_machine_as_test(
        ClientStateMachine,
        settings=settings(
            max_examples=30,
            stateful_step_count=20,
            deadline=None,  # сетевые операции
        ),
    )
