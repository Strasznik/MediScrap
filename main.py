import requests
import json
from unidecode import unidecode
from bs4 import BeautifulSoup
from logger import logger

BASIC_MEDICOVER_URL = "https://www.medicover.pl/lekarze"
API_MEDICOVER_URL = "https://www.medicover.pl/API/pl/Cms.Widgets.SearchDoctors.Main/AutocompleteFilters"


def get_data(url, payload):
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return json.loads(response.text).get('d')
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return []


def fetch_data(payload):
    data = get_data(API_MEDICOVER_URL, payload)
    formatted_data = {
        unidecode(entry).replace(' - ', '-').replace(' ', '-').replace('/', '-').lower()
        for entry in data
    }
    return sorted(list(formatted_data))


def scrape_doctors(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.find_all(attrs={'class': 'doctors-box'})
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return []


def gather_medicover_data():
    all_doctors_data = {}
    cities = fetch_data(json.dumps({"autocompleteType": 2, "city": "", "specialization": "", "getAll": True}))
    professions = fetch_data(json.dumps({"autocompleteType": 1, "city": "", "specialization": "", "getAll": True}))

    for city in cities:
        all_doctors_data[city] = {}
        for profession in professions:
            doctors_info = []
            # We are not expecting to be more than 10-20 pages anyway
            for i in range(1, 100):
                url = f"{BASIC_MEDICOVER_URL}/{profession}/{city},sl,{i},s"
                doctor_boxes = scrape_doctors(url)

                if doctor_boxes:
                    logger.info(f"Szukam lekarzy o profesji {profession.capitalize()} w miejscowości "
                                f"{city.capitalize()} (strona {i})")
                    doctors_info.extend([
                        {
                            "imie": doctor.find('span').text.replace(' - ', '-'),
                            "placowka": doctor.find(attrs={'class': 'doctor-facility'}).text
                            .replace(' - ', '-').replace("|", "-").strip()
                        }
                        for doctor in doctor_boxes if doctor.find('span')
                    ])
                else:
                    all_doctors_data[city][profession] = doctors_info
                    if not all_doctors_data[city][profession]:
                        logger.note(f"W miejscowości {city.capitalize()} nie ma lekarzy o profesji "
                                    f"{profession.capitalize()}")
                    break

    return all_doctors_data


def save_medicover_data(file_name, doctors_data):
    with open(file_name, "w", encoding='utf8') as outfile:
        json.dump(doctors_data, outfile, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    save_medicover_data("medicover_doctors.json", gather_medicover_data())
