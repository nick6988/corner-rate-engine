import json
import os

FILE_PATH = "leagues.json"

class LeagueCategorizer:
    """Manages dynamic reading, writing, and tier evaluation for football leagues."""

    @classmethod
    def load_data(cls) -> dict:
        if not os.path.exists(FILE_PATH):
            return {}
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def save_data(cls, data: dict) -> None:
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_tier(cls, league_name: str) -> str:
        data = cls.load_data()
        if league_name in data:
            return data[league_name].get("tier", "ALLOWED")
        return "ALLOWED"

    @classmethod
    def get_display_name(cls, english_key: str) -> str:
        data = cls.load_data()
        if english_key in data:
            zh_name = data[english_key].get("zh", "")
            return f"{zh_name} | {english_key}" if zh_name else english_key
        return english_key

    @classmethod
    def get_all_display_names(cls) -> list[str]:
        data = cls.load_data()
        display_list = [cls.get_display_name(key) for key in data.keys()]
        return sorted(display_list)

    @classmethod
    def add_or_update_league(cls, english_name: str, zh_name: str, tier: str) -> None:
        data = cls.load_data()
        data[english_name.strip()] = {
            "zh": zh_name.strip(),
            "tier": tier.strip()
        }
        cls.save_data(data)


def get_league_tier(league_name: str) -> str:
    return LeagueCategorizer.get_tier(league_name)