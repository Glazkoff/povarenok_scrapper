import sqlite3
import json
import re
from random import randrange
import aiohttp
import asyncio
from bs4 import BeautifulSoup

from decorators.mark_time import mark_time
from settings.config import PROXY_IP, PROXY_PORT, PROXY_LOGIN, PROXY_PASSWORD
from settings.paths import db_path
from settings.headers import headers
from load_categories import get_categories

proxy = f"http://{PROXY_LOGIN}:{PROXY_PASSWORD}@{PROXY_IP}:{PROXY_PORT}"


async def get_receipt_page_data(session, db_con, receipt_url):
    cursor = db_con.cursor()
    async with session.get(url=receipt_url, proxy=proxy, headers=headers) as response:
        if response.status != 200:
            return None
        response_text = await response.text()
        receipt_bs4 = BeautifulSoup(response_text, "lxml")

        receipt_text = ""
        ingredients = []
        if h2 := receipt_bs4.find("h2", text=re.compile("Рецепт")):
            # Классический путь
            # ПРИМЕР: https://www.povarenok.ru/recipes/show/58070/
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

        if ingredients_div := receipt_bs4.find("div", class_="ingredients-bl"):
            ingredients_items = ingredients_div.find_all(
                "li", itemprop="recipeIngredient"
            )

            for item in ingredients_items:
                a = item.find("a")
                ingredient_label = a.text.strip()
                ingredient_url = a["href"]
                ingredients.append((ingredient_label, ingredient_url))
                print(f'--- Ингредиент "{ingredient_label}" - {ingredient_url}')

        text_result = "".join(receipt_text.splitlines())
        try:
            cursor.executemany(
                "INSERT OR IGNORE INTO ingredients (title, url) VALUES (?, ?)",
                ingredients,
            )
            receipt_id_query = cursor.execute(
                "SELECT id FROM receipts WHERE url=?", (receipt_url,)
            )
            receipt_id = receipt_id_query.fetchone()
            receipt_id = receipt_id[0]

            ingredients_in_receipts_data = [
                (receipt_id, ingredient[1]) for ingredient in ingredients
            ]
            cursor.executemany(
                "INSERT OR IGNORE INTO ingredients_in_receipts (receipt_id, ingredient_id) SELECT ?, id FROM ingredients WHERE url=?",
                ingredients_in_receipts_data,
            )

            cursor.execute(
                "INSERT OR IGNORE INTO receipts_data (receipt_id, text) VALUES (?, ?)",
                (receipt_id, text_result),
            )
            cursor.execute("UPDATE receipts SET done=1 WHERE id=?", (receipt_id,))
            db_con.commit()
        except Exception as e:
            print("e", e)
            return None

        await asyncio.sleep(
            randrange(0, 1),
        )
        print(f"ВЫГРУЖЕН РЕЦЕПТ #{receipt_id} - {receipt_url}")
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
            "UPDATE categories SET next_page=? WHERE id=?",
            (
                page + 1,
                category_id,
            ),
        )
    cursor.execute("UPDATE categories SET done=1 WHERE id=?", (category_id,))
    db_con.commit()


async def gather_data(db_con):
    categories = get_categories(db_con)

    cursor = db_con.cursor()
    receipts_query = cursor.execute("SELECT url FROM receipts WHERE done=FALSE")
    receipts = receipts_query.fetchall()

    # TODO: убрать ограничения
    receipts = receipts[:3]
    categories = categories[:3]
    async with aiohttp.ClientSession() as session:
        tasks = []

        # Добавление заданий для необработанных рецептов
        for receipt in receipts:
            receipt_url = receipt[0]
            task = asyncio.create_task(
                get_receipt_page_data(session, db_con, receipt_url)
            )
            tasks.append(task)

        # Добавление заданий для категорий
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
    # Создаём таблицы в БД, если не существуют
    db_con = sqlite3.connect(db_path)
    cur = db_con.cursor()

    # Таблица со ссылками рецептов и метаинформацией
    cur.execute(
        "CREATE TABLE IF NOT EXISTS receipts (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, title VARCHAR(255), url VARCHAR(255) UNIQUE, done BOOLEAN DEFAULT FALSE, FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE CASCADE)"
    )

    # Таблица с текстами рецептов
    cur.execute(
        "CREATE TABLE IF NOT EXISTS receipts_data (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_id INTEGER UNIQUE, text TEXT, FOREIGN KEY (receipt_id) REFERENCES receipts (receipt_id) ON DELETE CASCADE)"
    )

    # Таблица с ингредиентами и ссылками на их страницы
    cur.execute(
        "CREATE TABLE IF NOT EXISTS ingredients (id INTEGER PRIMARY KEY AUTOINCREMENT, title VARCHAR(255), url VARCHAR(255) UNIQUE)"
    )

    # M2M-связь рецептов и ингредиентов
    cur.execute(
        "CREATE TABLE IF NOT EXISTS ingredients_in_receipts (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_id INTEGER, ingredient_id INTEGER, FOREIGN KEY (receipt_id) REFERENCES receipts (receipt_id) ON DELETE CASCADE, FOREIGN KEY (ingredient_id) REFERENCES ingredients (ingredient_id) ON DELETE CASCADE)"
    )

    # Запускаем асинхронные задачи
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(gather_data(db_con))

    db_con.close()


if __name__ == "__main__":
    main()
