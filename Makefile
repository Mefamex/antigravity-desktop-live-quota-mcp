# =============================================================================
# antigravity-desktop-live-quota-mcp — Makefile
#
# Kendi kendini belgeleyen (Self-documenting) görev yöneticisi.
# Terminalde sadece 'make' yazıldığında kullanılabilir komutları renkli listeler.
#
# ⚠️ 6 ZORUNLU YAŞAM DÖNGÜSÜ HEDEFİ:
# [install, reinstall, update, run, clean, remove]
# =============================================================================

.DEFAULT_GOAL := help
.PHONY: help install reinstall update run status inject test-notify test verify clean clean-scratch delCache remove enable-cdp

help: ## Mevcut komutları ve açıklamalarını listeler
	@echo "Kullanım: make [komut]"
	@echo ""
	@echo "Kullanılabilir Komutlar:"
	@LC_ALL=C grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# --- 1. KURULUM & YAŞAM DÖNGÜSÜ (Zorunlu Hedefler) ---

install: ## MCP sunucusunu mcp_config.json içine kaydeder ve pencereye rozeti enjekte eder
	@echo "==> antigravity-desktop-live-quota-mcp kuruluyor..."
	@chmod +x install.sh
	@./install.sh

enable-cdp: ## Antigravity Desktop 2.33+ için kullanıcı-seviyesi CDP launcher override kurar
	@chmod +x install.sh
	@./install.sh --cdp-only

reinstall: remove install ## Kurulumu kaldırıp sıfırdan tertemiz yeniden kurar
	@echo "==> Yeniden kurulum tamamlandı."

update: clean ## Bağımlılık gerektirmez; bytecode temizler ve testleri doğrular
	@echo "==> Proje bileşenleri güncelleniyor ve doğrulanıyor..."
	@python3 -B tests/verify_all.py
	@echo "==> Güncelleme ve doğrulama tamamlandı."

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
        print(f"[UYARI] {config_path} güncellenemedi: {exc}", file=sys.stderr)
endef
export _REMOVE_MCP_PY

remove: ## MCP kaydını mcp_config.json içinden ve yönetilen launcher dosyalarından temizler
	@echo "==> MCP kaydı temizleniyor..."
	@python3 -B -c "$$_REMOVE_MCP_PY" || true
	@for f in "$(HOME)/.local/share/applications/antigravity.desktop" "$(HOME)/.local/bin/antigravity"; do \
		if [ -f "$$f" ] && head -c 1024 "$$f" 2>/dev/null | tr -d '\0' | grep -qF "managed-by: antigravity-desktop-live-quota-mcp"; then \
			rm -f "$$f" && echo "[INFO] Temizlendi -> $$f"; \
		fi; \
	done
	@command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(HOME)/.local/share/applications" >/dev/null 2>&1 || true
	@command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
	@make clean
	@echo "==> Kaldırma işlemi tamamlandı."

# --- 2. ÇALIŞTIRMA & TEST ---

run: ## MCP Stdio sunucusunu doğrudan JSON-RPC stdio modunda başlatır
	@python3 -B main.py

status: ## Canlı kotayı, açık pencereleri ve lider durumunu terminalde JSON yazdırır
	@python3 -B main.py --status

inject: ## Açık Antigravity Desktop penceresine rozeti hemen enjekte eder
	@python3 -B main.py --inject

test-notify: ## Masaüstüne örnek bir kritik kota test bildirimi gönderir
	@python3 -B main.py --test-notify

test: ## Soğuk başlangıç, çoklu örnek kilit, failover ve CDP testlerini koşturur
	@python3 -B tests/verify_all.py

verify: clean test ## Commit/Push öncesi tam temizlik ve doğrulama zincirini çalıştırır
	@echo "==> Tüm kontroller başarıyla tamamlandı (ALL_OK)."

# --- 3. TEMİZLİK ---

clean: delCache ## Geçici dosyaları, bytecode ve test kalıntılarını temizler

clean-scratch: ## Antigravity brain scratch/ geçici oturum dosyalarını temizler
	@python3 -B main.py --clean-scratch

delCache: ## Derleme ve bytecode önbelleğini (__pycache__) siler
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@rm -f /tmp/antigravity-desktop-live-quota*.lock 2>/dev/null || true
	@echo "[INFO] Önbellek kalıntıları temizlendi."
