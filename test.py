from pathlib import Path
import asyncio
import datetime
from random import randrange

count = 0
start_time = datetime.datetime.now()

test_folder = Path("./data/test")

if not test_folder.exists():
    test_folder.mkdir()

filename = start_time.__str__().replace(" ", "_").replace(".", "_").replace(":", "-")
test_file = test_folder / f"{filename}.txt"
test_file.touch()


async def get_task(i, last):
    try:
        print(f"{i} - start")
        await asyncio.sleep(
            randrange(10, 500),
        )
        global count
        count += 1
        print(f"{i} - end {count}/{last}")
        current_time = datetime.datetime.now()
        diff = current_time - start_time
        print(f"Time has passed: {diff}")

        if diff > datetime.timedelta(seconds=20):
            print("20 sec finished!!!")
            for task in asyncio.all_tasks():
                task.cancel()

        with test_file.open("a", encoding="utf8") as f:
            f.write("---\n")
    except asyncio.CancelledError:
        pass


async def gather_data(last):
    try:
        tasks = []
        for i in range(last):
            task = asyncio.create_task(get_task(i, last))
            tasks.append(task)
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


def main():

    with test_file.open("w", encoding="utf8") as f:
        f.write("Start writing\n")

    asyncio.run(gather_data(1000))

    end_time = datetime.datetime.now()
    print(f"Lead time: {end_time - start_time}")


if __name__ == "__main__":
    main()
