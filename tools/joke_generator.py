"""Random joke generator backed by JokeAPI (https://jokeapi.dev/)."""

from __future__ import annotations

import json
from typing import Dict, Optional

import requests


class JokeGenerator:
    BASE_URL = "https://v2.jokeapi.dev/joke"
    VALID_TYPES = {"Any", "General", "Programming", "Knock-Knock", "Dark"}

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()

    def get_random_joke(self, joke_type: str = "Any") -> Optional[Dict]:
        if joke_type not in self.VALID_TYPES:
            joke_type = "Any"
        url = f"{self.BASE_URL}/{joke_type}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            data = response.json()
        except (requests.RequestException, ValueError):
            return None
        if data.get("error"):
            return None
        return data

    def format_joke(self, joke_data: Optional[Dict]) -> str:
        if not joke_data:
            return "Could not fetch a joke right now. Please try again."
        if joke_data.get("type") == "twopart":
            return f"Q: {joke_data.get('setup', '')}\nA: {joke_data.get('delivery', '')}"
        return joke_data.get("joke", "")

    def print_joke(self, joke_type: str = "Any") -> None:
        print(self.format_joke(self.get_random_joke(joke_type)))

    def get_joke_json(self, joke_type: str = "Any") -> str:
        return json.dumps(self.get_random_joke(joke_type), indent=2)
