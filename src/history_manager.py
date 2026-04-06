import json
import os

HISTORY_FILE = "data/history.json"

class HistoryManager:
    @staticmethod
    def _load_history():
        if not os.path.exists(HISTORY_FILE):
            os.makedirs("data", exist_ok=True)
            return {"challenges": [], "medium_posts": [], "news": []}
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"challenges": [], "medium_posts": [], "news": []}

    @staticmethod
    def _save_history(history):
        os.makedirs("data", exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)

    @staticmethod
    def add_to_history(category, item):
        history = HistoryManager._load_history()
        if item not in history.get(category, []):
            history.setdefault(category, []).append(item)
            # Keep only last 50 for performance
            if len(history[category]) > 50:
                history[category].pop(0)
            HistoryManager._save_history(history)

    @staticmethod
    def get_history(category):
        return HistoryManager._load_history().get(category, [])
