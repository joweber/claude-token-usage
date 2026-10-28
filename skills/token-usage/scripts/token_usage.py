#!/usr/bin/env python3
"""token_usage.py : DaisyDisk-style breakdown of Claude Code token usage since the last quota reset.

Usage:
  token_usage.py [--usage usage.json] [--window weekly|model|5h] [--since 7d|24h|2026-10-27T22:00Z]
                 [--top 10] [--actions 30] [--project NAME] [--conversation ID]
                 [--html page.html] [--json out.json] [--lang en|fr]

usage.json : output of the Claude desktop app's get_usage tool (the "plan" object), which gives the
percentage used and the reset time of each quota window. Without it, pass --since (default 7d):
the report then has no quota gauges, only what the transcripts measure.

Measured : the "assistant" lines of ~/.claude/projects transcripts, once per request (requestId),
subagents included. Estimated : the "weight" (cost-equivalent) and the window budget derived
from the app's percentage. The footer of every report says so.
"""
import argparse, json, os, sys, glob, re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
ROOT = os.environ.get("CLAUDE_CONFIG_DIR", os.path.join(HOME, ".claude"))
ROOT = os.path.join(ROOT, "projects")

# Cost-equivalent weighting (Anthropic API price ratios: cache read 0.1x, cache write 1.25x,
# output 5x). An estimate, not a measurement.
WEIGHT = {"input": 1.0, "cache_creation": 1.25, "cache_read": 0.1, "output": 5.0}

T = {
 "en": {"title": "CLAUDE CODE TOKEN USAGE", "plan": "plan", "as_of": "as of", "quotas": "QUOTAS (measured by the app)",
        "used": "used, left", "reset": "resets", "in": "in", "extra": "Extra usage", "on": "enabled", "off": "disabled", "spent": "spent",
        "window": "WINDOW", "from": "from", "to": "to", "project": "project", "conversation": "conversation",
        "counts": "{req} requests, {conv} conversations, {proj} projects, {sub} subagent requests",
        "read": "Tokens read by the model", "ctx": "new context", "cache": "cache reads", "direct": "direct", "written": "written",
        "weight": "Weight (cost-equivalent, estimated)", "units": "units", "budget": "Estimated window budget", "left": "about {n} left",
        "projects": "PROJECTS", "conversations": "CONVERSATIONS (top {n})", "actions": "HEAVIEST REQUESTS (top {n}, one line = one model request)",
        "share": "share", "tokens": "tokens", "ctxh": "new ctx", "req": "req", "name": "name", "when": "when", "conv": "conv.", "action": "action",
        "others": "({n} more)", "conv_s": "conv.", "untitled": "(untitled)", "text_reply": "(text reply)",
        "startup": "[startup: initial context] ", "subagent": "[subagent] ", "more_req": "{n} more requests",
        "legend1": "Reading: \"new ctx\" = tokens written to the cache by this request (big tool result, file read, session start);",
        "legend2": "\"cache\" = context re-read, ten times cheaper; \"written\" = what the model produced, the most expensive per token.",
        "legend3": "Measured: local transcript tokens, once per request. Estimated: the weight (cost ratios) and the budget derived from the app's percentage.",
        "no_usage": "No usage.json: quotas unknown, window taken from --since.", "html": "HTML page", "window_since": "since {d}"},
 "fr": {"title": "CONSO TOKENS CLAUDE CODE", "plan": "plan", "as_of": "relevé du", "quotas": "QUOTAS (mesure de l'app)",
        "used": "utilisé, reste", "reset": "remise à zéro", "in": "dans", "extra": "Usage supplémentaire", "on": "activé", "off": "désactivé", "spent": "dépensé",
        "window": "FENÊTRE", "from": "du", "to": "au", "project": "projet", "conversation": "conversation",
        "counts": "{req} requêtes, {conv} conversations, {proj} projets, {sub} requêtes de sous-agents",
        "read": "Tokens lus par le modèle", "ctx": "contexte neuf", "cache": "relu en cache", "direct": "direct", "written": "écrit",
        "weight": "Poids (équivalent coût, estimé)", "units": "unités", "budget": "Budget estimé de la fenêtre", "left": "reste environ {n}",
        "projects": "PROJETS", "conversations": "CONVERSATIONS (top {n})", "actions": "REQUÊTES LES PLUS LOURDES (top {n}, une ligne = une requête au modèle)",
        "share": "part", "tokens": "tokens", "ctxh": "ctx neuf", "req": "req", "name": "nom", "when": "quand", "conv": "conv.", "action": "action",
        "others": "({n} autres)", "conv_s": "conv.", "untitled": "(sans titre)", "text_reply": "(réponse texte)",
        "startup": "[démarrage : contexte initial] ", "subagent": "[sous-agent] ", "more_req": "{n} autres requêtes",
        "legend1": "Lecture : « ctx neuf » = tokens écrits dans le cache à cette requête (gros résultat d'outil, fichier lu, démarrage de session) ;",
        "legend2": "« cache » = contexte relu, dix fois moins cher ; « écrit » = ce que le modèle a produit, le plus cher par token.",
        "legend3": "Mesuré : tokens des transcriptions locales, une fois par requête. Estimé : le poids (pondération coût) et le budget déduit du pourcentage de l'app.",
        "no_usage": "Pas de usage.json : quotas inconnus, fenêtre prise de --since.", "html": "Page HTML", "window_since": "depuis {d}"},
}


def project_name(cwd, folder):
    """Readable project name: last folder of the working directory (worktrees folded into their repo)."""
    p = cwd or ""
    p = re.sub(r"/\.claude/worktrees/[^/]+$", "", p)
    if "scratch-workspaces" in p or "scratch_workspaces" in p:
        return "Claude desktop (scratch)"
    if not p:
        return folder
    if os.path.abspath(p) == HOME:
        return "~"
    return os.path.basename(p.rstrip("/")) or p


def short(s, n):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def tool_label(block):
    name = block.get("name", "?")
    e = block.get("input") or {}
    hint = ""
    if name == "Bash":
        hint = e.get("description") or e.get("command", "")
    elif name in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        hint = os.path.basename(str(e.get("file_path", "")))
    elif name in ("Agent", "Task"):
        hint = e.get("description", "")
    elif name in ("Grep", "Glob"):
        hint = e.get("pattern", "")
    elif name in ("WebFetch", "WebSearch"):
        hint = e.get("url") or e.get("query", "")
    elif name.startswith("mcp__"):
        name = "mcp " + name.split("__")[-1]
        hint = e.get("action_summary") or e.get("action") or e.get("url") or e.get("command") or ""
    return short(f"{name} {hint}".strip(), 70)


def read_transcripts(start, end, tr):
    requests = {}
    titles = {}
    firsts = {}
    files = glob.glob(os.path.join(ROOT, "*", "*.jsonl")) + glob.glob(os.path.join(ROOT, "*", "*", "subagents", "*.jsonl"))
    t_start = start.timestamp()
    for f in files:
        try:
            if os.path.getmtime(f) < t_start:
                continue
        except OSError:
            continue
        folder = f[len(ROOT) + 1:].split("/")[0]
        sid_file = os.path.basename(f).replace(".jsonl", "")
        agent_file = ""
        if "/subagents/" in f:
            sid_file = f.split("/")[-3]
            agent_file = os.path.basename(f).replace(".jsonl", "")
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"type":"custom-title"' in line:
                    try:
                        d = json.loads(line)
                        titles[d.get("sessionId", sid_file)] = d.get("customTitle", "")
                    except Exception:
                        pass
                    continue
                if '"usage"' not in line and '"type":"user"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                typ = d.get("type")
                sid = d.get("sessionId") or sid_file
                if typ == "user" and not d.get("isSidechain"):
                    c = d.get("message", {}).get("content")
                    if isinstance(c, str) and sid not in firsts and not c.startswith("<"):
                        firsts[sid] = short(c, 60)
                    continue
                if typ != "assistant":
                    continue
                m = d.get("message", {})
                u = m.get("usage")
                ts = d.get("timestamp")
                if not u or not ts:
                    continue
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if t < start or t > end:
                    continue
                rid = d.get("requestId") or m.get("id") or d.get("uuid")
                r = requests.get(rid)
                if r is None:
                    r = requests[rid] = {
                        "t": t, "sid": sid, "project": project_name(d.get("cwd"), folder),
                        "model": (m.get("model") or d.get("requestedModel") or "?"),
                        "input": u.get("input_tokens", 0) or 0,
                        "cache_creation": u.get("cache_creation_input_tokens", 0) or 0,
                        "cache_read": u.get("cache_read_input_tokens", 0) or 0,
                        "output": u.get("output_tokens", 0) or 0,
                        "subagent": bool(d.get("isSidechain")), "agent": d.get("agentId") or agent_file,
                        "tools": [], "text": "",
                    }
                for b in m.get("content") or []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        r["tools"].append(tool_label(b))
                    elif b.get("type") == "text" and not r["text"]:
                        r["text"] = short(b.get("text", ""), 60)
    # one project per conversation: the working directory of its first main-thread request
    proj_of = {}
    for r in sorted(requests.values(), key=lambda r: (r["subagent"], r["t"])):
        proj_of.setdefault(r["sid"], r["project"])
    for r in requests.values():
        r["project"] = proj_of[r["sid"]]
    seen = set()
    for r in sorted(requests.values(), key=lambda r: r["t"]):
        key = (r["sid"], r["agent"])
        r["startup"] = key not in seen or r["cache_read"] == 0
        seen.add(key)
    for r in requests.values():
        r["total"] = r["input"] + r["cache_creation"] + r["cache_read"] + r["output"]
        r["weight"] = sum(r[k] * WEIGHT[k] for k in WEIGHT)
    for sid, p in firsts.items():
        titles.setdefault(sid, p)
    return list(requests.values()), titles


def fmt(n, lang):
    n = float(n); sep = "," if lang == "fr" else "."
    if n >= 1e9: return f"{n/1e9:.2f} G".replace(".", sep)
    if n >= 1e6: return f"{n/1e6:.2f} M".replace(".", sep)
    if n >= 1e3: return f"{n/1e3:.0f} k"
    return f"{n:.0f}"


def bar(part, width=20):
    n = int(round(part * width))
    return "█" * n + "░" * (width - n)


def when(t):
    return t.astimezone().strftime("%d/%m %H:%M")


def parse_since(s, now):
    m = re.fullmatch(r"(\d+)([hd])", s.strip())
    if m:
        n, u = int(m.group(1)), m.group(2)
        return now - (timedelta(hours=n) if u == "h" else timedelta(days=n))
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--usage", help="JSON from the desktop app's get_usage tool")
    ap.add_argument("--window", default="weekly", help="weekly | model | 5h (needs --usage)")
    ap.add_argument("--since", default="7d", help="without --usage: 7d, 24h, or an ISO date")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--actions", type=int, default=30, help="requests kept per conversation in the HTML")
    ap.add_argument("--project"); ap.add_argument("--conversation")
    ap.add_argument("--html"); ap.add_argument("--json")
    ap.add_argument("--lang", default="en", choices=["en", "fr"])
    ap.add_argument("--anonymize", action="store_true", help="replace project names, titles and actions with neutral labels (for a screenshot to share)")
    a = ap.parse_args()
    tr = T[a.lang]
    now = datetime.now(timezone.utc)

    plan, windows, chosen = {}, [], None
    if a.usage:
        with open(a.usage, encoding="utf-8") as fh:
            plan = json.load(fh)
        plan = plan.get("plan", plan)
        for w in plan.get("windows", []):
            lab = w.get("label", "")
            reset = datetime.fromisoformat(w["resetsAt"].replace("Z", "+00:00"))
            is5h = "5-hour" in lab or "5h" in lab
            key = "5h" if is5h else ("weekly" if "all models" in lab.lower() else "model")
            windows.append({"key": key, "label": lab, "pct": w.get("percentUsed", 0), "reset": reset,
                            "start": reset - (timedelta(hours=5) if is5h else timedelta(days=7)), "resetsIn": w.get("resetsIn", "")})
        chosen = next((w for w in windows if w["key"] == a.window), None)
        if not chosen:
            sys.exit(f"window {a.window!r} not in {a.usage} (available: {[w['key'] for w in windows]})")
        start, end = chosen["start"], min(chosen["reset"], now)
        label = chosen["label"]
    else:
        start, end = parse_since(a.since, now), now
        label = tr["window_since"].format(d=when(start))

    reqs, titles = read_transcripts(start, end, tr)
    if chosen and chosen["key"] == "model":
        # per-model window: keep requests of the model named in the label (e.g. "Weekly · Opus")
        tag = chosen["label"].split("·")[-1].strip().lower()
        if tag:
            reqs = [r for r in reqs if tag in r["model"].lower()]
    if a.anonymize:
        pmap, smap = {}, {}
        for r in sorted(reqs, key=lambda r: r["t"]):
            pmap.setdefault(r["project"], f"Project {chr(65 + len(pmap) % 26)}")
            smap.setdefault(r["sid"], f"Conversation {len(smap) + 1}")
            r["project"] = pmap[r["project"]]; r["tools"] = [f"{t.split(' ')[0]} …" for t in r["tools"]]; r["text"] = ""
        for r in reqs: r["sid"] = smap[r["sid"]].replace("Conversation ", "conv-").zfill(8)
        titles = {smap[sid].replace("Conversation ", "conv-").zfill(8): smap[sid] for sid in smap}
    if a.project:
        reqs = [r for r in reqs if r["project"] == a.project]
    if a.conversation:
        reqs = [r for r in reqs if r["sid"].startswith(a.conversation)]

    F = lambda n: fmt(n, a.lang)
    plan_txt = f"{tr['plan']} {plan['plan']}  ·  " if plan.get("plan") else ""
    L = [f"{tr['title']}  ·  {plan_txt}{tr['as_of']} {when(now)}", ""]
    if windows:
        L.append(tr["quotas"])
        for w in windows:
            L.append(f"  {bar(w['pct']/100)} {w['pct']:3d} % {tr['used']} {100-w['pct']:3d} %   {w['label']:<22} {tr['reset']} {when(w['reset'])} ({tr['in']} {w['resetsIn']})")
        eu = plan.get("extraUsage") or {}
        if eu:
            L.append(f"  {tr['extra']} : {tr['on'] if eu.get('enabled') else tr['off']}, {tr['spent']} {eu.get('spent', '?')} {eu.get('currency', '')}")
    else:
        L.append(tr["no_usage"])
    L.append("")
    head = f"{tr['window']} : {label}  {tr['from']} {when(start)} {tr['to']} {when(end)}"
    if a.project: head += f"  ·  {tr['project']} {a.project}"
    if a.conversation: head += f"  ·  {tr['conversation']} {a.conversation}"
    L.append(head)
    tot = {k: sum(r[k] for r in reqs) for k in ("input", "cache_creation", "cache_read", "output", "total", "weight")}
    n_sess = len({r["sid"] for r in reqs})
    L.append("  " + tr["counts"].format(req=len(reqs), conv=n_sess, proj=len({r['project'] for r in reqs}), sub=sum(1 for r in reqs if r["subagent"])))
    L.append(f"  {tr['read']} : {F(tot['total'])}   ({tr['ctx']} {F(tot['cache_creation'])}, {tr['cache']} {F(tot['cache_read'])}, {tr['direct']} {F(tot['input'])}, {tr['written']} {F(tot['output'])})")
    L.append(f"  {tr['weight']} : {F(tot['weight'])} {tr['units']}")
    if chosen and chosen["pct"] > 0 and tot["weight"] > 0 and not a.project and not a.conversation:
        budget = tot["weight"] * 100 / chosen["pct"]
        L.append(f"  {tr['budget']} : {F(budget)} {tr['units']}, {tr['left'].format(n=F(budget - tot['weight']))}")
    L.append("")

    def table(title, key, name_of):
        groups = defaultdict(lambda: {"weight": 0.0, "total": 0.0, "output": 0.0, "cache_creation": 0.0, "n": 0, "sids": set()})
        for r in reqs:
            g = groups[key(r)]
            for k in ("weight", "total", "output", "cache_creation"):
                g[k] += r[k]
            g["n"] += 1; g["sids"].add(r["sid"])
        rows = sorted(groups.items(), key=lambda kv: -kv[1]["weight"])
        L.append(title)
        L.append(f"  {tr['share']:>5}  {'':20}  {'weight' if a.lang=='en' else 'poids':>8}  {tr['tokens']:>8}  {tr['ctxh']:>8}  {tr['written']:>7}  {tr['req']:>5}  {tr['name']}")
        rest = 0.0
        for i, (k, g) in enumerate(rows):
            if i >= a.top:
                rest += g["weight"]; continue
            part = g["weight"] / tot["weight"] if tot["weight"] else 0
            L.append(f"  {part*100:4.0f} %  {bar(part)}  {F(g['weight']):>8}  {F(g['total']):>8}  {F(g['cache_creation']):>8}  {F(g['output']):>7}  {g['n']:>5}  {name_of(k, g)}")
        if rest:
            L.append(f"  {rest/tot['weight']*100:4.0f} %  {bar(rest/tot['weight'])}  {F(rest):>8}  {'':>8}  {'':>8}  {'':>7}  {'':>5}  {tr['others'].format(n=len(rows)-a.top)}")
        L.append("")

    if not a.project and not a.conversation:
        table(tr["projects"], lambda r: r["project"], lambda k, g: f"{k}  ({len(g['sids'])} {tr['conv_s']})")
    if not a.conversation:
        table(tr["conversations"].format(n=a.top), lambda r: r["sid"],
              lambda k, g: f"{k[:8]}  {short(titles.get(k, tr['untitled']), 48)}  [{next(r['project'] for r in reqs if r['sid']==k)}]")

    def action_of(r):
        act = " ; ".join(r["tools"][:3]) if r["tools"] else (r["text"] or tr["text_reply"])
        if len(r["tools"]) > 3: act += f" (+{len(r['tools'])-3})"
        return (tr["startup"] if r["startup"] else "") + (tr["subagent"] if r["subagent"] else "") + act

    L.append(tr["actions"].format(n=a.top))
    L.append(f"  {'weight' if a.lang=='en' else 'poids':>8}  {tr['ctxh']:>8}  {'cache':>8}  {tr['written']:>7}  {tr['when']:<12} {tr['conv']:<9} {tr['action']}")
    for r in sorted(reqs, key=lambda r: -r["weight"])[: a.top]:
        L.append(f"  {F(r['weight']):>8}  {F(r['cache_creation']):>8}  {F(r['cache_read']):>8}  {F(r['output']):>7}  {when(r['t'])}  {r['sid'][:8]}  {short(action_of(r), 90)}")
    L += ["", tr["legend1"], tr["legend2"], tr["legend3"]]
    print("\n".join(L))

    if a.html:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from page import write_html
        def node(name, rs, meta="", others=False):
            return {"name": name, "meta": meta, "others": others, "v": sum(r["weight"] for r in rs),
                    "tokens": sum(r["total"] for r in rs), "ctx": sum(r["cache_creation"] for r in rs),
                    "out": sum(r["output"] for r in rs), "n": len(rs)}
        by_project = defaultdict(list)
        for r in reqs: by_project[r["project"]].append(r)
        tree = node(label, reqs, f"{tr['from']} {when(start)} {tr['to']} {when(end)}"); tree["children"] = []
        for pj, rp in by_project.items():
            by_sess = defaultdict(list)
            for r in rp: by_sess[r["sid"]].append(r)
            np_ = node(pj, rp, f"{len(by_sess)} {tr['conv_s']}"); np_["children"] = []
            for sid, rs in by_sess.items():
                ns = node(titles.get(sid, tr["untitled"]), rs, f"{sid[:8]} · {when(min(r['t'] for r in rs))} → {when(max(r['t'] for r in rs))}")
                ns["children"] = []
                ranked = sorted(rs, key=lambda r: -r["weight"])
                for r in ranked[: a.actions]:
                    ns["children"].append(node(short(action_of(r), 110), [r], when(r["t"]) + " · " + r["model"]))
                rest = ranked[a.actions:]
                if rest:
                    ns["children"].append(node(tr["more_req"].format(n=len(rest)), rest, "", True))
                np_["children"].append(ns)
            tree["children"].append(np_)
        quotas = [{"label": w["label"], "pct": w["pct"], "reset": when(w["reset"]), "in": w["resetsIn"]} for w in windows]
        main_q = {"label": chosen["label"], "pct": chosen["pct"]} if chosen else None
        subtitle = f"{plan_txt.replace('  ·  ', ' · ')}{tr['as_of']} {when(now)} · {label} {tr['from']} {when(start)} {tr['to']} {when(end)} · {len(reqs)} req., {n_sess} conv."
        write_html(a.html, tree, quotas, main_q, subtitle, a.lang)
        print(f"\n{tr['html']} : {a.html}")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"window": label, "start": start.isoformat(), "end": end.isoformat(),
                       "requests": [{**r, "t": r["t"].isoformat()} for r in reqs], "titles": titles}, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
