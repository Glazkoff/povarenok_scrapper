import sqlite3
import json
import re
from random import randrange
import aiohttp
import asyncio
from bs4 import BeautifulSoup

from mark_time import mark_time
from proxy_auth_data import proxy_ip, proxy_port, proxy_login, proxy_password
from paths import receipts_path, db_path, data_path
from load_categories import get_categories

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
}
proxy = f"http://{proxy_login}:{proxy_password}@{proxy_ip}:{proxy_port}"


async def get_receipt_page_data(session, db_con, receipt_url):
    cursor = db_con.cursor()
    async with session.get(url=receipt_url, proxy=proxy, headers=headers) as response:
        if response.status != 200:
            return None
        response_text = await response.text()
        receipt_bs4 = BeautifulSoup(response_text, "lxml")

        receipt_text = ""
        if h2 := receipt_bs4.find("h2", text=re.compile("Рецепт")):
            # Классический путь
            if recipe_instructions_ul := h2.findNext(
                "ul", itemprop="recipeInstructions"
            ):
                receipt_text = recipe_instructions_ul.text.strip()
                if receipt_text == "":
                    receipt_text = (
                        receipt_bs4.find("h2", text=re.compile("Рецепт"))
                        .findNext("div")
                        .text.strip()
                    )

            else:
                receipt_text = (
                    receipt_bs4.find("h2", text=re.compile("Рецепт"))
                    .findNext("div")
                    .text.strip()
                )
        elif h2 := receipt_bs4.find("div", class_="h2title", text=re.compile("Рецепт")):
            if recipe_steps_div := h2.findNext("div", class_="recipe-steps"):
                receipt_text = recipe_steps_div.text.strip()

        result = "".join(receipt_text.splitlines())
        # TODO: добавить сохранение текста в БД и отметку об обработанности
        tmp_path = data_path / "tmp.txt"
        try:
            with open(tmp_path, "w", encoding="utf8") as tmp_file:
                print("ВЫГРУЗИЛИ ТЕКСТ ДЛЯ РЕЦЕПТА ПО URL:", receipt_url)
                json.dump(result, tmp_file, ensure_ascii=False, indent=4)
        except Exception as e:
            print(e)
        return receipt_text


async def get_category_page_data(
    session, db_con, category_id, category_url, next_page=1
):
    cursor = db_con.cursor()
    page = next_page
    while page != 10000:
        page_url = category_url if page == 1 else f"{category_url}~{page}/"
        try:
            async with session.get(
                url=page_url, proxy=proxy, headers=headers
            ) as response:
                if response.status != 200:
                    break
                response_text = await response.text()
                category_bs4 = BeautifulSoup(response_text, "lxml")
                all_articles_per_page = category_bs4.find_all(
                    "article", class_="item-bl"
                )
                if all_articles_per_page == []:
                    break
                links_per_page = {}
                for article in all_articles_per_page:
                    try:
                        header = article.find("h2")
                        receipt_header = header.text.strip()
                        receipt_link = header.find("a").get("href", None)
                        print(
                            f"Категория #{category_id} / Страница {page} --- {receipt_header} {receipt_link}"
                        )
                        links_per_page[receipt_header] = receipt_link
                    except Exception as e:
                        print("ERROR! ", e)

                if links_per_page != {}:

                    insert_receipts_data = [
                        (category_id, title, link)
                        for title, link in links_per_page.items()
                    ]
                    cursor.executemany(
                        "INSERT OR IGNORE INTO  receipts (category_id, title, url) VALUES (?, ?, ?)",
                        insert_receipts_data,
                    )
                    db_con.commit()

                    receipt_tasks = []
                    for link in links_per_page.values():
                        task = asyncio.create_task(
                            get_receipt_page_data(session, db_con, link)
                        )
                        receipt_tasks.append(task)
                    await asyncio.gather(*receipt_tasks)

                await asyncio.sleep(
                    randrange(0, 3),
                )

        except Exception as e:
            break

        page += 1
        cursor.execute(
            f"UPDATE categories SET next_page={page+1} WHERE id={category_id}"
        )
    cursor.execute(f"UPDATE categories SET done=TRUE WHERE id={category_id}")
    db_con.commit()


async def gather_data(db_con):
    categories = get_categories(db_con)
    # TODO: убрать ограничения
    categories = categories[:3]
    async with aiohttp.ClientSession() as session:
        tasks = []
        for category_id, category_url, next_page in categories:
            task = asyncio.create_task(
                get_category_page_data(
                    session, db_con, category_id, category_url, next_page
                )
            )
            tasks.append(task)

        await asyncio.gather(*tasks)


@mark_time
def main():
    # Создаём необходимые папки, если не существуют
    if not receipts_path.exists() or not receipts_path.is_dir():
        receipts_path.mkdir()

    # Создаём таблицы в БД, если не существуют
    db_con = sqlite3.connect(db_path)
    cur = db_con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS receipts (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, title VARCHAR(255), url VARCHAR(255) UNIQUE, done BOOLEAN DEFAULT FALSE, FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE CASCADE)"
    )

    # Запускаем асинхронные задачи
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(gather_data(db_con))

    db_con.close()


if __name__ == "__main__":
    main()
