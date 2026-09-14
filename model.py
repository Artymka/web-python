import random
import time
import math
import threading

completions = []  # key, datetime, response, stage, error, task
completions_lock = threading.Lock()
tasks = []  # key, datetime, parameter, session, description, done
tasks_lock = threading.Lock()
sessions = []  # key, datetime, ip, locale, user_agent
sessions_lock = threading.Lock()


# common functions


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


# particular functions


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
def create_task(parameter: str, session: int, description: str, done: int) -> int:
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


@use_lock(completions_lock)
@use_lock(tasks_lock)
def aggregate() -> list:
    filt = [
        completion
        for completion in completions
        if completion[1] >= int(time.time()) - 7 * 60
    ]
    join = []
    pasted_tasks = set()
    for c in filt:
        pasted = False
        for t in tasks:
            if c[5] == t[0]:
                join.append([c[2], t[4], t[2]])
                pasted_tasks.add(t[0])
                pasted = True
                break
        if not pasted:
            join.append([c[2], None, None])
    for t in tasks:
        if t[0] not in pasted_tasks:
            join.append([None, t[4], t[2]])

    return join


def repl():
    print("Firstly type command, press enter and then type arguments.")
    while True:
        print("> ", end="")
        command = input()
        # print("  ", end="")
        # args = input().split()

        match command:
            case "create_completion":
                print("  response stage error task")
                print("  ", end="")
                args = input().split()
                try:
                    response = args[0]
                    stage = args[1]
                    error = args[2]
                    task = int(args[3])
                    res = create_completion(response, stage, error, task)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "delete_completion":
                print("  key")
                print("  ", end="")
                args = input().split()
                try:
                    key = int(args[0])
                    res = delete_completion(key)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "get_completions":
                print(f"< {get_completions()}")
            case "get_completion":
                print("  key")
                print("  ", end="")
                args = input().split()
                try:
                    key = int(args[0])
                    res = get_completion(key)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "create_task":
                print("  parameter session description done")
                print("  ", end="")
                args = input().split()
                try:
                    parameter = args[0]
                    session = int(args[1])
                    description = args[2]
                    done = int(args[3])
                    res = create_task(parameter, session, description, done)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "delete_task":
                print("  key")
                print("  ", end="")
                args = input().split()
                try:
                    key = int(args[0])
                    res = delete_task(key)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "get_tasks":
                print(f"< {get_tasks()}")
            case "get_task":
                print("  key")
                print("  ", end="")
                args = input().split()
                try:
                    key = int(args[0])
                    res = get_task(key)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "create_session":
                print("  ip locale user_agent")
                print("  ", end="")
                args = input().split()
                try:
                    ip = args[0]
                    locale = args[1]
                    user_agent = args[2]
                    res = create_session(ip, locale, user_agent)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "delete_session":
                print("  key")
                print("  ", end="")
                args = input().split()
                try:
                    key = int(args[0])
                    res = delete_session(key)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "get_sessions":
                print(f"< {get_sessions()}")
            case "get_session":
                print("  key")
                print("  ", end="")
                args = input().split()
                try:
                    key = int(args[0])
                    res = get_session(key)
                    print(f"< {res}")
                except Exception as e:
                    print("< wrong args")
            case "aggregate":
                print(f"<\n{aggregate()}")


if __name__ == "__main__":
    repl()
