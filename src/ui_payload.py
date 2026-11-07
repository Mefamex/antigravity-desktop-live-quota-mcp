"""
Tarayıcı İçi (DOM) Canlı Kota Rozeti Yükü (src/ui_payload.py)

Bu modül, Antigravity Desktop penceresine enjekte edilen izole JavaScript
kodunu üretir.

Özellikler:
1. Dinamik Kalan Süre Sayacı: Statik `/w` ve `/5h` yerine `resetTime` verisinden
   hesaplanan kalan süreyi gösterir (örn: `1:20h`, `3.5d`).
2. Aktif Model Vurgusu: DOM'daki seçili modeli okuyarak ilgili grubun (`⚡G`, `Ar`, `C`)
   etiketini parlak arka plan ve ışıltı ile öne çıkarır.
3. Kritik Eşik Nabız Uyarısı (Pulse Alert): Kota belirlenen eşiğin (`config.PULSE_ALERT_THRESHOLD_PCT`)
   altına düştüğünde rozet etrafında hafif kırmızı nabız animasyonu devreye girer.
4. Çift Katmanlı Çakışma Koruması (Idempotency): Eski zamanlayıcı ve gözlemcileri
   temizler, asla çift döngü veya bellek sızıntısı yapmaz.
"""

from __future__ import annotations

import config


def build_check_badge_js() -> str:
    """Rozetin DOM'da aktif olup olmadığını kontrol eden JS ifadesi."""
    return (
        f"Boolean(document.getElementById('{config.BADGE_ELEMENT_ID}') && "
        f"window.__AGY_QUOTA_STATE__ && window.__AGY_QUOTA_STATE__.active)"
    )


def build_injection_js() -> str:
    """
    Antigravity Desktop penceresine enjekte edilecek tam izole ve
    idempotent JavaScript kodunu döndürür.
    """
    enable_pulse_js = "true" if config.ENABLE_PULSE_ALERT else "false"

    return f"""
(() => {{
    const BADGE_ID = "{config.BADGE_ELEMENT_ID}";
    const STYLE_ID = "agy-quota-pulse-style";
    const BAR_SELECTOR = '{config.TARGET_BAR_SELECTOR}';
    const POLL_MS = {config.BROWSER_FETCH_INTERVAL_MS};
    const HIGH_PCT = {config.THRESHOLD_HIGH_PCT};
    const LOW_PCT = {config.THRESHOLD_LOW_PCT};
    const PULSE_THRESHOLD = {config.PULSE_ALERT_THRESHOLD_PCT};
    const ENABLE_PULSE = {enable_pulse_js};
    const COLOR_HIGH = "{config.COLOR_HIGH}";
    const COLOR_MED = "{config.COLOR_MEDIUM}";
    const COLOR_LOW = "{config.COLOR_LOW}";

    // Önceki bir örnek varsa zamanlayıcılarını ve gözlemcisini temizle (Idempotency)
    if (window.__AGY_QUOTA_STATE__) {{
        if (window.__AGY_QUOTA_STATE__.fetchTimerId) {{
            clearInterval(window.__AGY_QUOTA_STATE__.fetchTimerId);
        }}
        if (window.__AGY_QUOTA_STATE__.renderTimerId) {{
            clearInterval(window.__AGY_QUOTA_STATE__.renderTimerId);
        }}
        if (window.__AGY_QUOTA_STATE__.observer) {{
            window.__AGY_QUOTA_STATE__.observer.disconnect();
        }}
    }}

    const state = {{
        active: true,
        isRefreshing: false,
        fetchTimerId: null,
        renderTimerId: null,
        observer: null,
        lastQuota: null,
        installedAt: Date.now()
    }};
    window.__AGY_QUOTA_STATE__ = state;

    // CSS Nabız Animasyonunu (Keyframes) belgenin head etiketine bir kez ekle
    if (!document.getElementById(STYLE_ID)) {{
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            @keyframes agy-quota-pulse {{
                0%, 100% {{
                    box-shadow: 0 0 0 0 rgba(248, 113, 113, 0);
                    border-color: rgba(248, 113, 113, 0.35);
                }}
                50% {{
                    box-shadow: 0 0 8px 1px rgba(248, 113, 113, 0.5);
                    border-color: rgba(248, 113, 113, 0.85);
                }}
            }}
        `;
        document.head.appendChild(style);
    }}

    function pickColor(pct) {{
        if (pct > HIGH_PCT) return COLOR_HIGH;
        if (pct > LOW_PCT) return COLOR_MED;
        return COLOR_LOW;
    }}

    function formatTimeRemaining(resetTimeStr, windowType) {{
        if (!resetTimeStr) return windowType === "5h" ? "5h" : "w";
        try {{
            const resetDate = new Date(resetTimeStr);
            const diffMs = resetDate.getTime() - Date.now();
            if (diffMs <= 0) {{
                return windowType === "5h" ? "0m" : "0d";
            }}
            const diffMin = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMin / 60);

            if (windowType === "5h") {{
                const remMin = diffMin % 60;
                return `${{diffHours}}:${{remMin.toString().padStart(2, '0')}}h`;
            }} else {{
                const days = diffMs / 86400000;
                return `${{days.toFixed(1)}}d`;
            }}
        }} catch (_err) {{
            return windowType === "5h" ? "5h" : "w";
        }}
    }}

    function detectActiveModelGroup() {{
        try {{
            const btn = document.querySelector('button[aria-label*="Select model, current:"]');
            let label = btn ? (btn.getAttribute('aria-label') || btn.innerText || '') : '';
            if (!label) {{
                const anyBtn = Array.from(document.querySelectorAll('button')).find(b => {{
                    const t = (b.innerText || '').toLowerCase();
                    return t.includes('flash') || t.includes('pro') || t.includes('argon') || t.includes('claude') || t.includes('gpt');
                }});
                if (anyBtn) label = anyBtn.innerText;
            }}
            const lower = label.toLowerCase();
            if (lower.includes('argon')) return 'argon';
            if (lower.includes('claude') || lower.includes('gpt') || lower.includes('sonnet') || lower.includes('opus')) return 'claude';
            if (lower.includes('flash') || lower.includes('gemini') || lower.includes('pro')) return 'gemini';
        }} catch (_err) {{}}
        return '';
    }}

    async function fetchQuotaFromLocalServer(forceRefresh = false) {{
        try {{
            const token = window.__APP_CONFIG__?.csrfToken || "";
            const bodyStr = forceRefresh ? JSON.stringify({{ forceRefresh: true }}) : "{{}}";
            const resp = await fetch(
                "/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary",
                {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "X-Codeium-Csrf-Token": token
                    }},
                    body: bodyStr
                }}
            );
            if (!resp.ok) return null;
            const data = await resp.json();
            return data?.response || null;
        }} catch (_err) {{
            return null;
        }}
    }}

    function renderBadge(quota) {{
        const bar = document.querySelector(BAR_SELECTOR);
        if (!bar) return false;

        let badge = document.getElementById(BADGE_ID);
        if (!badge) {{
            badge = document.createElement("div");
            badge.id = BADGE_ID;
            badge.style.cssText = [
                "margin-left: 10px",
                "margin-right: auto",
                "display: inline-flex",
                "align-items: center",
                "gap: 8px",
                "font-size: 11px",
                "font-family: ui-sans-serif, system-ui, -apple-system, sans-serif",
                "padding: 2px 10px",
                "border-radius: 9999px",
                "background: rgba(255, 255, 255, 0.07)",
                "border: 1px solid rgba(255, 255, 255, 0.12)",
                "color: #d1d5db",
                "app-region: no-drag",
                "-webkit-app-region: no-drag",
                "cursor: pointer",
                "transition: background 0.15s ease, opacity 0.15s ease, border-color 0.2s ease",
                "user-select: none"
            ].join(";");

            badge.onmouseenter = () => {{
                badge.style.background = "rgba(255, 255, 255, 0.13)";
            }};
            badge.onmouseleave = () => {{
                badge.style.background = "rgba(255, 255, 255, 0.07)";
            }};
            badge.onclick = async () => {{
                if (state.isRefreshing) return;
                state.isRefreshing = true;
                badge.style.opacity = "0.5";
                badge.style.cursor = "wait";
                try {{
                    const fresh = await fetchQuotaFromLocalServer(true);
                    if (fresh) {{
                        state.lastQuota = fresh;
                        renderBadge(fresh);
                        badge.style.borderColor = "rgba(96, 165, 250, 0.8)";
                        setTimeout(() => {{
                            if (badge) badge.style.borderColor = "rgba(255, 255, 255, 0.12)";
                        }}, 350);
                    }}
                }} finally {{
                    badge.style.opacity = "1";
                    badge.style.cursor = "pointer";
                    state.isRefreshing = false;
                }}
            }};
            bar.appendChild(badge);
        }}

        if (!quota) {{
            badge.innerHTML = "<span>⚡ Kota: Bekleniyor...</span>";
            return true;
        }}

        let geminiWeekly = 100;
        let geminiWeeklyReset = "";
        let gemini5h = 100;
        let gemini5hReset = "";

        let argonWeekly = 100;
        let argonWeeklyReset = "";

        let claudeWeekly = 100;
        let claudeWeeklyReset = "";
        let claude5h = 100;
        let claude5hReset = "";

        let minPct = 100;
        const tooltipLines = ["Canlı Kota Durumu (Yenilemek için tıklayın):"];

        for (const g of quota.groups || []) {{
            const gName = g.displayName || "";
            for (const b of g.buckets || []) {{
                const pct = Math.round((b.remainingFraction ?? 1) * 100);
                if (pct < minPct) minPct = pct;

                if (gName.includes("Gemini") && !gName.includes("Argon")) {{
                    if (b.window === "weekly") {{
                        geminiWeekly = pct;
                        geminiWeeklyReset = b.resetTime || "";
                    }}
                    if (b.window === "5h") {{
                        gemini5h = pct;
                        gemini5hReset = b.resetTime || "";
                    }}
                }} else if (gName.includes("Argon")) {{
                    if (b.window === "weekly") {{
                        argonWeekly = pct;
                        argonWeeklyReset = b.resetTime || "";
                    }}
                }} else if (gName.includes("Claude") || gName.includes("GPT")) {{
                    if (b.window === "weekly") {{
                        claudeWeekly = pct;
                        claudeWeeklyReset = b.resetTime || "";
                    }}
                    if (b.window === "5h") {{
                        claude5h = pct;
                        claude5hReset = b.resetTime || "";
                    }}
                }}
                if (b.description) {{
                    tooltipLines.push(`• ${{gName}} (${{b.window}}): %${{pct}} — ${{b.description}}`);
                }}
            }}
        }}

        // Kritik kota nabız efekti kontrolü
        if (ENABLE_PULSE && minPct <= PULSE_THRESHOLD) {{
            badge.style.animation = "agy-quota-pulse 2s infinite ease-in-out";
        }} else {{
            badge.style.animation = "none";
            badge.style.borderColor = "rgba(255, 255, 255, 0.12)";
        }}

        // Kalan süre formatlamaları
        const gWeeklyTime = formatTimeRemaining(geminiWeeklyReset, "weekly");
        const g5hTime = formatTimeRemaining(gemini5hReset, "5h");
        const arWeeklyTime = formatTimeRemaining(argonWeeklyReset, "weekly");
        const cWeeklyTime = formatTimeRemaining(claudeWeeklyReset, "weekly");
        const c5hTime = formatTimeRemaining(claude5hReset, "5h");

        // Aktif model grubu tespiti ve görsel stil ayrımı
        const activeGroup = detectActiveModelGroup();
        tooltipLines.push(`\\nAktif Model Grubu: ${{activeGroup || "Bilinmiyor"}}`);

        const isGActive = activeGroup === 'gemini';
        const isArActive = activeGroup === 'argon';
        const isCActive = activeGroup === 'claude';

        const gLabelStyle = isGActive
            ? "color:#93c5fd; font-weight:700; background:rgba(96,165,250,0.2); padding:1px 4px; border-radius:4px; text-shadow:0 0 6px rgba(147,197,253,0.7);"
            : "color:#9ca3af; font-weight:500; opacity:0.8;";

        const arLabelStyle = isArActive
            ? "color:#7dd3fc; font-weight:700; background:rgba(56,189,248,0.2); padding:1px 4px; border-radius:4px; text-shadow:0 0 6px rgba(125,211,252,0.7);"
            : "color:#9ca3af; font-weight:500; opacity:0.8;";

        const cLabelStyle = isCActive
            ? "color:#d8b4fe; font-weight:700; background:rgba(192,132,252,0.2); padding:1px 4px; border-radius:4px; text-shadow:0 0 6px rgba(216,180,254,0.7);"
            : "color:#9ca3af; font-weight:500; opacity:0.8;";

        const timeTagStyle = "color:#e2e8f0; font-size:9.5px; font-weight:500; opacity:0.95;";

        badge.innerHTML = `
            <div style="display:flex; align-items:center; gap:3px;">
                <span style="${{gLabelStyle}}">⚡G:</span>
                <span style="color:${{pickColor(geminiWeekly)}}; font-weight:600;">%${{geminiWeekly}}</span><span style="${{timeTagStyle}}">${{gWeeklyTime}}</span>
                <span style="color:#6b7280; font-size:10px;">/</span>
                <span style="color:${{pickColor(gemini5h)}}; font-weight:600;">%${{gemini5h}}</span><span style="${{timeTagStyle}}">${{g5hTime}}</span>
            </div>
            <span style="color:#6b7280;">|</span>
            <div style="display:flex; align-items:center; gap:3px;">
                <span style="${{arLabelStyle}}">Ar:</span>
                <span style="color:${{pickColor(argonWeekly)}}; font-weight:600;">%${{argonWeekly}}</span><span style="${{timeTagStyle}}">${{arWeeklyTime}}</span>
            </div>
            <span style="color:#6b7280;">|</span>
            <div style="display:flex; align-items:center; gap:3px;">
                <span style="${{cLabelStyle}}">C:</span>
                <span style="color:${{pickColor(claudeWeekly)}}; font-weight:600;">%${{claudeWeekly}}</span><span style="${{timeTagStyle}}">${{cWeeklyTime}}</span>
                <span style="color:#6b7280; font-size:10px;">/</span>
                <span style="color:${{pickColor(claude5h)}}; font-weight:600;">%${{claude5h}}</span><span style="${{timeTagStyle}}">${{c5hTime}}</span>
            </div>
        `;
        badge.title = tooltipLines.join("\\n");
        return true;
    }}

    async function updateCycle() {{
        const q = await fetchQuotaFromLocalServer();
        if (q) {{
            state.lastQuota = q;
        }}
        renderBadge(state.lastQuota);
    }}

    // React DOM değişimlerinde rozet silinirse veya model değişirse anında güncelle
    const observer = new MutationObserver(() => {{
        if (!document.getElementById(BADGE_ID) && document.querySelector(BAR_SELECTOR)) {{
            renderBadge(state.lastQuota);
        }}
    }});
    observer.observe(document.body, {{ childList: true, subtree: true }});
    state.observer = observer;

    // İlk yükleme ve periyodik döngüler
    updateCycle();
    // 1. Ağ üzerinden kota çekme döngüsü (varsayılan: 30 sn)
    state.fetchTimerId = setInterval(updateCycle, POLL_MS);
    // 2. Kalan süre geri sayımı ve aktif model kontrolü için hafif yerel render döngüsü (5 sn)
    state.renderTimerId = setInterval(() => {{
        if (state.lastQuota) {{
            renderBadge(state.lastQuota);
        }}
    }}, 5000);

    return "OK";
}})()
"""
