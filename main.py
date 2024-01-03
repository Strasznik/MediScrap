from typing import List, Dict, Union
import requests
import json
from unidecode import unidecode
from bs4 import BeautifulSoup
from logger import logger


class MedicoverScraper:
    BASIC_URL = "https://www.medicover.pl/lekarze"
    API_URL = "https://www.medicover.pl/API/pl/Cms.Widgets.SearchDoctors.Main/AutocompleteFilters"

    def __init__(self, basic_url: str = BASIC_URL, api_url: str = API_URL, pagination_limit: int = 50) -> None:
        """
        Initializes the MedicoverScraper class.

        Args:
        - basic_url (str): Base URL for fetching doctor information.
        - api_url (str): URL for Medicover "API".
        - pagination_limit (int): Maximum limit for pagination.
        """
        self.basic_url = basic_url
        self.api_url = api_url
        self.pagination_limit = pagination_limit

    @staticmethod
    def get_data(url: str, payload: str) -> List[Union[str, Dict[str, str]]]:
        """
        Sends a POST request to retrieve data from a specified URL.

        Args:
        - url (str): URL for the POST request.
        - payload (str): JSON-formatted payload.

        Returns:
        - list: Retrieved data or an empty list if an error occurs.
        """
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()
            return json.loads(response.text).get('d', [])
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return []

    def fetch_data(self, payload: str) -> List[str]:
        """
        Fetches and formats data from the Medicover API.

        Args:
        - payload (str): JSON-formatted payload.

        Returns:
        - list: Formatted list of retrieved data.
        """
        data = self.get_data(self.api_url, payload)
        formatted_data = {self.format_entry(entry) for entry in data}
        return sorted(list(formatted_data))

    @staticmethod
    def format_entry(entry: str) -> str:
        """
        Formats an entry by replacing characters and converting to lowercase.

        Args:
        - entry (str): Entry to be formatted.

        Returns:
        - str: Formatted entry.
        """
        return unidecode(entry).replace(' - ', '-').replace(' ', '-').replace('/', '-').lower()

    @staticmethod
    def scrape_doctors(url: str) -> List[BeautifulSoup]:
        """
        Scrapes doctor information from the provided URL.

        Args:
        - url (str): URL for scraping.

        Returns:
        - list: List of doctor information.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup.find_all(class_='doctors-box')
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return []

    def gather_medicover_data(self) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        """
        Gathers data for all cities and professions available in Medicover.

        Returns:
        - dict: Collected data for all cities and professions.
        """
        all_doctors_data: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
        cities = self.fetch_data(json.dumps({"autocompleteType": 2, "city": "", "specialization": "",
                                             "getAll": True}))
        professions = self.fetch_data(json.dumps({"autocompleteType": 1, "city": "", "specialization": "",
                                                  "getAll": True}))

        for city in cities:
            all_doctors_data[city] = {}
            for profession in professions:
                doctors_info = self.scrape_doctors_info(profession, city)
                all_doctors_data[city][profession] = doctors_info

        return all_doctors_data

    def scrape_doctors_info(self, profession: str, city: str) -> List[Dict[str, str]]:
        """
        Scrapes information of doctors for a specific profession and city.

        Args:
        - profession (str): Profession of the doctors.
        - city (str): City for which doctors' information is fetched.

        Returns:
        - list: List of doctor information.
        """
        doctors_info: List[Dict[str, str]] = []
        for i in range(1, self.pagination_limit):
            url = f"{self.basic_url}/{profession}/{city},sl,{i},s"
            doctor_boxes = self.scrape_doctors(url)

            if doctor_boxes:
                logger.info(f"Szukam lekarzy o profesji {profession.capitalize()} w miejscowości "
                            f"{city.capitalize()} (strona {i})")
                extracted_info = self.extract_doctor_info(doctor_boxes)
                doctors_info.extend(extracted_info)
            else:
                if not doctors_info:
                    logger.note(f"W miejscowości {city.capitalize()} nie ma lekarzy o profesji "
                                f"{profession.capitalize()}")
                break

        return doctors_info

    @staticmethod
    def extract_doctor_info(doctor_boxes: List[BeautifulSoup]) -> List[Dict[str, str]]:
        """
        Extracts information from doctor boxes.

        Args:
        - doctor_boxes (list): List of doctor boxes.

        Returns:
        - list: Extracted doctor information.
        """
        return [
            {
                "imie": doctor.find('span').text.replace(' - ', '-'),
                "placowka": doctor.find(class_='doctor-facility').text.replace(' - ', '-').replace("|", "-").strip()
            }
            for doctor in doctor_boxes if doctor.find('span')
        ]

    @staticmethod
    def save_medicover_data(file_name: str, doctors_data: Dict[str, Dict[str, List[Dict[str, str]]]]):
        """
        Saves Medicover data to a JSON file.

        Args:
        - file_name (str): Name of the output file.
        - doctors_data (dict): Data to be saved.
        """
        with open(file_name, "w", encoding='utf8') as outfile:
            json.dump(doctors_data, outfile, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    scraper = MedicoverScraper()
    scraper.save_medicover_data("medi_docs.json", scraper.gather_medicover_data())
