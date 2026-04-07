# OpenClaw Makefile

PYTHON = .\venv\Scripts\python.exe
STREAMLIT = .\venv\Scripts\streamlit.exe

.PHONY: help install dashboard daemon clean test

help:
	@echo "Available commands:"
	@echo "  make install   - Install dependencies"
	@echo "  make dashboard - Run the Streamlit dashboard"
	@echo "  make daemon    - Run the multi-user bot daemon"
	@echo "  make test      - Run tests with pytest"
	@echo "  make clean     - Remove temporary files and python cache"

install:
	pip install -r requirements.txt

dashboard:
	$(STREAMLIT) run app.py

daemon:
	$(PYTHON) main.py

test:
	pytest tests/

clean:
	@powershell -Command "Remove-Item -Path __pycache__, .pytest_cache -Recurse -ErrorAction SilentlyContinue; Get-ChildItem -Path . -Filter *.pyc -Recurse | Remove-Item -Force"
	@echo "Cleanup complete."
