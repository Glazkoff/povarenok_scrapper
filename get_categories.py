import re
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup

category_list_url = "https://www.povarenok.ru/recipes/cat/"
headers = {
    "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
}
data_path = Path("data")
categories_file = data_path / "categories.json"


def get_categories():
    main_response = requests.get(category_list_url, headers=headers)
    main_src = main_response.text
    soup = BeautifulSoup(main_src, "lxml")

    all_links = soup.find_all(
        "a",
        href=re.compile(
            r"^https?://www.povarenok.ru/recipes/(category|kitchen|destiny|dishes)*"
        ),
    )

    all_categories_dict = {}
    for link in all_links:
        label = link.text.strip()
        href = link["href"]
        all_categories_dict[label] = href

    with open(categories_file, "w", encoding="utf8") as file:
        json.dump(all_categories_dict, file, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    get_categories()
