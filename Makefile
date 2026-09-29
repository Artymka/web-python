# Makefile для Linux (bash / sh)
# Инструменты: black, flake8, radon

# ============================================================
# Параметры
# ============================================================
PYTHON        := python3.11
VENV_DIR      := .venv
VENV_PYTHON   := $(VENV_DIR)/bin/python
VENV_MARKER   := $(VENV_DIR)/bin/activate
SRC_DIR       := src
TEST_DIR      := tests

BLACK_LINE_LENGTH := 79
BLACK_TARGET      := py311
FLAKE8_MAX_LINE   := 79
FLAKE8_MAX_COMPLEXITY := 10
RADON_MIN_GRADE   := B

# ============================================================
# Цели
# ============================================================
.PHONY: help venv install format format-check lint complexity check check-all clean clean-all

help:
	@echo "Available commands:"
	@echo "  make venv          - create virtual environment"
	@echo "  make install       - install dependencies"
	@echo "  make format        - format code with black"
	@echo "  make format-check  - check formatting (CI)"
	@echo "  make lint          - run flake8"
	@echo "  make complexity    - run radon analysis"
	@echo "  make check         - format-check + lint + complexity"
	@echo "  make check-all     - format + lint + complexity"
	@echo "  make clean         - remove caches"
	@echo "  make clean-all     - clean + remove venv"

venv: $(VENV_MARKER)

$(VENV_MARKER):
	@echo "Creating virtual environment..."
	@$(PYTHON) -m venv $(VENV_DIR)
	@echo "Activate with: source $(VENV_DIR)/bin/activate"

install: venv
	@$(VENV_PYTHON) -m pip install --upgrade pip
	@$(VENV_PYTHON) -m pip install -r requirements.txt
	@echo "Dependencies installed."

format: venv
	@$(VENV_PYTHON) -m black --line-length $(BLACK_LINE_LENGTH) --target-version $(BLACK_TARGET) $(SRC_DIR) $(TEST_DIR)

format-check: venv
	@$(VENV_PYTHON) -m black --check --diff --line-length $(BLACK_LINE_LENGTH) --target-version $(BLACK_TARGET) $(SRC_DIR) $(TEST_DIR)

lint: venv
	@$(VENV_PYTHON) -m flake8 --max-line-length=$(FLAKE8_MAX_LINE) --max-complexity=$(FLAKE8_MAX_COMPLEXITY) $(SRC_DIR) $(TEST_DIR)

complexity: venv
	@echo "=== Cyclomatic Complexity ==="
	@$(VENV_PYTHON) -m radon cc --min $(RADON_MIN_GRADE) --show-complexity --total-average $(SRC_DIR)
	@echo "=== Maintainability Index ==="
	@$(VENV_PYTHON) -m radon mi --min C --show $(SRC_DIR)
	@echo "=== Raw metrics ==="
	@$(VENV_PYTHON) -m radon raw --summary $(SRC_DIR)

check: format-check lint complexity
	@echo "All checks passed."

check-all: format lint complexity
	@echo "Code formatted and verified."

clean:
	@echo "Cleaning caches..."
	@find . -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' \) -prune -exec rm -rf {} +

clean-all: clean
	@echo "Removing virtual environment..."
	@rm -rf $(VENV_DIR)
	@echo "Environment removed."
