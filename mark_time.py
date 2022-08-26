import datetime


def mark_time(func):
    def wrapper():
        start_time = datetime.datetime.now()
        func()
        end_time = datetime.datetime.now()
        print(f"Время выполнения: {end_time - start_time}")

    return wrapper
