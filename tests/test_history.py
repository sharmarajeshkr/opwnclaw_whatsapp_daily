from src.history_manager import HistoryManager
import os

def test_history():
    print("Testing HistoryManager...")
    category = "test_cat"
    item = "Some unique test item"
    
    HistoryManager.add_to_history(category, item)
    history = HistoryManager.get_history(category)
    
    if item in history:
        print(f"✅ Success: Item found in {category} history.")
    else:
        print(f"❌ Fail: Item NOT found in {category} history.")
        
    # Test file persistence
    if os.path.exists("data/history.json"):
        print("✅ Success: history.json file exists.")
    else:
        print("❌ Fail: history.json file missing.")

if __name__ == "__main__":
    test_history()
