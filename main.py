import os
import argparse
import sys
import logging 

import requests
import urllib3
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlsplit, unquote


BASE_URL = "https://tululu.org"
current_path = os.path.dirname(__file__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.BasicConfig(level=logging.ERROR, 
                    format='%{asctime}s - %{levelname}s - %{message}s')

def book_url_returner(book_id):
    """Возвращает URL-адрес книги по ее ID."""
    return f"{BASE_URL}/b{book_id}/"


def check_for_redirect(response):
    """Проверяет наличие редиректа в ответе."""
    if response.history:
        raise requests.exceptions.HTTPError("Перенаправление обнаружено")
    return True


def get_image_url(book_id):
    """Находит URL-адрес изображения книги по ее ID."""
    try:
        response = requests.get(book_url_returner(book_id), verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.select_one("div.bookimage img")
        if img_tag:
            return urljoin(BASE_URL, img_tag["src"])
    except requests.exceptions.RequestException:
        return


def get_book_title(book_id):
    """Находит название книги по ее ID."""
    try:
        response = requests.get(book_url_returner(book_id), verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.select_one("h1")
        return title_tag.text.split("::")[0].strip()
    except requests.exceptions.RequestException:
        return


def download_file(url, filename, folder="book/"):
    """Скачивает файл и обрабатывает возможные ошибки."""
    os.makedirs(os.path.join(current_path, folder), exist_ok=True)
    filepath = os.path.join(current_path, folder, sanitize_filename(filename))

    response = requests.get(url, verify=False, stream=True)
    response.raise_for_status()
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return filepath


def download_book(book_id):
    """Скачивает книгу по ее ID."""
    title = get_book_title(book_id)
    url = f"{BASE_URL}/txt.php?id={book_id}"
    response = requests.get(url, verify=False, allow_redirects=True)
    response.raise_for_status()
    filename = f"{book_id}.{title}"

    if check_for_redirect(response):
        download_file(url, f"{filename}.txt")


def download_image(book_id):
    """Скачивает изображение книги по ее ID."""
    url = get_image_url(book_id)
    if not url:
        print(f"Изображение для книги с ID {book_id} не найдено.")
        return
    response = requests.get(url, verify=False, allow_redirects=True)
    if check_for_redirect(response):
        filename = os.path.basename(urlsplit(url).path)
        filename = unquote(filename)
        download_file(url, filename, folder="images/")


def parse_book_page(book_id):
    """Парсит страницу книги и возвращает ее данные."""
    try:
        response = requests.get(book_url_returner(book_id))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        comments_divs = soup.find_all("div", class_="texts")

        book_data = {}
        book_data["title"] = soup.find("h1").text.split("::")[0].strip()
        book_data["author"] = soup.find("h1").find("a").text.strip()
        book_data["genre"] = soup.find(
            "span", class_="d_book").find("a").text.strip()
        book_data["comments"] = [
            div.find("span").text.strip() for div in comments_divs]

        return book_data
    except requests.exceptions.RequestException as e:
        return {}


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
            url = f"{BASE_URL}/txt.php?id={book_id}"
            response = requests.get(url, verify=False, allow_redirects=True)
            response.raise_for_status()
            if check_for_redirect(response):
                download_book(book_id)
                download_image(book_id)
                book_data = parse_book_page(book_id)

                if book_data:
                    print(f"Название: {book_data['title']}")
                    print(f"Автор: {book_data['author']}")
                    print(f"Жанр: {book_data['genre']}")
                    print("Комментарии:")
                    for comment in book_data["comments"]:
                        print(f"- {comment}")
                print("-" * 40)
            else:
                pass
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTPError для книги ID {book_id}: {e}")
            print(
                f"Ошибка при загрузке книги ID {book_id}. Проверьте логи для деталей.", file=sys.stderr)



if __name__ == "__main__":
    main()
