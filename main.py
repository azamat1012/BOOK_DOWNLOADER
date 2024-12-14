import os
import argparse
import sys
import logging
import time

import requests
import urllib3
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlsplit, unquote


BASE_URL = "https://tululu.org"
current_path = os.path.dirname(__file__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def retry_request(url, retries=5, delay=5, **kwargs):
    """Отправляет запрос по указанному url в связи ошибок соединения"""
    for attempt in range(retries+1):
        try:
            response = requests.get(url, verify=False, **kwargs)
            response.raise_for_status()
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logging.error(f"There's an error: {e}")
            print(f"Попытка {attempt} из {retries}: Ошибка подключения - {e}")
            if attempt == retries:
                raise
            time.sleep(delay)


def check_for_redirect(response):
    """Проверяет наличие редиректа в ответе."""
    if response.history:
        raise requests.exceptions.HTTPError("Перенаправление обнаружено")


def parse_book_page(response):
    """Парсит страницу книги и возвращает ее данные."""
    soup = BeautifulSoup(response.text, "html.parser")
    comments_divs = soup.find_all("div", class_="texts")

    base_book_info = {
        "title": soup.find("h1").text.split("::")[0].strip(),
        "author": soup.find("h1").find("a").text.strip(),
        "genre": soup.find("span", class_="d_book").find("a").text.strip(),
        "comments": [div.find("span").text.strip() for div in comments_divs],
        "image_url": urljoin(BASE_URL, soup.select_one("div.bookimage img")["src"]),
    }
    return base_book_info


def download_file(url, filepath):
    """Скачивает файл и обрабатывает возможные ошибки."""

    response = retry_request(url, stream=True)
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return filepath


def download_book(book_id, title):
    """Скачивает книгу по ее ID."""

    params = {
        'id': book_id
    }
    url = f"{BASE_URL}/txt.php"

    filename = sanitize_filename(f"{book_id}.{title}.txt")
    filepath = os.path.join(current_path, "book", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    response = retry_request(url, params=params, allow_redirects=True)
    check_for_redirect(response)
    download_file(url, filepath)

    return filepath


def download_image(image_url):
    """Скачивает изображение книги."""

    filename = unquote(os.path.basename(urlsplit(image_url).path))
    filepath = os.path.join(current_path, "images", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    download_file(image_url, filepath)
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Скачивает книги с сайта tululu.org")
    parser.add_argument("start_id", type=int,
                        help="Начальный ID книги", default=1)
    parser.add_argument("end_id", type=int,
                        help="Конечный ID книги", default=11)
    args = parser.parse_args()

    for book_id in range(args.start_id, args.end_id + 1):
        try:
            url = f"{BASE_URL}/b{book_id}/"
            response = retry_request(url, allow_redirects=True)
            response.raise_for_status()
            check_for_redirect(response)

            base_book_info = parse_book_page(response)

            print(f"Название: {base_book_info['title']}")
            print(f"Автор: {base_book_info['author']}")
            print(f"Жанр: {base_book_info['genre']}")
            print(f"Жанр: {base_book_info['image_url']}")

            print("Комментарии:")
            for comment in base_book_info["comments"]:
                print(f"- {comment}")

            download_book(book_id, base_book_info["title"])
            download_image(base_book_info['image_url'])

        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTPError для книги ID {book_id}: {e}")
            print(
                f"Ошибка при загрузке книги ID {book_id}. Проверьте логи для деталей.", file=sys.stderr)
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка загрузки для книги ID {book_id}: {e}")
            print(
                f"Ошибка при загрузке книги ID {book_id}. Проверьте логи для деталей.", file=sys.stderr)


if __name__ == "__main__":
    main()
