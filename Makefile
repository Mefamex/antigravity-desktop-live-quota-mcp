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
.PHONY: help install reinstall update run clean remove status inject test verify delCache

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

reinstall: remove install ## Kurulumu kaldırıp sıfırdan tertemiz yeniden kurar
	@echo "==> Yeniden kurulum tamamlandı."

update: clean ## Bağımlılık gerektirmez; bytecode temizler ve testleri doğrular
	@echo "==> Proje bileşenleri güncelleniyor ve doğrulanıyor..."
	@python3 -B tests/verify_all.py
	@echo "==> Güncelleme ve doğrulama tamamlandı."

remove: ## MCP kaydını mcp_config.json içinden temizler ve önbellekleri siler
	@echo "==> MCP kaydı temizleniyor..."
	@python3 -B -c "import json, os; p=os.path.expanduser('~/.gemini/config/mcp_config.json'); (lambda f: [f and [d.setdefault('mcpServers',{}).pop('antigravity-desktop-live-quota-mcp',None), d.setdefault('mcpServers',{}).pop('antigravity-quota',None), open(p,'w').write(json.dumps(d,indent=2))] for d in [json.load(open(p))]])(os.path.exists(p))" || true
	@make clean
	@echo "==> Kaldırma işlemi tamamlandı."

# --- 2. ÇALIŞTIRMA & TEST ---

run: ## MCP Stdio sunucusunu doğrudan JSON-RPC stdio modunda başlatır
	@python3 -B main.py

status: ## Canlı kotayı, açık pencereleri ve lider durumunu terminalde JSON yazdırır
	@python3 -B main.py --status

inject: ## Açık Antigravity Desktop penceresine rozeti hemen enjekte eder
	@python3 -B main.py --inject

test: ## Soğuk başlangıç, çoklu örnek kilit, failover ve CDP testlerini koşturur
	@python3 -B tests/verify_all.py

verify: clean test ## Commit/Push öncesi tam temizlik ve doğrulama zincirini çalıştırır
	@echo "==> Tüm kontroller başarıyla tamamlandı (ALL_OK)."

# --- 3. TEMİZLİK ---

clean: delCache ## Geçici dosyaları, bytecode ve test kalıntılarını temizler

delCache: ## Derleme ve bytecode önbelleğini (__pycache__) siler
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@rm -f /tmp/antigravity-desktop-live-quota*.lock 2>/dev/null || true
	@echo "[INFO] Önbellek kalıntıları temizlendi."
