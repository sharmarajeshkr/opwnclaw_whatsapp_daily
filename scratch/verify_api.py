import sys
import os

sys.path.append(os.getcwd())

def test_imports():
    print("Checking imports...")
    try:
        from app.api.routes import router
        print("SUCCESS: API Routes imported successfully.")
    except Exception as e:
        print(f"FAILURE: API Routes import failed: {e}")
        return

    try:
        from app.core.utils import get_user_status
        print("SUCCESS: get_user_status utility found.")
    except Exception as e:
        print(f"FAILURE: get_user_status missing: {e}")
        return

if __name__ == "__main__":
    test_imports()
