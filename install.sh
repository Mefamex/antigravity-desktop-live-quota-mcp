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

resolve_system_antigravity_bin() {
    local user_bin_dir="${1:-${HOME}/.local/bin}"
    user_bin_dir="${user_bin_dir%/}"
    local user_bin="${user_bin_dir}/antigravity"
    local user_bin_dir_canon user_bin_canon
    user_bin_dir_canon="$(readlink -m "${user_bin_dir}" 2>/dev/null || readlink -f "${user_bin_dir}" 2>/dev/null || printf '%s' "${user_bin_dir}")"
    user_bin_canon="$(readlink -m "${user_bin}" 2>/dev/null || readlink -f "${user_bin}" 2>/dev/null || printf '%s' "${user_bin}")"

    local -a candidates=()
    local -a path_dirs=()
    local dir dir_canon cand cand_canon header

    IFS=':' read -ra path_dirs <<< "${PATH:-}"
    if [[ ${#path_dirs[@]} -gt 0 ]]; then
        for dir in "${path_dirs[@]}"; do
            [[ -n "${dir}" ]] || continue
            dir="${dir%/}"
            [[ -n "${dir}" ]] || dir="/"
            if [[ "${dir}" == "${user_bin_dir}" ]]; then
                continue
            fi
            dir_canon="$(readlink -m "${dir}" 2>/dev/null || readlink -f "${dir}" 2>/dev/null || printf '%s' "${dir}")"
            if [[ "${dir_canon}" == "${user_bin_dir_canon}" ]]; then
                continue
            fi
            candidates+=("${dir%/}/antigravity")
        done
    fi

    candidates+=(
        "/usr/bin/antigravity"
        "/usr/local/bin/antigravity"
        "/opt/Antigravity/antigravity"
    )

    for cand in "${candidates[@]}"; do
        [[ -f "${cand}" && -x "${cand}" ]] || continue
        if [[ "${cand}" == "${user_bin}" ]]; then
            continue
        fi
        cand_canon="$(readlink -m "${cand}" 2>/dev/null || readlink -f "${cand}" 2>/dev/null || printf '%s' "${cand}")"
        if [[ "${cand_canon}" == "${user_bin_canon}" ]]; then
            continue
        fi
        header="$({ head -c 1024 "${cand}" | tr -d '\0'; } 2>/dev/null || true)"
        if [[ "${header}" == *"${MARKER}"* ]]; then
            continue
        fi
        printf '%s\n' "${cand}"
        return 0
    done

    return 1
}

setup_cdp_launcher() {
    echo "--------------------------------------------------------------------"
    echo "🔧 Antigravity Desktop (>= 2.33.0) kalıcı CDP launcher ayarlanıyor (sudo gerekmez)..."

    local sys_desktop="/usr/share/applications/antigravity.desktop"
    local user_app_dir="${HOME}/.local/share/applications"
    local user_desktop="${user_app_dir}/antigravity.desktop"
    local user_bin_dir="${HOME}/.local/bin"
    local user_bin="${user_bin_dir}/antigravity"
    local real_bin=""
    if ! real_bin="$(resolve_system_antigravity_bin "${user_bin_dir}")"; then
        real_bin=""
    fi

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
        # Tırnaklı veya tırnaksız komut token'ı sonrası --remote-debugging-port=0 ekle
        line = re.sub(
            r'^Exec=\s*("[^"]+"|\S+)',
            r"Exec=\1 --remote-debugging-port=0",
            line,
            count=1,
        )
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
    local user_bin_header=""
    local user_bin_managed=0
    if [[ -e "${user_bin}" || -L "${user_bin}" ]]; then
        user_bin_header="$({ head -c 1024 "${user_bin}" | tr -d '\0'; } 2>/dev/null || true)"
        if [[ "${user_bin_header}" == *"${MARKER}"* ]]; then
            user_bin_managed=1
        fi
    fi

    if [[ ( -e "${user_bin}" || -L "${user_bin}" ) && "${user_bin_managed}" -eq 0 ]]; then
        echo "[UYARI] Mevcut ${user_bin} dosyamız bizim işaretçimizi taşımıyor, dokunulmadı." >&2
    elif [[ -z "${real_bin}" ]]; then
        echo "[UYARI] Sistem genelinde çalıştırılabilir Antigravity ikili dosyası bulunamadı; ${user_bin} sarmalayıcısı oluşturulmadı." >&2
    else
        mkdir -p "${user_bin_dir}"
        local quoted_real_bin
        quoted_real_bin="$(printf '%q' "${real_bin}")"
        cat > "${user_bin}" <<EOF
#!/usr/bin/env bash
# ${MARKER}
for arg in "\$@"; do
    case "\$arg" in
        --remote-debugging-port|--remote-debugging-port=*)
            exec ${quoted_real_bin} "\$@"
            ;;
    esac
done
exec ${quoted_real_bin} --remote-debugging-port=0 "\$@"
EOF
        chmod +x "${user_bin}"
        echo "[BAŞARILI] Terminal sarmalayıcısı hazır -> ${user_bin} (hedef: ${real_bin})"
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
