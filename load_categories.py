import re
import requests
import sqlite3
from bs4 import BeautifulSoup

category_list_url = "https://www.povarenok.ru/recipes/cat/"
from settings.headers import headers
from settings.paths import db_path


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

    query = cur.execute("SELECT id, url, next_page FROM categories WHERE done = FALSE")
    return query.fetchall()


def save_categories(categories_dict):
    db_insert_data = list(categories_dict.items())
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT, title VARCHAR(255), url VARCHAR(255), next_page INTEGER DEFAULT 1, done BOOLEAN DEFAULT FALSE)"
    )

    cur.executemany("INSERT INTO categories (title, url) VALUES(?, ?)", db_insert_data)

    con.commit()
    con.close()


def load_categories(save=True):
    main_response = requests.get(category_list_url, headers=headers)
    main_src = main_response.text
    soup = BeautifulSoup(main_src, "lxml")

    all_links = soup.find_all(
        "a",
        href=re.compile(
            r"^https?://www.povarenok.ru/recipes/(category|kitchen|destiny|dishes)*"
        ),
    )

    black_list = [
        "https://www.povarenok.ru/recipes/search/?ing=1#searchformtop",
        "https://www.povarenok.ru/recipes/cat/",
        "https://www.povarenok.ru/recipes/",
        "https://www.povarenok.ru/recipes/add/",
    ]

    all_categories_dict = {}
    for link in all_links:
        label = link.text.strip()
        href = link["href"]
        if href not in black_list:
            all_categories_dict[label] = href

    if save:
        save_categories(all_categories_dict)

    return all_categories_dict


if __name__ == "__main__":
    load_categories()
