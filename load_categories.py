import re
import requests
import sqlite3
from bs4 import BeautifulSoup

category_list_url = "https://www.povarenok.ru/recipes/cat/"
headers = {
    "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
}
from paths import db_path


def save_categories(categories_dict):
    db_insert_data = list(categories_dict.items())
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT, title VARCHAR(255), url VARCHAR(255), done BOOLEAN DEFAULT FALSE)"
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
