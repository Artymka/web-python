import random
import time
import math

completions = []  # key, datetime, response, stage, error, task
tasks = []  # key, datetime, parameter, session, description, done
sessions = []  # key, datetime, ip, locale, user_agent

# common functions


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
            key = int(random.random())
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


# particular functions
def create_completion(response: str, stage: str, error: str, task: int) -> int:
    return base_create(completions, response, stage, error, task)


def delete_completion(key: int) -> list | None:
    return base_delete(completions, key)


def get_completions() -> list:
    return completions


def get_completion(key: int) -> list | None:
    return base_get(completions, key)


def create_task(parameter: str, session: int, description: str, done: int) -> int:
    return base_create(tasks, parameter, session, description, done)


def delete_task(key: int) -> list | None:
    return base_delete(tasks, key)


def get_tasks() -> list:
    return tasks


def get_task(key: int) -> list | None:
    return base_get(tasks, key)


def create_session(ip: str, locale: str, user_agent: str) -> int:
    return base_create(sessions, ip, locale, user_agent)


def delete_session(key: int) -> list | None:
    return base_delete(sessions, key)


def get_sessions() -> list:
    return sessions


def get_session(key: int) -> list | None:
    return base_get(sessions, key)


def aggregate() -> list:
    filt = [
        completion
        for completion in completions
        if completion[1] >= int(time.time()) - 7 * 60
    ]
    join = [[t, c] for t in tasks for c in filt if t[0] == c[5]]
    proj = [[c[2], t[4], t[2]] for t, c in join]

    return proj


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
