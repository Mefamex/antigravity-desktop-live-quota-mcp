# antigravity-quota-mcp Makefile
# Standart hedefler: status, inject, test, test-collision, delCache

PYTHON := PYTHONDONTWRITEBYTECODE=1 python3 -B

.PHONY: status inject test test-collision delCache

status:
	@$(PYTHON) main.py --status

inject:
	@$(PYTHON) main.py --inject

test:
	@$(PYTHON) tests/verify_all.py

delCache:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@rm -f /tmp/antigravity-quota-ui.lock
	@echo "[INFO] Önbellek kalıntıları temizlendi."
