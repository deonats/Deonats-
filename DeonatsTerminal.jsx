import { useState, useEffect, useRef, useCallback } from "react";

// ─── i18n ─────────────────────────────────────────────────────────────────────
const T = {
  ru: {
    placeholder: "введите команду...",
    boot: "DEONATS v1.0.0 — ЯДРО ЗАПУЩЕНО",
    hint: "введите 'help' для списка команд",
    authPrompt: "ТРЕБУЕТСЯ MASTER PASSWORD",
    commands: {
      help: "Список команд",
      add: "add [сумма] [тип] [категория] — добавить транзакцию",
      status: "check-status — статус ядра и лимиты",
      goal_add: "goal-add [название] [сумма] [YYYY-MM-DD] — создать цель",
      goal_status: "goal-status — список целей",
      repay: "repay-debt [id] [сумма] — погасить долг",
      clear: "clear — очистить терминал",
      theme: "theme [dark|light] — переключить тему",
      lang: "lang [ru|en] — сменить язык",
    },
  },
  en: {
    placeholder: "enter command...",
    boot: "DEONATS v1.0.0 — KERNEL RUNNING",
    hint: "type 'help' for command list",
    authPrompt: "MASTER PASSWORD REQUIRED",
    commands: {
      help: "Command list",
      add: "add [amount] [type] [category] — add transaction",
      status: "check-status — kernel status & limits",
      goal_add: "goal-add [name] [amount] [YYYY-MM-DD] — create goal",
      goal_status: "goal-status — list goals",
      repay: "repay-debt [id] [amount] — repay debt",
      clear: "clear — clear terminal",
      theme: "theme [dark|light] — switch theme",
      lang: "lang [ru|en] — switch language",
    },
  },
};

// ─── Mock API (demo mode — replace with real fetch) ───────────────────────────
const API_BASE = "http://localhost:8000/api/v1";

async function apiCall(path, method = "GET", body = null) {
  try {
    const opts = {
      method,
      headers: { "Content-Type": "application/json" },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    return await res.json();
  } catch {
    return { error: true, message: "KERNEL: CONNECTION LOST — OFFLINE MODE" };
  }
}

// ─── ProgressBar ─────────────────────────────────────────────────────────────
function ProgressBar({ label, value, max = 100, unit = "%", warn = 80, danger = 100, blocked = false }) {
  const pct = Math.min((value / max) * 100, 100);
  const color = blocked
    ? "var(--color-panic)"
    : pct >= danger
    ? "var(--color-panic)"
    : pct >= warn
    ? "var(--color-warn)"
    : "var(--color-gold)";

  return (
    <div style={{ marginBottom: "8px", fontFamily: "var(--font-mono)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--color-dim)", marginBottom: "3px" }}>
        <span>{label}</span>
        <span style={{ color }}>
          {blocked ? "■ BLOCKED" : `${value.toFixed(0)}${unit} / ${max}${unit}`}
        </span>
      </div>
      <div style={{ height: "8px", background: "var(--color-track)", position: "relative" }}>
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            height: "100%",
            width: `${pct}%`,
            background: color,
            transition: "width 0.4s ease",
          }}
        />
        {/* CPU-style tick marks */}
        {[25, 50, 75].map((tick) => (
          <div
            key={tick}
            style={{
              position: "absolute",
              left: `${tick}%`,
              top: 0,
              width: "1px",
              height: "100%",
              background: "rgba(255,255,255,0.1)",
            }}
          />
        ))}
      </div>
    </div>
  );
}

// ─── LogLine ──────────────────────────────────────────────────────────────────
function LogLine({ type = "output", children, ts }) {
  const colors = {
    input: "var(--color-gold)",
    output: "var(--color-fg)",
    error: "var(--color-panic)",
    warn: "var(--color-warn)",
    success: "var(--color-ok)",
    system: "var(--color-dim)",
    panic: "#FF2020",
  };
  const prefixes = {
    input: "► ",
    output: "  ",
    error: "✖ ",
    warn: "⚠ ",
    success: "✔ ",
    system: "§ ",
    panic: "!!! ",
  };

  return (
    <div
      style={{
        display: "flex",
        gap: "8px",
        color: colors[type] || colors.output,
        fontSize: "13px",
        lineHeight: "1.6",
        fontFamily: "var(--font-mono)",
        padding: "1px 0",
      }}
    >
      {ts && (
        <span style={{ color: "var(--color-dim)", fontSize: "11px", minWidth: "60px", opacity: 0.6 }}>
          {ts}
        </span>
      )}
      <span style={{ opacity: 0.5 }}>{prefixes[type]}</span>
      <span style={{ flex: 1, wordBreak: "break-word" }}>{children}</span>
    </div>
  );
}

// ─── StatusPanel ──────────────────────────────────────────────────────────────
function StatusPanel({ status }) {
  if (!status) return null;
  const { categories = [], kernel_panic, panic_count } = status;

  return (
    <div
      style={{
        border: `1px solid ${kernel_panic ? "var(--color-panic)" : "var(--color-border)"}`,
        padding: "12px 16px",
        marginTop: "8px",
        marginBottom: "8px",
        background: "var(--color-surface)",
      }}
    >
      <div
        style={{
          fontSize: "11px",
          color: kernel_panic ? "var(--color-panic)" : "var(--color-gold)",
          fontFamily: "var(--font-mono)",
          marginBottom: "10px",
          letterSpacing: "2px",
        }}
      >
        {kernel_panic ? `⚡ KERNEL PANIC — ${panic_count} CATEGORIES LOCKED` : "■ KERNEL STATUS — ALL SYSTEMS"}
      </div>
      {categories.map((cat) => (
        <ProgressBar
          key={cat.category}
          label={cat.category.toUpperCase()}
          value={cat.spent}
          max={cat.limit}
          unit=""
          warn={80}
          danger={100}
          blocked={cat.blocked}
        />
      ))}
    </div>
  );
}

// ─── GoalsPanel ───────────────────────────────────────────────────────────────
function GoalsPanel({ goals }) {
  if (!goals?.length) return null;
  return (
    <div style={{ border: "1px solid var(--color-border)", padding: "12px 16px", marginTop: "8px", background: "var(--color-surface)" }}>
      <div style={{ fontSize: "11px", color: "var(--color-gold)", fontFamily: "var(--font-mono)", marginBottom: "10px", letterSpacing: "2px" }}>
        ◈ GOAL TRACKING SYSTEM
      </div>
      {goals.map((g) => (
        <div key={g.id} style={{ marginBottom: "10px" }}>
          <ProgressBar
            label={`[${g.status.toUpperCase()}] ${g.name.toUpperCase()}`}
            value={g.current_amount}
            max={g.target_amount}
            unit=""
            warn={60}
            danger={99}
            blocked={g.status === "violated"}
          />
          {g.penalty_applied && (
            <div style={{ fontSize: "11px", color: "var(--color-panic)", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
              ⚠ PENALTY: -{g.penalty_amount.toFixed(2)} (INTEGRITY VIOLATION)
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Main Terminal ─────────────────────────────────────────────────────────────
export default function DeonatsTerminal() {
  const [theme, setTheme] = useState("dark");
  const [lang, setLang] = useState("ru");
  const [logs, setLogs] = useState([]);
  const [input, setInput] = useState("");
  const [history, setHistory] = useState([]);
  const [histIdx, setHistIdx] = useState(-1);
  const [authenticated, setAuthenticated] = useState(false);
  const [userId, setUserId] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [goalsData, setGoalsData] = useState(null);
  const [bootDone, setBootDone] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  const t = T[lang];

  // ─── CSS vars by theme ─────────────────────────────────────────────────────
  const themes = {
    dark: {
      "--bg": "#0A0A0A",
      "--fg": "#D4D4D4",
      "--color-fg": "#D4D4D4",
      "--color-gold": "#C9A84C",
      "--color-panic": "#FF3333",
      "--color-warn": "#FF9900",
      "--color-ok": "#33FF99",
      "--color-dim": "#555555",
      "--color-border": "#2A2A2A",
      "--color-surface": "#111111",
      "--color-track": "#1E1E1E",
      "--color-input-bg": "#0F0F0F",
      "--font-mono": "'Courier New', 'Lucida Console', monospace",
    },
    light: {
      "--bg": "#E5E5E5",
      "--fg": "#1A1A1A",
      "--color-fg": "#1A1A1A",
      "--color-gold": "#8B6914",
      "--color-panic": "#CC0000",
      "--color-warn": "#CC7700",
      "--color-ok": "#006633",
      "--color-dim": "#888888",
      "--color-border": "#AAAAAA",
      "--color-surface": "#D8D8D8",
      "--color-track": "#BBBBBB",
      "--color-input-bg": "#DADADA",
      "--font-mono": "'Courier New', 'Lucida Console', monospace",
    },
  };

  const cssVars = themes[theme];

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, statusData, goalsData]);

  // ─── Boot sequence ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (bootDone) return;
    const bootLines = [
      { type: "system", text: "██████████████████████████████████████████" },
      { type: "system", text: "  DEONATS FINANCIAL OS v1.0.0" },
      { type: "system", text: "  INDUSTRIAL BRUTALISM KERNEL" },
      { type: "system", text: "██████████████████████████████████████████" },
      { type: "system", text: "" },
      { type: "output", text: t.boot },
      { type: "system", text: "LOADING MODULES: [TRANSACTIONS] [GOALS] [PENALTY_ENGINE] [KERNEL_PANIC]" },
      { type: "success", text: "ALL MODULES LOADED — OK" },
      { type: "system", text: "" },
      { type: "warn", text: t.hint },
    ];
    let delay = 0;
    bootLines.forEach((line, i) => {
      setTimeout(() => {
        if (line.text === "") {
          setLogs((prev) => [...prev, { id: Date.now() + i, type: line.type, text: " " }]);
        } else {
          setLogs((prev) => [...prev, { id: Date.now() + i, type: line.type, text: line.text }]);
        }
      }, delay);
      delay += line.text === "" ? 50 : 120;
    });
    setTimeout(() => setBootDone(true), delay + 200);
  }, []);

  const addLog = useCallback((type, text) => {
    const ts = new Date().toLocaleTimeString("en-GB", { hour12: false }).slice(0, 5);
    setLogs((prev) => [...prev, { id: Date.now() + Math.random(), type, text, ts }]);
  }, []);

  // ─── Command parser ─────────────────────────────────────────────────────────
  const handleCommand = useCallback(
    async (raw) => {
      const trimmed = raw.trim();
      if (!trimmed) return;

      setHistory((prev) => [trimmed, ...prev.slice(0, 49)]);
      setHistIdx(-1);
      addLog("input", trimmed);

      const parts = trimmed.split(/\s+/);
      const cmd = parts[0].toLowerCase();

      // ── Built-in commands ──────────────────────────────────────────────────
      if (cmd === "clear") {
        setLogs([]);
        setStatusData(null);
        setGoalsData(null);
        return;
      }

      if (cmd === "theme") {
        const t2 = parts[1];
        if (t2 === "dark" || t2 === "light") {
          setTheme(t2);
          addLog("success", `THEME SET: ${t2.toUpperCase()}`);
        } else {
          addLog("error", "USAGE: theme [dark|light]");
        }
        return;
      }

      if (cmd === "lang") {
        const l = parts[1];
        if (l === "ru" || l === "en") {
          setLang(l);
          addLog("success", `LANGUAGE SET: ${l.toUpperCase()}`);
        } else {
          addLog("error", "USAGE: lang [ru|en]");
        }
        return;
      }

      if (cmd === "help") {
        addLog("system", "─────────────────────────────────");
        Object.values(T[lang].commands).forEach((c) => addLog("output", c));
        addLog("system", "─────────────────────────────────");
        return;
      }

      // ── Auth check ─────────────────────────────────────────────────────────
      if (!authenticated && cmd !== "login") {
        addLog("warn", t.authPrompt);
        addLog("output", "USAGE: login [username] [password]");
        return;
      }

      // ── API commands ────────────────────────────────────────────────────────
      if (cmd === "login") {
        const [, uname, pass] = parts;
        if (!uname || !pass) {
          addLog("error", "USAGE: login [username] [password]");
          return;
        }
        addLog("system", "AUTHENTICATING...");
        const res = await apiCall("/auth/login", "POST", { username: uname, password: pass });
        if (res.error || res.detail) {
          addLog("panic", res.detail || res.message);
        } else {
          setAuthenticated(true);
          setUserId(res.user_id);
          addLog("success", res.message);
        }
        return;
      }

      if (cmd === "check-status") {
        addLog("system", "QUERYING KERNEL...");
        const res = await apiCall(`/status/${userId}`);
        if (res.error) {
          addLog("error", res.message);
        } else {
          setStatusData(res);
          addLog("output", res.kernel_panic ? "⚡ KERNEL PANIC DETECTED" : "KERNEL: ALL CLEAR");
        }
        return;
      }

      if (cmd === "add") {
        const [, amount, type, category, ...descParts] = parts;
        if (!amount || !type || !category) {
          addLog("error", "USAGE: add [amount] [income|expense] [category] [description?]");
          return;
        }
        const res = await apiCall("/transaction/add", "POST", {
          user_id: userId,
          amount: parseFloat(amount),
          type,
          category,
          description: descParts.join(" ") || null,
        });
        if (res.error) {
          addLog("error", res.message);
        } else if (res.status === "BLOCKED") {
          addLog("panic", res.message);
        } else {
          addLog("success", res.message);
          if (res.kernel) addLog("warn", res.kernel.message);
        }
        return;
      }

      if (cmd === "goal-add") {
        const [, ...nameParts] = parts;
        const deadline = nameParts.pop();
        const amount = nameParts.pop();
        const name = nameParts.join(" ");
        if (!name || !amount || !deadline) {
          addLog("error", "USAGE: goal-add [name] [amount] [YYYY-MM-DD]");
          return;
        }
        const res = await apiCall("/goal/add", "POST", {
          user_id: userId,
          name,
          amount: parseFloat(amount),
          deadline: new Date(deadline).toISOString(),
        });
        if (res.error) {
          addLog("error", res.message || "API ERROR");
        } else {
          addLog("success", res.message);
        }
        return;
      }

      if (cmd === "goal-status") {
        const res = await apiCall(`/goal/status/${userId}`);
        if (res.error) {
          addLog("error", res.message);
        } else {
          setGoalsData(res.goals);
          addLog("output", `${res.goals.length} GOALS LOADED`);
        }
        return;
      }

      if (cmd === "repay-debt") {
        const [, debtId, amount] = parts;
        if (!debtId || !amount) {
          addLog("error", "USAGE: repay-debt [debt_id] [amount]");
          return;
        }
        const res = await apiCall("/debt/repay", "POST", {
          user_id: userId,
          debt_id: parseInt(debtId),
          amount: parseFloat(amount),
        });
        if (res.error) addLog("error", res.message);
        else addLog(res.status === "DEBT_CLOSED" ? "success" : "output", res.message);
        return;
      }

      addLog("error", `UNKNOWN COMMAND: '${cmd}' — type 'help'`);
    },
    [authenticated, userId, lang, addLog, t]
  );

  // ─── Key handlers ────────────────────────────────────────────────────────────
  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      handleCommand(input);
      setInput("");
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const next = Math.min(histIdx + 1, history.length - 1);
      setHistIdx(next);
      setInput(history[next] || "");
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = Math.max(histIdx - 1, -1);
      setHistIdx(next);
      setInput(next === -1 ? "" : history[next] || "");
    }
  };

  return (
    <div
      onClick={() => inputRef.current?.focus()}
      style={{
        ...Object.fromEntries(Object.entries(cssVars).map(([k, v]) => [k, v])),
        minHeight: "100vh",
        background: "var(--bg)",
        color: "var(--color-fg)",
        fontFamily: "var(--font-mono)",
        display: "flex",
        flexDirection: "column",
        padding: "0",
        boxSizing: "border-box",
        cursor: "text",
      }}
    >
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div
        style={{
          borderBottom: "1px solid var(--color-border)",
          padding: "8px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "var(--color-surface)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ color: "var(--color-gold)", fontWeight: "bold", fontSize: "14px", letterSpacing: "3px" }}>
            DEONATS
          </span>
          <span style={{ color: "var(--color-dim)", fontSize: "10px" }}>FINANCIAL OS v1.0.0</span>
        </div>
        <div style={{ display: "flex", gap: "16px", fontSize: "11px", color: "var(--color-dim)" }}>
          <span
            style={{ cursor: "pointer", color: theme === "dark" ? "var(--color-gold)" : "var(--color-dim)" }}
            onClick={(e) => { e.stopPropagation(); setTheme("dark"); }}
          >DARK</span>
          <span style={{ color: "var(--color-border)" }}>|</span>
          <span
            style={{ cursor: "pointer", color: theme === "light" ? "var(--color-gold)" : "var(--color-dim)" }}
            onClick={(e) => { e.stopPropagation(); setTheme("light"); }}
          >LIGHT</span>
          <span style={{ color: "var(--color-border)" }}>|</span>
          <span
            style={{ cursor: "pointer", color: lang === "ru" ? "var(--color-gold)" : "var(--color-dim)" }}
            onClick={(e) => { e.stopPropagation(); setLang("ru"); }}
          >RU</span>
          <span style={{ color: "var(--color-border)" }}>|</span>
          <span
            style={{ cursor: "pointer", color: lang === "en" ? "var(--color-gold)" : "var(--color-dim)" }}
            onClick={(e) => { e.stopPropagation(); setLang("en"); }}
          >EN</span>
          {authenticated && (
            <>
              <span style={{ color: "var(--color-border)" }}>|</span>
              <span style={{ color: "var(--color-ok)" }}>● ONLINE</span>
            </>
          )}
        </div>
      </div>

      {/* ── Terminal output ──────────────────────────────────────────────────── */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
          minHeight: "400px",
        }}
      >
        {logs.map((log) => (
          <LogLine key={log.id} type={log.type} ts={log.ts}>
            {log.text}
          </LogLine>
        ))}
        {statusData && <StatusPanel status={statusData} />}
        {goalsData && <GoalsPanel goals={goalsData} />}
        <div ref={endRef} />
      </div>

      {/* ── Input bar ──────────────────────────────────────────────────────── */}
      <div
        style={{
          borderTop: "1px solid var(--color-border)",
          padding: "10px 16px",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          background: "var(--color-input-bg)",
        }}
      >
        <span style={{ color: "var(--color-gold)", fontSize: "13px", userSelect: "none" }}>
          {authenticated ? `[${userId}]►` : "guest►"}
        </span>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t.placeholder}
          autoFocus
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--color-fg)",
            fontFamily: "var(--font-mono)",
            fontSize: "13px",
            caretColor: "var(--color-gold)",
          }}
        />
        <span style={{ color: "var(--color-dim)", fontSize: "10px" }}>↑↓ history · enter</span>
      </div>
    </div>
  );
}
