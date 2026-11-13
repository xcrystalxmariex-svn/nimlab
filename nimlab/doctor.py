"""`nimlab doctor` (v3.7.1): one command that checks the parts that break
quietly: the long-term memory connection (a real write + semantic recall +
keyword search through the wallet/DSN on this phone), the system prompts
(no instructions to call tools that don't exist), and the MCP tools the
persona would get."""
import sys

from . import colors as C


def memory_checks(ent):
    """[(ok, msg)] for the memory store, with a write/recall round trip."""
    m = ent.memory
    if m is None or (m.settings or {}).get("backend") == "off":
        return [(True, "long-term memory is off (nothing to check)")]
    out = [(not m.offline, ent.memory_startup_line().replace("[memory] ", ""))]
    if m.offline:
        return out
    try:
        out += m.roundtrip()
    except Exception as e:  # noqa: BLE001 - a check reports, it never crashes
        out.append((False, f"round trip failed: {type(e).__name__}: {e}"))
    return out


def prompt_checks(ent):
    from . import environment as ENV
    warns = ENV.lint_entity(ent)
    if not warns:
        return [(True, "system prompts name no tools that are missing")]
    return [(False, w) for w in warns]


def mcp_checks(ent):
    s = ent.mcp_settings or {}
    if not s.get("enabled") or not s.get("url"):
        return [(True, "MCP chat tools are off")]
    tools = ent.refresh_tools() if hasattr(ent, "refresh_tools") else []
    if getattr(ent, "tools_error", None):
        return [(False, f"MCP server unavailable: {ent.tools_error}")]
    from . import mcpmenu
    out = [(True, ent.mcp_startup_line(tools).replace("[MCP] ", ""))]
    own = (s.get("own_memory_tool") or "").strip()
    if own:
        t = next((x for x in tools or [] if x.get("name") == own), None)
        if t is None:
            out.append((False, f"own_memory_tool {own} is not in the server's tool list"))
        else:
            probs = mcpmenu.check_memory_tool_schema(t)
            out.append((not probs, f"own_memory_tool {own}: " + ("; ".join(probs) if probs else "schema fits")))
    return out


def settings_checks(ent):
    """3.7.2: settings that look set but cannot work (a speech URL that is a
    website homepage, roles or fallbacks that are bare URLs)."""
    from . import configlint
    found = configlint.lines(getattr(ent, "cluster", None) or {})
    if not found:
        return [(True, "speech URLs and role models look like endpoints and model ids")]
    return [(False, line) for line in found]


def platform_checks(ent=None, info=None):
    """3.7.4: Python, venv, ffmpeg, cloudflared, linger, RAM/swap. Warnings
    show as [!] and do not fail the doctor; only a too-old Python does."""
    from . import hostenv
    rows = []
    for level, msg, fix in hostenv.checks(info):
        if level == "info":
            continue
        first = (fix or "").splitlines()
        tail = f" -> {first[0]}" if first else ""
        if len(first) > 1:
            tail += " (all commands: nimlab platform)"
        rows.append((True if level == "ok" else ("warn" if level == "warn" else False), msg + tail))
    return rows


def scheduler_checks(ent=None):
    """3.8.0: job schedules parse, shell jobs have shell on, no broken jobs,
    and the scheduler runs when jobs are enabled (a warning)."""
    from . import scheduler
    return scheduler.doctor_lines()


def run(ent=None, out=print, mcp=True):
    if ent is None:
        from .entity import Entity
        ent = Entity(log=lambda *a: None)
    ok_all = True
    for title, fn in (("Settings", settings_checks), ("Long-term memory", memory_checks),
                      ("System prompts", prompt_checks), ("Platform", platform_checks),
                      ("Scheduler", scheduler_checks),
                      ("MCP tools", mcp_checks if mcp else None)):
        if fn is None:
            continue
        out(C.section(title))
        try:
            rows = fn(ent)
        except Exception as e:  # noqa: BLE001
            rows = [(False, f"check failed: {type(e).__name__}: {e}")]
        for ok, msg in rows:
            if " -> " in msg and C.enabled():
                head, _, fix = msg.partition(" -> ")
                msg = head + C.dim(" -> ") + C.hint(fix)
            if ok == "warn":
                out("  " + C.warn("[!]   ") + msg)
                continue
            ok_all &= bool(ok)
            out("  " + (C.ok("[ok]  ") if ok else C.err("[!!]  ")) + msg)
    return ok_all


def cmd_doctor(args):
    from .servemenu import ensure_nvidia_key
    try:
        ensure_nvidia_key()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - the memory check can still run with a local embedder
        pass
    ok = run(mcp=not getattr(args, "no_mcp", False))
    print(C.ok("All checks passed.") if ok else C.warn("Some checks need attention (see [!!] above)."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(cmd_doctor(None))
