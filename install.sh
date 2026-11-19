#!/usr/bin/env bash
# ============================================================================
# antigravity-desktop-live-quota-mcp — Tek Komutla Otomatik Kurulum Betiği (install.sh)
#
# Kullanım:
#   ./install.sh                    # MCP kaydı + 2.33+ kalıcı CDP launcher + enjeksiyon
#   ./install.sh --cdp-only         # Yalnızca kullanıcı-seviyesi CDP launcher kurulumu
#   ./install.sh --no-cdp-launcher  # Yalnızca MCP kaydı ve enjeksiyon
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${HOME}/.gemini/config"
MCP_CONFIG="${CONFIG_DIR}/mcp_config.json"
TARGET_MAIN="${SCRIPT_DIR}/main.py"
SERVER_KEY="antigravity-desktop-live-quota-mcp"
MARKER="managed-by: antigravity-desktop-live-quota-mcp"

CDP_ONLY=0
NO_CDP_LAUNCHER=0
for arg in "$@"; do
    case "${arg}" in
        --cdp-only)
            CDP_ONLY=1
            ;;
        --no-cdp-launcher)
            NO_CDP_LAUNCHER=1
            ;;
        -h|--help)
            sed -n '2,9p' "$0"
            exit 0
            ;;
        *)
            echo "[HATA] Bilinmeyen parametre: ${arg}" >&2
            exit 2
            ;;
    esac
done

setup_cdp_launcher() {
    echo "--------------------------------------------------------------------"
    echo "🔧 Antigravity Desktop (>= 2.33.0) kalıcı CDP launcher ayarlanıyor (sudo gerekmez)..."

    local sys_desktop="/usr/share/applications/antigravity.desktop"
    local user_app_dir="${HOME}/.local/share/applications"
    local user_desktop="${user_app_dir}/antigravity.desktop"
    local user_bin_dir="${HOME}/.local/bin"
    local user_bin="${user_bin_dir}/antigravity"

    # 1. XDG Desktop Entry override (~/.local/share/applications/antigravity.desktop)
    if [[ -f "${sys_desktop}" ]]; then
        mkdir -p "${user_app_dir}"
        python3 -B - "${sys_desktop}" "${user_desktop}" "${MARKER}" <<'PYEOF'
import os
import re
import shutil
import sys

src_path, dst_path, marker = sys.argv[1:4]
marker_line = f"# {marker}"

if os.path.exists(dst_path):
    with open(dst_path, "r", encoding="utf-8", errors="ignore") as f:
        existing = f.read()
    if marker not in existing:
        shutil.copyfile(dst_path, dst_path + ".bak")

with open(src_path, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

out_lines = [marker_line]
for line in lines:
    if line.startswith("Exec=") and "--remote-debugging-port" not in line:
        # /usr/bin/antigravity veya antigravity sonrası --remote-debugging-port=0 ekle
        if "/usr/bin/antigravity" in line:
            line = line.replace("/usr/bin/antigravity", "/usr/bin/antigravity --remote-debugging-port=0", 1)
        else:
            line = re.sub(r"^Exec=(\S+)", r"Exec=\1 --remote-debugging-port=0", line)
    out_lines.append(line)

with open(dst_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")
print(f"[BAŞARILI] Desktop launcher güncellendi -> {dst_path}")
PYEOF

        if command -v desktop-file-validate >/dev/null 2>&1; then
            if desktop-file-validate "${user_desktop}"; then
                echo "[BAŞARILI] desktop-file-validate doğrulaması geçti."
            else
                echo "[UYARI] desktop-file-validate uyarı döndürdü: ${user_desktop}" >&2
            fi
        fi

        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database "${user_app_dir}" >/dev/null 2>&1 || true
        fi
        if command -v kbuildsycoca6 >/dev/null 2>&1; then
            kbuildsycoca6 --noincremental >/dev/null 2>&1 || kbuildsycoca6 >/dev/null 2>&1 || true
        fi
    else
        echo "[BİLGİ] Sistem masaüstü dosyası bulunamadı (${sys_desktop}), .desktop override atlandı."
    fi

    # 2. Terminal CLI wrapper (~/.local/bin/antigravity)
    mkdir -p "${user_bin_dir}"
    if [[ -e "${user_bin}" ]] && ! grep -q "${MARKER}" "${user_bin}" 2>/dev/null; then
        echo "[UYARI] Mevcut ${user_bin} dosyamız bizim işaretçimizi taşımıyor, dokunulmadı." >&2
    else
        cat > "${user_bin}" <<'EOF'
#!/usr/bin/env bash
# managed-by: antigravity-desktop-live-quota-mcp
for arg in "$@"; do
    case "$arg" in
        --remote-debugging-port|--remote-debugging-port=*)
            exec /usr/bin/antigravity "$@"
            ;;
    esac
done
exec /usr/bin/antigravity --remote-debugging-port=0 "$@"
EOF
        chmod +x "${user_bin}"
        echo "[BAŞARILI] Terminal sarmalayıcısı hazır -> ${user_bin}"
    fi
}

echo "===================================================================="
echo "⚡ ${SERVER_KEY} Kurulumu Başlatılıyor..."
echo "===================================================================="

if [[ "${CDP_ONLY}" -eq 1 ]]; then
    setup_cdp_launcher
    echo "===================================================================="
    echo "✨ CDP launcher yapılandırması tamamlandı!"
    echo "Not: Çalışan Antigravity Desktop varsa değişikliklerin aktifleşmesi"
    echo "için uygulamayı bir kez tamamen kapatıp yeniden açın."
    echo "===================================================================="
    exit 0
fi

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

# 4. Antigravity >= 2.33.0 kalıcı CDP launcher kurulumu
if [[ "${NO_CDP_LAUNCHER}" -eq 0 ]]; then
    setup_cdp_launcher
fi

# 5. Hemen canlı pencereye enjeksiyon testi yap ve CDP durumunu denetle
echo "--------------------------------------------------------------------"
echo "🔍 Aktif Antigravity Desktop penceresine rozet enjeksiyonu deneniyor..."
python3 -B "${TARGET_MAIN}" --inject || true

PYTHONPATH="${SCRIPT_DIR}" python3 -B - <<'PYEOF'
from src.discovery import diagnose_cdp_status

diag = diagnose_cdp_status()
if not diag.get("cdp_available") and diag.get("reason") == "cdp_disabled_in_antigravity_2_33":
    print("")
    print("⚠️  ÖNEMLİ UYARI (Antigravity >= 2.33.0):")
    print("    Açık olan Antigravity Desktop penceresi --remote-debugging-port=0")
    print("    olmadan başlatıldığı için canlı rozet şu an enjekte edilemedi.")
    print("    Kalıcı launcher ayarı yapıldı; rozetin görünmesi için Antigravity")
    print("    Desktop uygulamasını bir kez tamamen kapatıp yeniden açın.")
PYEOF

echo "--------------------------------------------------------------------"
echo "✨ Kurulum tamamlandı!"
echo "Antigravity Desktop veya agy CLI her açıldığında bu MCP sunucusu"
echo "otomatik başlayacak ve canlı kota rozetini pencere üstüne takacaktır."
echo "===================================================================="
