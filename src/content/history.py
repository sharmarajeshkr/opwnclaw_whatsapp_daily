import json
import os

HISTORY_DIR = os.path.join("data", "history")

class UserHistoryManager:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.history_file = os.path.join(HISTORY_DIR, f"{phone_number}.json")
        self._ensure_history_dir()

    def _ensure_history_dir(self):
        if not os.path.exists(HISTORY_DIR):
            os.makedirs(HISTORY_DIR, exist_ok=True)

    def _load_history(self):
        if not os.path.exists(self.history_file):
            return {"challenges": [], "medium_posts": [], "news": []}
        try:
            with open(self.history_file, "r") as f:
                return json.load(f)
        except Exception:
            return {"challenges": [], "medium_posts": [], "news": []}

    def _save_history(self, history):
        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=4)

    def add_to_history(self, category, item):
        history = self._load_history()
        if item not in history.get(category, []):
            history.setdefault(category, []).append(item)
            # Keep only last 50 entries
            if len(history[category]) > 50:
                history[category].pop(0)
            self._save_history(history)

    def get_history(self, category):
        return self._load_history().get(category, [])
