"""
In-Browser (DOM) Live Quota Badge Payload (src/ui_payload.py)

This module generates the isolated JavaScript code injected into the
Antigravity Desktop window.

Features:
1. Dynamic Time Remaining Counter: Displays remaining time computed from
   `resetTime` instead of static `/w` and `/5h` labels (e.g., `1:20h`, `3.5d`).
2. Active Model Highlight: Reads the currently selected model in the DOM and
   highlights the corresponding group tag (`⚡G`, `Ar`, `C`) with a bright background and glow.
3. Critical Threshold Pulse Alert: Activates a subtle red pulse animation around
   the badge when quota drops below the threshold (`config.PULSE_ALERT_THRESHOLD_PCT`).
4. Double-Layer Collision Guard (Idempotency): Cleans up previous timers and
   observers to prevent duplicate loops or memory leaks.
"""

from __future__ import annotations

import config


def build_check_badge_js() -> str:
    """Returns the JS expression checking whether the badge is active in the DOM."""
    return (
        f"Boolean(document.getElementById('{config.BADGE_ELEMENT_ID}') && "
        f"window.__AGY_QUOTA_STATE__ && window.__AGY_QUOTA_STATE__.active)"
    )


def build_injection_js() -> str:
    """
    Returns fully isolated and idempotent JavaScript code to be injected into
    the Antigravity Desktop window.
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

    // Clean up timers and observer from any previous instance (Idempotency)
    const prevHistory = window.__AGY_QUOTA_STATE__?.history;
    const history = {{ g5h: [], c5h: [] }};
    if (Array.isArray(prevHistory)) {{
        history.g5h = prevHistory
            .filter(e => e && typeof e.t === "number" && typeof e.g5h === "number")
            .map(e => ({{ t: e.t, pct: e.g5h }}))
            .slice(-30);
        history.c5h = prevHistory
            .filter(e => e && typeof e.t === "number" && typeof e.c5h === "number")
            .map(e => ({{ t: e.t, pct: e.c5h }}))
            .slice(-30);
    }} else if (prevHistory && typeof prevHistory === "object") {{
        if (Array.isArray(prevHistory.g5h)) {{
            history.g5h = prevHistory.g5h
                .filter(e => e && typeof e.t === "number" && typeof e.pct === "number")
                .slice(-30);
        }}
        if (Array.isArray(prevHistory.c5h)) {{
            history.c5h = prevHistory.c5h
                .filter(e => e && typeof e.t === "number" && typeof e.pct === "number")
                .slice(-30);
        }}
    }}
    const prevInstalledAt = window.__AGY_QUOTA_STATE__?.installedAt || Date.now();
    if (window.__AGY_QUOTA_STATE__) {{
        if (window.__AGY_QUOTA_STATE__.fetchTimerId) {{
            clearInterval(window.__AGY_QUOTA_STATE__.fetchTimerId);
        }}
        if (window.__AGY_QUOTA_STATE__.renderTimerId) {{
            clearInterval(window.__AGY_QUOTA_STATE__.renderTimerId);
        }}
        if (window.__AGY_QUOTA_STATE__.reattachFrameId !== null && window.__AGY_QUOTA_STATE__.reattachFrameId !== undefined) {{
            cancelAnimationFrame(window.__AGY_QUOTA_STATE__.reattachFrameId);
        }}
        if (window.__AGY_QUOTA_STATE__.observer) {{
            window.__AGY_QUOTA_STATE__.observer.disconnect();
        }}
    }}

    const state = {{
        active: true,
        isRefreshing: false,
        fetchSeq: 0,
        lastAppliedSeq: 0,
        fetchTimerId: null,
        renderTimerId: null,
        reattachFrameId: null,
        observer: null,
        lastQuota: null,
        installedAt: prevInstalledAt,
        history: history
    }};
    window.__AGY_QUOTA_STATE__ = state;

    // Append CSS pulse animation (Keyframes) to document head once
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

    function calculateBurnRate(key, currentPct) {{
        const arr = state.history?.[key];
        if (!arr || arr.length < 2) return null;
        const oldest = arr[0];
        const newest = arr[arr.length - 1];
        const timeDiffMin = (newest.t - oldest.t) / 60000;
        if (timeDiffMin < 0.3) return null;

        const drop = oldest.pct - currentPct;
        if (drop <= 0) {{
            return {{ ratePerHour: 0, etaMinutes: null, text: "Stable (no depletion)" }};
        }}

        const ratePerHour = (drop / timeDiffMin) * 60;
        const etaMinutes = ratePerHour > 0 ? Math.round((currentPct / ratePerHour) * 60) : null;
        let etaText = "";
        if (etaMinutes !== null) {{
            if (etaMinutes >= 60) {{
                const h = Math.floor(etaMinutes / 60);
                const m = etaMinutes % 60;
                etaText = `~${{h}}h ${{m}}m`;
            }} else {{
                etaText = `~${{etaMinutes}}m`;
            }}
        }}
        const roundedRate = Math.round(ratePerHour * 10) / 10;
        return {{
            ratePerHour: roundedRate,
            etaMinutes: etaMinutes,
            text: `🔥 ~${{roundedRate}}%/hr (Est. depletion: ${{etaText}})`
        }};
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

    function mapGroupDisplayName(displayName) {{
        const gLower = String(displayName || '').toLowerCase();
        if (gLower.includes('argon')) return 'argon';
        if (gLower.includes('claude') || gLower.includes('gpt')) return 'claude';
        if (gLower.includes('gemini')) return 'gemini';
        return '';
    }}

    function normalizeModelLabel(rawLabel) {{
        let normalized = String(rawLabel || '')
            .replace(/\\s+/g, ' ')
            .trim()
            .replace(/^select model,\\s*current:\\s*/i, '')
            .trim();
        const effortRe = /(?:\\s*\\((?:low|medium|high|minimal)\\)|\\s+(?:low|medium|high|minimal))\\s*$/i;
        while (effortRe.test(normalized)) {{
            normalized = normalized.replace(effortRe, '').trim();
        }}
        return normalized.replace(/^(?:low|medium|high|minimal)$/i, '').trim().toLowerCase();
    }}

    function detectActiveModelGroup(quota) {{
        try {{
            const descCandidates = [];
            const nameCandidates = [];
            for (const g of quota?.groups || []) {{
                const groupKey = mapGroupDisplayName(g.displayName);
                if (!groupKey) continue;
                const gNameNorm = String(g.displayName || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                if (gNameNorm && gNameNorm.length <= 50) {{
                    nameCandidates.push({{ text: gNameNorm, group: groupKey }});
                }}
                const desc = String(g.description || '').trim();
                if (desc.includes(':')) {{
                    const listPart = desc.slice(desc.indexOf(':') + 1);
                    for (const chunk of listPart.split(',')) {{
                        const entry = chunk.replace(/\\s+/g, ' ').trim().toLowerCase();
                        if (entry && entry.length <= 50) {{
                            descCandidates.push({{ text: entry, group: groupKey }});
                        }}
                    }}
                }}
            }}
            descCandidates.sort((a, b) => b.text.length - a.text.length);
            nameCandidates.sort((a, b) => b.text.length - a.text.length);

            const btn = document.querySelector(
                'button[data-testid="model-selector-trigger"], button[aria-label*="Select model, current:"]'
            );
            let label = btn ? (btn.getAttribute('aria-label') || btn.innerText || '') : '';
            if (btn && !normalizeModelLabel(label) && btn.innerText) {{
                label = btn.innerText;
            }}
            if (!label) {{
                const buttons = Array.from(document.querySelectorAll('button'));
                const dynBtn = descCandidates.length > 0
                    ? buttons.find(b => {{
                        const t = (b.innerText || '').toLowerCase();
                        return descCandidates.some(c => t.includes(c.text));
                    }})
                    : null;
                const anyBtn = dynBtn || buttons.find(b => {{
                    const t = (b.innerText || '').toLowerCase();
                    return (
                        t.includes('neon') ||
                        t.includes('hydrogen') ||
                        t.includes('orchestrator') ||
                        t.includes('flash') ||
                        t.includes('pro') ||
                        t.includes('argon') ||
                        t.includes('claude') ||
                        t.includes('gpt') ||
                        t.includes('sonnet') ||
                        t.includes('opus')
                    );
                }});
                if (anyBtn) label = anyBtn.innerText || '';
            }}

            const lower = normalizeModelLabel(label);
            if (!lower) return '';

            for (const c of descCandidates) {{
                if (lower === c.text) return c.group;
            }}
            for (const c of nameCandidates) {{
                if (lower === c.text) return c.group;
            }}

            const allCandidates = descCandidates.concat(nameCandidates).sort((a, b) => b.text.length - a.text.length);
            for (const c of allCandidates) {{
                if (lower.includes(c.text)) return c.group;
            }}

            if (lower.length >= 3) {{
                for (const c of descCandidates) {{
                    if (c.text.includes(lower)) return c.group;
                }}
            }}

            if (lower.includes('argon')) return 'argon';
            if (lower.includes('claude') || lower.includes('gpt') || lower.includes('sonnet') || lower.includes('opus')) return 'claude';
            if (lower.includes('flash') || lower.includes('gemini') || lower.includes('pro') || lower.includes('neon') || lower.includes('hydrogen') || lower.includes('orchestrator')) return 'gemini';
        }} catch (_err) {{}}
        return '';
    }}

    function applyQuotaResponse(data, seq) {{
        if (!data || seq < state.lastAppliedSeq) return false;
        state.lastAppliedSeq = seq;
        state.lastQuota = data;
        let curG5h = null;
        let curC5h = null;
        let hasG5h = false;
        let hasC5h = false;
        for (const g of data.groups || []) {{
            const gKey = mapGroupDisplayName(g.displayName);
            for (const b of g.buckets || []) {{
                if (b.window === "5h") {{
                    const pct = Math.round((b.remainingFraction ?? 1) * 100);
                    if (gKey === "gemini") {{
                        curG5h = pct;
                        hasG5h = true;
                    }} else if (gKey === "claude") {{
                        curC5h = pct;
                        hasC5h = true;
                    }}
                }}
            }}
        }}
        const now = Date.now();
        function recordHistory(key, pct) {{
            const arr = state.history[key] || (state.history[key] = []);
            const prev = arr.length > 0 ? arr[arr.length - 1] : null;
            if (prev && pct > prev.pct + 5) {{
                state.history[key] = [{{ t: now, pct }}];
            }} else {{
                arr.push({{ t: now, pct }});
                if (arr.length > 30) arr.shift();
            }}
        }}
        if (hasG5h) recordHistory("g5h", curG5h);
        if (hasC5h) recordHistory("c5h", curC5h);
        return true;
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
                "margin-left: clamp(6px, 1vw, 12px)",
                "margin-right: auto",
                "display: inline-flex",
                "align-items: center",
                "gap: clamp(6px, 0.8vw, 9px)",
                "white-space: nowrap",
                "flex-shrink: 0",
                "font-size: 11px",
                "font-family: inherit, ui-sans-serif, system-ui, -apple-system, sans-serif",
                "padding: 2.5px clamp(8px, 1vw, 12px)",
                "border-radius: 9999px",
                "background: rgba(255, 255, 255, 0.07)",
                "border: 1px solid rgba(255, 255, 255, 0.12)",
                "color: #d1d5db",
                "line-height: 1.2",
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
                const seq = ++state.fetchSeq;
                try {{
                    const fresh = await fetchQuotaFromLocalServer(true);
                    if (applyQuotaResponse(fresh, seq)) {{
                        if (state.fetchTimerId) {{
                            clearInterval(state.fetchTimerId);
                        }}
                        state.fetchTimerId = setInterval(updateCycle, POLL_MS);
                        renderBadge(state.lastQuota);
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
            badge.innerHTML = "<span>⚡ Quota: Loading...</span>";
            return true;
        }}

        let geminiWeekly = 100;
        let geminiWeeklyReset = "";
        let gemini5h = 100;
        let gemini5hReset = "";
        let hasGeminiWeekly = false;
        let hasGemini5h = false;

        let argonWeekly = 100;
        let argonWeeklyReset = "";
        let hasArgon = false;

        let claudeWeekly = 100;
        let claudeWeeklyReset = "";
        let claude5h = 100;
        let claude5hReset = "";
        let hasClaudeWeekly = false;
        let hasClaude5h = false;

        let minPct = 100;
        const tooltipLines = ["Live Quota Status (Click to refresh):"];

        for (const g of quota.groups || []) {{
            const gName = g.displayName || "";
            const gKey = mapGroupDisplayName(gName);
            for (const b of g.buckets || []) {{
                const pct = Math.round((b.remainingFraction ?? 1) * 100);
                if (pct < minPct) minPct = pct;

                if (gKey === "gemini") {{
                    if (b.window === "weekly") {{
                        geminiWeekly = pct;
                        geminiWeeklyReset = b.resetTime || "";
                        hasGeminiWeekly = true;
                    }}
                    if (b.window === "5h") {{
                        gemini5h = pct;
                        gemini5hReset = b.resetTime || "";
                        hasGemini5h = true;
                    }}
                }} else if (gKey === "argon") {{
                    if (b.window === "weekly") {{
                        argonWeekly = pct;
                        argonWeeklyReset = b.resetTime || "";
                        hasArgon = true;
                    }}
                }} else if (gKey === "claude") {{
                    if (b.window === "weekly") {{
                        claudeWeekly = pct;
                        claudeWeeklyReset = b.resetTime || "";
                        hasClaudeWeekly = true;
                    }}
                    if (b.window === "5h") {{
                        claude5h = pct;
                        claude5hReset = b.resetTime || "";
                        hasClaude5h = true;
                    }}
                }}
                if (b.description) {{
                    tooltipLines.push(`• ${{gName}} (${{b.window}}): ${{pct}}% — ${{b.description}}`);
                }}
            }}
        }}

        const hasGemini = hasGeminiWeekly || hasGemini5h;
        const hasClaude = hasClaudeWeekly || hasClaude5h;

        // Check critical quota pulse effect
        if (ENABLE_PULSE && minPct <= PULSE_THRESHOLD) {{
            badge.style.animation = "agy-quota-pulse 2s infinite ease-in-out";
        }} else {{
            badge.style.animation = "none";
            badge.style.borderColor = "rgba(255, 255, 255, 0.12)";
        }}

        // Remaining time formatting
        const gWeeklyTime = formatTimeRemaining(geminiWeeklyReset, "weekly");
        const g5hTime = formatTimeRemaining(gemini5hReset, "5h");
        const arWeeklyTime = formatTimeRemaining(argonWeeklyReset, "weekly");
        const cWeeklyTime = formatTimeRemaining(claudeWeeklyReset, "weekly");
        const c5hTime = formatTimeRemaining(claude5hReset, "5h");

        // Active model group detection and visual style differentiation
        const activeGroup = detectActiveModelGroup(quota);
        tooltipLines.push(`\\nActive Model Group: ${{activeGroup || "Unknown"}}`);

        const gBurn = hasGemini5h ? calculateBurnRate("g5h", gemini5h) : null;
        const cBurn = hasClaude5h ? calculateBurnRate("c5h", claude5h) : null;
        if (gBurn) {{
            tooltipLines.push(`• Gemini (5h) Burn Rate: ${{gBurn.text}}`);
        }}
        if (cBurn) {{
            tooltipLines.push(`• Claude/GPT (5h) Burn Rate: ${{cBurn.text}}`);
        }}

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

        const timeTagStyle = "color:#e2e8f0; font-size:9.5px; font-weight:500; opacity:0.95; margin-left:1px;";

        function renderPct(val) {{
            return `<span style="color:${{pickColor(val)}}; font-weight:700; font-size:12px; letter-spacing:-0.2px;">${{val}}%</span>`;
        }}

        const segments = [];
        if (hasGemini) {{
            const gParts = [];
            if (hasGeminiWeekly) gParts.push(`${{renderPct(geminiWeekly)}}<span style="${{timeTagStyle}}">${{gWeeklyTime}}</span>`);
            if (hasGemini5h) gParts.push(`${{renderPct(gemini5h)}}<span style="${{timeTagStyle}}">${{g5hTime}}</span>`);
            segments.push(`
                <div style="display:flex; align-items:center; gap:3px;">
                    <span style="${{gLabelStyle}}">⚡G:</span>
                    ${{gParts.join('<span style="color:#6b7280; font-size:10px; margin:0 1px;">/</span>')}}
                </div>
            `);
        }}
        if (hasArgon) {{
            segments.push(`
                <div style="display:flex; align-items:center; gap:3px;">
                    <span style="${{arLabelStyle}}">Ar:</span>
                    ${{renderPct(argonWeekly)}}<span style="${{timeTagStyle}}">${{arWeeklyTime}}</span>
                </div>
            `);
        }}
        if (hasClaude) {{
            const cParts = [];
            if (hasClaudeWeekly) cParts.push(`${{renderPct(claudeWeekly)}}<span style="${{timeTagStyle}}">${{cWeeklyTime}}</span>`);
            if (hasClaude5h) cParts.push(`${{renderPct(claude5h)}}<span style="${{timeTagStyle}}">${{c5hTime}}</span>`);
            segments.push(`
                <div style="display:flex; align-items:center; gap:3px;">
                    <span style="${{cLabelStyle}}">C:</span>
                    ${{cParts.join('<span style="color:#6b7280; font-size:10px; margin:0 1px;">/</span>')}}
                </div>
            `);
        }}

        badge.innerHTML = segments.length > 0
            ? segments.join('<span style="color:#6b7280; margin:0 1px;">|</span>')
            : "<span>⚡ Quota: No Data</span>";
        badge.title = tooltipLines.join("\\n");
        return true;
    }}

    async function updateCycle() {{
        if (state.isRefreshing) return;
        const seq = ++state.fetchSeq;
        const q = await fetchQuotaFromLocalServer(true);
        if (q) {{
            applyQuotaResponse(q, seq);
        }}
        renderBadge(state.lastQuota);
    }}

    // Reattach badge on the next animation frame if removed by React DOM mutations
    const observer = new MutationObserver(() => {{
        if (state.reattachFrameId !== null) return;
        state.reattachFrameId = requestAnimationFrame(() => {{
            state.reattachFrameId = null;
            if (!document.getElementById(BADGE_ID) && document.querySelector(BAR_SELECTOR)) {{
                renderBadge(state.lastQuota);
            }}
        }});
    }});
    observer.observe(document.body, {{ childList: true, subtree: true }});
    state.observer = observer;

    // Initial load and periodic loops
    updateCycle();
    // 1. Network quota fetch loop (interval: POLL_MS)
    state.fetchTimerId = setInterval(updateCycle, POLL_MS);
    // 2. Lightweight local render loop for countdown and active model check (5s)
    state.renderTimerId = setInterval(() => {{
        if (state.lastQuota) {{
            renderBadge(state.lastQuota);
        }}
    }}, 5000);

    return "OK";
}})()
"""
