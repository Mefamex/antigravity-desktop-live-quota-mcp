# =============================================================================
# antigravity-desktop-live-quota-mcp — Makefile
#
# Self-documenting task runner.
# Running bare 'make' in a terminal lists available targets in color.
#
# ⚠️ 6 MANDATORY LIFECYCLE TARGETS:
# [install, reinstall, update, run, clean, remove]
# =============================================================================

.DEFAULT_GOAL := help
.PHONY: help install reinstall update run status inject test-notify test verify clean clean-scratch delCache remove enable-cdp

help: ## List available targets and their descriptions
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available Targets:"
	@LC_ALL=C grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# --- 1. INSTALL & LIFECYCLE (Mandatory Targets) ---

install: ## Register the MCP server in mcp_config.json and inject the badge
	@echo "==> Installing antigravity-desktop-live-quota-mcp..."
	@chmod +x install.sh
	@./install.sh

enable-cdp: ## Install user-level CDP launcher override for Antigravity Desktop 2.33+
	@chmod +x install.sh
	@./install.sh --cdp-only

reinstall: remove install ## Remove existing installation and perform a clean reinstall
	@echo "==> Reinstall complete."

update: clean ## Zero dependencies; clean bytecode and run verification tests
	@echo "==> Updating and verifying project components..."
	@python3 -B tests/verify_all.py
	@echo "==> Update and verification complete."

define _REMOVE_MCP_PY
import json
import os
import sys

config_path = os.path.expanduser("~/.gemini/config/mcp_config.json")
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            servers = data.get("mcpServers")
            if isinstance(servers, dict):
                removed = False
                for key in ("antigravity-desktop-live-quota-mcp", "antigravity-quota"):
                    if key in servers:
                        servers.pop(key, None)
                        removed = True
                if removed:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                        f.write("\n")
    except Exception as exc:
        print(f"[WARN] Could not update {config_path}: {exc}", file=sys.stderr)
endef
export _REMOVE_MCP_PY

remove: ## Remove MCP registration from mcp_config.json and managed launcher files
	@echo "==> Removing MCP registration..."
	@python3 -B -c "$$_REMOVE_MCP_PY" || true
	@for f in "$(HOME)/.local/share/applications/antigravity.desktop" "$(HOME)/.local/bin/antigravity"; do \
		if [ -f "$$f" ] && head -c 1024 "$$f" 2>/dev/null | tr -d '\0' | grep -qF "managed-by: antigravity-desktop-live-quota-mcp"; then \
			rm -f "$$f" && echo "[INFO] Removed -> $$f"; \
		fi; \
	done
	@command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(HOME)/.local/share/applications" >/dev/null 2>&1 || true
	@command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
	@make clean
	@echo "==> Removal complete."

# --- 2. RUN & TEST ---

run: ## Start the MCP Stdio server directly in JSON-RPC stdio mode
	@python3 -B main.py

status: ## Print live quota, open windows, and leader status as JSON
	@python3 -B main.py --status

inject: ## Immediately inject the badge into open Antigravity Desktop windows
	@python3 -B main.py --inject

test-notify: ## Send a sample critical quota test desktop notification
	@python3 -B main.py --test-notify

test: ## Run cold-start, multi-instance lock, failover, and CDP tests
	@python3 -B tests/verify_all.py

verify: clean test ## Run full cleanup and verification chain before Commit/Push
	@echo "==> All checks passed successfully (ALL_OK)."

# --- 3. CLEANUP ---

clean: delCache ## Clean temporary files, bytecode, and test artifacts

clean-scratch: ## Clean Antigravity brain scratch/ temporary session files
	@python3 -B main.py --clean-scratch

delCache: ## Remove build and bytecode caches (__pycache__)
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@rm -f /tmp/antigravity-desktop-live-quota*.lock 2>/dev/null || true
	@echo "[INFO] Cache artifacts cleaned."
