import json
import csv
import sqlite3
from random import randrange
import aiohttp
import asyncio
from itertools import islice
from bs4 import BeautifulSoup

from mark_time import mark_time
from proxy_auth_data import proxy_ip, proxy_port, proxy_login, proxy_password
from paths import receipts_path, db_path, categories_file
from load_categories import load_categories

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
}
proxy = f"http://{proxy_login}:{proxy_password}@{proxy_ip}:{proxy_port}"


def get_categories(db_con):
    """Возвращает словарь с названиями категорий и ссылками на них"""
    cur = db_con.cursor()

    try:
        count_query = cur.execute("SELECT COUNT(*) FROM categories")
        count_result = count_query.fetchone()
    except Exception:
        count_result = 0

    if count_result == 0:
        load_categories(save=True)

    query = cur.execute("SELECT id, title, url FROM categories WHERE done = FALSE")
    return query.fetchall()


async def get_category_page_data(session, db_con, category_id, category_url):
    cursor = db_con.cursor()
    page = 1
    while page != 10000:
        page_url = category_url if page == 1 else f"{category_url}~{page}/"
        # TODO: добавить отказоустойчивость
        async with session.get(url=page_url, proxy=proxy, headers=headers) as response:
            if response.status != 200:
                break
            response_text = await response.text()
            category_bs4 = BeautifulSoup(response_text, "lxml")
            all_articles_per_page = category_bs4.find_all("article", class_="item-bl")
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
                    (category_id, title, link) for title, link in links_per_page.items()
                ]
                cursor.executemany(
                    "INSERT OR IGNORE INTO  receipts (category_id, title, url) VALUES (?, ?, ?)",
                    insert_receipts_data,
                )
                db_con.commit()

            await asyncio.sleep(
                randrange(0, 3),
            )

        page += 1
    cursor.execute(f"UPDATE categories SET done=TRUE WHERE id={category_id}")
    db_con.commit()


async def gather_data(db_con):
    categories = get_categories(db_con)
    # TODO: убрать ограничения
    categories = categories[:3]
    async with aiohttp.ClientSession() as session:
        tasks = []
        for category_id, category_name, category_url in categories:
            task = asyncio.create_task(
                get_category_page_data(session, db_con, category_id, category_url)
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
        "CREATE TABLE IF NOT EXISTS receipts (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, title VARCHAR(255), url VARCHAR(255), done BOOLEAN DEFAULT FALSE, FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE CASCADE)"
    )

    # Запускаем асинхронные задачи
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(gather_data(db_con))

    db_con.close()


if __name__ == "__main__":
    main()
