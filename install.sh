#!/usr/bin/env bash
# ============================================================================
# antigravity-desktop-live-quota-mcp — Tek Komutla Otomatik Kurulum Betiği (install.sh)
#
# Projeyi klonlayan veya indiren herhangi bir kullanıcının tek bir komutla:
#   $ ./install.sh
# Antigravity ortamına MCP sunucusunu kaydetmesini ve testi koşturmasını sağlar.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${HOME}/.gemini/config"
MCP_CONFIG="${CONFIG_DIR}/mcp_config.json"
TARGET_MAIN="${SCRIPT_DIR}/main.py"
SERVER_KEY="antigravity-desktop-live-quota-mcp"

echo "===================================================================="
echo "⚡ ${SERVER_KEY} Kurulumu Başlatılıyor..."
echo "===================================================================="

# 1. Proje dosya kontrolü
if [[ ! -f "${TARGET_MAIN}" ]]; then
    echo "[HATA] main.py dosyası bulunamadı: ${TARGET_MAIN}" >&2
    exit 1
fi
chmod +x "${TARGET_MAIN}"

# 2. Yapılandırma dizini kontrolü
mkdir -p "${CONFIG_DIR}"

# 3. mcp_config.json dosyasına otomatik kayıt
python3 -B - "${MCP_CONFIG}" "${TARGET_MAIN}" "${SERVER_KEY}" <<'PYEOF'
import sys, json, os, shutil

config_file = sys.argv[1]
main_script = sys.argv[2]
server_key = sys.argv[3]

data = {"mcpServers": {}}
if os.path.exists(config_file):
    try:
        shutil.copyfile(config_file, config_file + ".bak")
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[UYARI] Mevcut mcp_config.json okunamadı, yenisi oluşturuluyor: {e}", file=sys.stderr)

servers = data.setdefault("mcpServers", {})
# Eski kısa isim varsa temizle
servers.pop("antigravity-quota", None)

servers[server_key] = {
    "command": "python3",
    "args": ["-B", main_script],
    "disabled": False
}

with open(config_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"[BAŞARILI] {config_file} içine '{server_key}' MCP sunucusu kaydedildi.")
PYEOF

# 4. Hemen canlı pencereye enjeksiyon testi yap
echo "--------------------------------------------------------------------"
echo "🔍 Aktif Antigravity Desktop penceresine rozet enjeksiyonu deneniyor..."
python3 -B "${TARGET_MAIN}" --inject || true

echo "--------------------------------------------------------------------"
echo "✨ Kurulum tamamlandı!"
echo "Antigravity Desktop veya agy CLI her açıldığında bu MCP sunucusu"
echo "otomatik başlayacak ve canlı kota rozetini pencere üstüne takacaktır."
echo "===================================================================="
