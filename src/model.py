import random
import time
import threading
from typing import Dict, List, Callable

completions = []
completions_lock = threading.Lock()
tasks = []
tasks_lock = threading.Lock()
sessions = []
sessions_lock = threading.Lock()


"""Common functions"""


def use_lock(lock: threading.Lock):
    def decorator(f):
        def wrapper(*args, **kwargs):
            lock.acquire()
            res = 0
            try:
                res = f(*args, **kwargs)
            finally:
                lock.release()
            return res

        return wrapper

    return decorator


def base_create(source: list, *args) -> int:
    key = random.randint(0, 1 << 31)

    while True:
        has_key = False
        for line in source:
            cur_key = line[0]
            if cur_key == key:
                has_key = True
                break
        if has_key:
            key = random.randint(0, 1 << 31)
        else:
            break

    datetime = int(time.time())

    source.append([key, datetime, *args])
    return key


def base_delete(source: list, key: int) -> list | None:
    for i in range(len(source)):
        if source[i][0] == key:
            return source.pop(i)


def base_get(source: list, key: int) -> list | None:
    for item in source:
        if item[0] == key:
            return item


def reset_state():
    with sessions_lock:
        sessions.clear()
    with tasks_lock:
        tasks.clear()
    with completions_lock:
        completions.clear()


"""particular functions"""


@use_lock(completions_lock)
def create_completion(response: str, stage: str, error: str, task: int) -> int:
    return base_create(completions, response, stage, error, task)


@use_lock(completions_lock)
def delete_completion(key: int) -> list | None:
    return base_delete(completions, key)


@use_lock(completions_lock)
def get_completions() -> list:
    return completions


@use_lock(completions_lock)
def get_completion(key: int) -> list | None:
    return base_get(completions, key)


@use_lock(tasks_lock)
def create_task(
    parameter: str, session: int, description: str, done: int
) -> int:
    return base_create(tasks, parameter, session, description, done)


@use_lock(tasks_lock)
def delete_task(key: int) -> list | None:
    return base_delete(tasks, key)


@use_lock(tasks_lock)
def get_tasks() -> list:
    return tasks


@use_lock(tasks_lock)
def get_task(key: int) -> list | None:
    return base_get(tasks, key)


@use_lock(sessions_lock)
def create_session(ip: str, locale: str, user_agent: str) -> int:
    return base_create(sessions, ip, locale, user_agent)


@use_lock(sessions_lock)
def delete_session(key: int) -> list | None:
    return base_delete(sessions, key)


@use_lock(sessions_lock)
def get_sessions() -> list:
    return sessions


@use_lock(sessions_lock)
def get_session(key: int) -> list | None:
    return base_get(sessions, key)


def _filter_recent(completions: list, seconds: int = 7 * 60) -> list:
    """Оставляем completion'ы за последние `seconds` секунд."""
    threshold = int(time.time()) - seconds
    return [c for c in completions if c[1] >= threshold]


def _tasks_by_id(tasks: list) -> dict:
    """Индексируем задачи по id для O(1) доступа."""
    return {t[0]: t for t in tasks}


def _merge(completions: list, tasks_index: dict) -> tuple[list, set]:
    """LEFT JOIN: completion -> task."""
    join = []
    used_task_ids = set()
    for c in completions:
        task = tasks_index.get(c[5])
        if task is None:
            join.append([c[2], None, None])
            continue
        join.append([c[2], task[4], task[2]])
        used_task_ids.add(task[0])
    return join, used_task_ids


def _append_unmatched(join: list, tasks: list, used_task_ids: set) -> list:
    """RIGHT JOIN: задачи, которых не было среди completion'ов."""
    for t in tasks:
        if t[0] not in used_task_ids:
            join.append([None, t[4], t[2]])
    return join


@use_lock(completions_lock)
@use_lock(tasks_lock)
def aggregate() -> list:
    recent = _filter_recent(completions)
    tasks_index = _tasks_by_id(tasks)
    join, used_ids = _merge(recent, tasks_index)
    return _append_unmatched(join, tasks, used_ids)


"""repl"""


def repl_validation(
    params: List[str], types: List[type]
) -> Callable[[], List]:
    def validate() -> List:
        res = []
        for param, param_type in zip(params, types):
            while True:
                print(f"{param} ({param_type}): ", end="")
                try:
                    temp = param_type(input())
                    res.append(temp)
                    break
                except ValueError:
                    pass
        return res

    return validate


CREATE_COMPLETION_REPL = 0
DELETE_COMPLETION_REPL = 1
GET_COMPLETIONS_REPL = 2
GET_COMPLETION_REPL = 3
CREATE_TASK_REPL = 4
DELETE_TASK_REPL = 5
GET_TASKS_REPL = 6
GET_TASK_REPL = 7
CREATE_SESSION_REPL = 8
DELETE_SESSION_REPL = 9
GET_SESSIONS_REPL = 10
GET_SESSION_REPL = 11
AGGREGATE_REPL = 12

validation_funcs: Dict[int, Callable] = {
    CREATE_COMPLETION_REPL: repl_validation(
        ["response", "stage", "error", "task"], [str, str, str, int]
    ),
    DELETE_COMPLETION_REPL: repl_validation(["key"], [int]),
    GET_COMPLETIONS_REPL: repl_validation([], []),
    GET_COMPLETION_REPL: repl_validation(["key"], [int]),
    CREATE_TASK_REPL: repl_validation(
        ["parameter", "session", "description", "done"], [str, int, str, int]
    ),
    DELETE_TASK_REPL: repl_validation(["key"], [int]),
    GET_TASKS_REPL: repl_validation([], []),
    GET_TASK_REPL: repl_validation(["key"], [int]),
    CREATE_SESSION_REPL: repl_validation(
        ["ip", "locale", "user_agent"], [str, str, str]
    ),
    DELETE_SESSION_REPL: repl_validation(["key"], [int]),
    GET_SESSIONS_REPL: repl_validation([], []),
    GET_SESSION_REPL: repl_validation(["key"], [int]),
    AGGREGATE_REPL: repl_validation([], []),
}

operation_funcs = {
    CREATE_COMPLETION_REPL: create_completion,
    DELETE_COMPLETION_REPL: delete_completion,
    GET_COMPLETIONS_REPL: get_completions,
    GET_COMPLETION_REPL: get_completion,
    CREATE_TASK_REPL: create_task,
    DELETE_TASK_REPL: delete_task,
    GET_TASKS_REPL: get_tasks,
    GET_TASK_REPL: get_task,
    CREATE_SESSION_REPL: create_session,
    DELETE_SESSION_REPL: delete_session,
    GET_SESSIONS_REPL: get_sessions,
    GET_SESSION_REPL: get_session,
    AGGREGATE_REPL: aggregate,
}


def repl():
    print(
        """
Firstly type number of operation, then type arguments:
0 CREATE_COMPLETION
1 DELETE_COMPLETION
2 GET_COMPLETIONS
3 GET_COMPLETION
4 CREATE_TASK
5 DELETE_TASK
6 GET_TASKS
7 GET_TASK
8 CREATE_SESSION
9 DELETE_SESSION
10 GET_SESSIONS
11 GET_SESSION
12 AGGREGATE
"""
    )
    while True:
        try:
            operation_number = int(input("> "))
        except ValueError:
            continue
        if not (0 <= operation_number <= 12):
            continue

        args = validation_funcs[operation_number]()
        res = operation_funcs[operation_number](*args)
        print("<", res)


if __name__ == "__main__":
    repl()
