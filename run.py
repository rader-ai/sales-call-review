#!/usr/bin/env python3
"""Local, source-agnostic call review. Python standard library only."""
import argparse
import csv
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "workspace"
TURN = re.compile(r"^\*\*(.+?)\*\*\s*(?:\[(\d{1,2}:\d{2}(?::\d{2})?)\])?\s*:?[ \t]*(.*)$")


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or "account"


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def calls():
    return sorted(WORK.glob("accounts/*/calls/*/meta.json"))


def call_dir(meta):
    return meta.parent


def init():
    (WORK / "accounts").mkdir(parents=True, exist_ok=True)
    print(f"Private workspace ready: {WORK}")


def add(args):
    source = Path(args.transcript).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Transcript not found: {source}")
    account, ident = slug(args.account), slug(args.id)
    target = WORK / "accounts" / account / "calls" / ident
    if target.exists() and not args.replace:
        raise ValueError(f"Call already exists: {target}. Use --replace to update it.")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target / "transcript.md")
    meta = {"account": args.account, "id": ident, "date": args.date, "title": args.title,
            "internal": [x.strip() for x in args.internal.split(",") if x.strip()],
            "external": [x.strip() for x in args.external.split(",") if x.strip()],
            "source": args.source, "recorded": args.recorded}
    write_json(target / "meta.json", meta)
    print(f"Added {args.account} / {ident}")


def import_csv(args):
    """Expected columns: account,id,date,title,internal,external,transcript,recorded,source."""
    path = Path(args.csv).expanduser().resolve()
    count = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if not row.get("account") or not row.get("id"):
                raise ValueError("Each row needs account and id")
            transcript = (path.parent / row["transcript"]).resolve() if row.get("transcript") else None
            if transcript:
                add(argparse.Namespace(transcript=str(transcript), account=row["account"], id=row["id"],
                    date=row.get("date", ""), title=row.get("title", ""),
                    internal=row.get("internal", ""), external=row.get("external", ""),
                    source=row.get("source", "csv"), recorded=row.get("recorded", "").lower() in ("yes", "true", "1"),
                    replace=args.replace))
            else:
                target = WORK / "accounts" / slug(row["account"]) / "calls" / slug(row["id"])
                if target.exists() and not args.replace:
                    raise ValueError(f"Call already exists: {target}")
                write_json(target / "meta.json", {"account": row["account"], "id": slug(row["id"]),
                    "date": row.get("date", ""), "title": row.get("title", ""),
                    "internal": [x.strip() for x in row.get("internal", "").split(";") if x.strip()],
                    "external": [x.strip() for x in row.get("external", "").split(";") if x.strip()],
                    "source": row.get("source", "csv"), "recorded": False})
            count += 1
    print(f"Imported {count} timeline entries. Calls without transcripts remain visible as coverage gaps.")


def parse_turns(text):
    turns = []
    for line in text.splitlines():
        match = TURN.match(line.strip())
        if match:
            turns.append({"speaker": match[1].rstrip(":"), "time": match[2] or "", "text": match[3]})
        elif turns and line.strip() and not line.lstrip().startswith("#"):
            turns[-1]["text"] += " " + line.strip()
    return turns


def word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text))


def side(speaker, meta):
    if "unclear" in speaker.lower():
        return "unclear"
    for key, label in (("internal", "internal"), ("external", "external")):
        for person in meta.get(key, []):
            if speaker.casefold() == person.casefold():
                return label
    return "unclear"  # Never assign an unknown speaker to the customer.


def metrics(meta, transcript):
    turns = parse_turns(transcript)
    words = Counter({"internal": 0, "external": 0, "unclear": 0})
    questions = Counter({"internal": 0, "external": 0, "unclear": 0})
    longest = 0
    current, running = None, 0
    for turn in turns:
        role = side(turn["speaker"], meta)
        size = word_count(turn["text"])
        words[role] += size
        questions[role] += turn["text"].count("?")
        if role == "internal":
            running = running + size if current == turn["speaker"] else size
            current = turn["speaker"]
            longest = max(longest, running)
        else:
            current, running = None, 0
    known = words["internal"] + words["external"]
    return {"turns": len(turns), "words": dict(words), "question_marks": dict(questions),
            "internal_talk_share": round(words["internal"] / known, 3) if known else None,
            "longest_internal_monologue_words": longest,
            "unknown_speakers_excluded": words["unclear"] > 0}


def normalize(text):
    return " ".join(re.findall(r"[\w']+", text.casefold().replace("’", "'")))


def verify(analysis, transcript):
    """Require each substantive quote to match a single speaker turn."""
    turns = [normalize(t["text"]) for t in parse_turns(transcript)]
    results = []
    def walk(node, path="$"):
        if isinstance(node, dict):
            if "quote" in node:
                quote = normalize(str(node["quote"]))
                ok = bool(quote) and any(quote in turn for turn in turns)
                results.append({"path": path + ".quote", "ok": ok, "quote": node["quote"]})
            for key, value in node.items():
                if key != "quote":
                    walk(value, path + "." + key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
    walk(analysis)
    return results


def review(args):
    failures = 0
    for path in calls():
        folder = call_dir(path)
        transcript = folder / "transcript.md"
        if not transcript.exists():
            continue
        stats = metrics(load_json(path), transcript.read_text(encoding="utf-8"))
        write_json(folder / "metrics.json", stats)
        analysis_path = folder / "analysis.json"
        if analysis_path.exists():
            checks = verify(load_json(analysis_path), transcript.read_text(encoding="utf-8"))
            write_json(folder / "verification.json", {"checked": len(checks), "failed": sum(not x["ok"] for x in checks), "details": checks})
            failures += sum(not x["ok"] for x in checks)
        print(f"{load_json(path)['account']} / {folder.name}: {stats['turns']} turns, talk share {stats['internal_talk_share']}")
    if failures:
        print(f"{failures} quotes failed verification. The report will not present those claims as verified.")
    else:
        print("Review complete. Quote checks only run where analysis.json exists.")
    return failures


def card(title, value):
    return f'<div class="card"><span>{html.escape(title)}</span><strong>{html.escape(str(value))}</strong></div>'


def report(args):
    review(args)
    rows = []
    for path in calls():
        meta, folder = load_json(path), call_dir(path)
        stats = load_json(folder / "metrics.json") if (folder / "metrics.json").exists() else None
        analysis = load_json(folder / "analysis.json") if (folder / "analysis.json").exists() else None
        checks = load_json(folder / "verification.json") if (folder / "verification.json").exists() else None
        rows.append((meta, stats, analysis, checks))
    if not rows:
        raise ValueError("No calls yet. Run 'python3 run.py demo' or import your own calls.")
    account_groups = defaultdict(list)
    for row in rows:
        account_groups[row[0]["account"]].append(row)
    analyzed = sum(bool(r[2]) for r in rows)
    recorded = sum(bool(r[1]) for r in rows)
    failed = sum(r[3]["failed"] for r in rows if r[3])
    themes = defaultdict(lambda: {"accounts": set(), "calls": 0, "examples": []})
    for meta, _, analysis, checks in rows:
        for theme in (analysis or {}).get("themes", []):
            evidence = theme.get("evidence", [])
            verified = checks and evidence and all(any(x["ok"] and x["quote"] == e.get("quote") for x in checks["details"]) for e in evidence)
            if not verified or not theme.get("tag"):
                continue
            item = themes[theme["tag"]]
            item["accounts"].add(meta["account"])
            item["calls"] += 1
            item["examples"].append((meta["account"], theme.get("observation", "")))
    body = '<header><p class="eyebrow">CALL REVIEW LAB / LOCAL REPORT</p><h1>What happened in the conversations?</h1><p>Coverage, measured behavior, and evidence checked coaching notes. This is a review aid, not a performance verdict.</p></header>'
    body += '<section class="cards">' + card("Accounts", len(account_groups)) + card("Timeline calls", len(rows)) + card("Transcripts", recorded) + card("Analyzed", analyzed) + card("Unverified quotes", failed) + '</section>'
    if themes:
        body += '<section><h2>Patterns to investigate</h2><p>Counts use distinct accounts. Themes require checked quotations, but still need skeptical review before a market claim.</p><div class="stack">'
        for tag, item in sorted(themes.items(), key=lambda pair: (-len(pair[1]["accounts"]), pair[0])):
            body += f'<article><div class="top"><h3>{html.escape(tag)}</h3><span class="pill">{len(item["accounts"])} accounts · {item["calls"]} calls</span></div>'
            for account, observation in item["examples"][:3]:
                body += f'<p><b>{html.escape(account)}:</b> {html.escape(observation)}</p>'
            body += '</article>'
        body += '</div></section>'
    for account, items in sorted(account_groups.items()):
        body += f'<section><h2>{html.escape(account)}</h2><div class="stack">'
        for meta, stats, analysis, checks in sorted(items, key=lambda r: (r[0].get("date", ""), r[0]["id"])):
            state = "Transcript absent" if stats is None else "Transcript reviewed"
            body += f'<article><div class="top"><div><span class="eyebrow">{html.escape(meta.get("date", ""))} · {html.escape(meta.get("id", ""))}</span><h3>{html.escape(meta.get("title") or "Untitled call")}</h3></div><span class="pill">{state}</span></div>'
            if stats:
                share = f"{stats['internal_talk_share']:.0%}" if stats["internal_talk_share"] is not None else "Unknown"
                body += f'<div class="measure"><span>Internal talk share <b>{share}</b></span><span>Question marks <b>{stats["question_marks"]["internal"]} / {stats["question_marks"]["external"]}</b></span><span>Longest internal run <b>{stats["longest_internal_monologue_words"]} words</b></span></div>'
                if stats["unknown_speakers_excluded"]:
                    body += '<p class="note">Some speakers were unclear and excluded from talk share.</p>'
            if analysis:
                if checks and checks["failed"]:
                    body += '<p class="note">Some quotes failed verification. Interpret the summary and coaching notes with extra care.</p>'
                body += f'<p class="summary">{html.escape(analysis.get("summary", ""))}</p>'
                good = analysis.get("strengths", [])
                improve = analysis.get("opportunities", [])
                for heading, entries in (("What worked", good), ("What to practice", improve)):
                    if entries:
                        body += f'<h4>{heading}</h4><ul>'
                        for i, entry in enumerate(entries):
                            evidence = entry.get("evidence", [])
                            valid = checks and all(any(x["ok"] and x["quote"] == e.get("quote") for x in checks["details"]) for e in evidence) and bool(evidence)
                            body += f'<li><b>{html.escape(entry.get("point", ""))}</b> <span class="tag">{"Quote verified" if valid else "Needs evidence review"}</span>'
                            if valid:
                                body += '<blockquote>' + ' '.join('“' + html.escape(e["quote"]) + '”' for e in evidence) + '</blockquote>'
                            body += '</li>'
                        body += '</ul>'
                practice = analysis.get("practice") or {}
                if practice.get("behavior"):
                    body += '<h4>Practice and recheck</h4><p><b>' + html.escape(practice["behavior"]) + '</b> · ' + html.escape(practice.get("owner", "Owner to assign")) + ' · ' + html.escape(practice.get("check_in", "Next call")) + '</p>'
            body += '</article>'
        body += '</div></section>'
    body += '<footer>Numbers count words and question marks in speaker labeled transcripts. They do not measure speaking time or question quality. Human review is required for coaching conclusions.</footer>'
    css = """*{box-sizing:border-box}body{margin:0;background:#f4f3ee;color:#172c35;font:16px/1.55 system-ui,-apple-system,sans-serif}header,section,footer{max-width:1100px;margin:0 auto;padding:30px 24px}header{padding-top:76px}h1{font-size:clamp(2.5rem,6vw,5rem);line-height:1.06;letter-spacing:-.055em;max-width:850px;margin:12px 0}h2{font-size:1.9rem;letter-spacing:-.035em}h3{margin:3px 0;font-size:1.24rem}.eyebrow{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:#53727a;font-weight:750}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;padding-top:8px}.card,article{background:#fff;border:1px solid #d8e0dd;border-radius:15px}.card{padding:18px}.card span{font-size:.78rem;color:#527077;display:block}.card strong{display:block;font-size:2rem;line-height:1.2}.stack{display:grid;gap:12px}article{padding:24px}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.pill,.tag{font-size:.72rem;background:#e6f1ee;color:#225849;padding:5px 9px;border-radius:99px;white-space:nowrap}.tag{margin-left:6px}.measure{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.measure span{background:#f3f6f4;padding:9px 12px;border-radius:8px;font-size:.83rem}.measure b{margin-left:6px}.summary{font-size:1.06rem}.note,footer{color:#63747a;font-size:.83rem}ul{padding-left:20px}li{margin:12px 0}blockquote{border-left:3px solid #50a590;padding-left:13px;margin:8px 0;color:#385159}@media(max-width:750px){header{padding-top:42px}.cards{grid-template-columns:repeat(2,1fr)}.top{display:block}.pill{display:inline-block;margin-top:8px}.measure{display:grid}.card strong{font-size:1.5rem}}@media print{body{background:white}article,.card{break-inside:avoid}header{padding-top:10px}}"""
    out = Path(args.output).expanduser().resolve() if args.output else WORK / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Call Review Lab</title><style>' + css + '</style></head><body>' + body + '</body></html>', encoding="utf-8")
    print(f"Report: {out}")


def transcribe(args):
    media, model = Path(args.media).expanduser().resolve(), Path(args.model).expanduser().resolve()
    for tool in ("ffmpeg", "whisper-cli"):
        if not shutil.which(tool):
            raise ValueError(f"{tool} is required and was not found on PATH")
    if not media.is_file() or not model.is_file():
        raise ValueError("Provide an existing --media file and --model file")
    out = Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".temporary.wav")
    try:
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
        subprocess.run(["whisper-cli", "-m", str(model), "-f", str(wav), "-l", args.language,
                        "-t", str(args.threads), "-otxt", "-of", str(out.with_suffix(""))], check=True)
    finally:
        wav.unlink(missing_ok=True)
    print(f"Raw transcript written beside {out}. Review and label speakers before import. Source media preserved.")


def demo():
    if any(calls()):
        raise ValueError("Demo requires an empty workspace so it cannot mix with your calls")
    root = ROOT / "examples"
    import_csv(argparse.Namespace(csv=str(root / "calls.csv"), replace=False))
    sample = root / "sample-analysis.json"
    target = WORK / "accounts" / "harbor-tools" / "calls" / "discovery-01" / "analysis.json"
    shutil.copyfile(sample, target)
    report(argparse.Namespace(output=None))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("demo")
    p = sub.add_parser("add", help="Import one cleaned, speaker labeled transcript")
    for name in ("transcript", "account", "id", "date", "title", "internal", "external"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--source", default="local")
    p.add_argument("--recorded", action="store_true")
    p.add_argument("--replace", action="store_true")
    p = sub.add_parser("import-csv", help="Import a timeline and relative transcript paths")
    p.add_argument("csv")
    p.add_argument("--replace", action="store_true")
    sub.add_parser("review")
    p = sub.add_parser("report")
    p.add_argument("--output")
    p = sub.add_parser("transcribe", help="Optional local whisper.cpp transcription")
    p.add_argument("--media", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--language", default="en")
    p.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    try:
        {"init": init, "demo": demo, "add": lambda: add(args), "import-csv": lambda: import_csv(args),
         "review": lambda: review(args), "report": lambda: report(args), "transcribe": lambda: transcribe(args)}[args.command]()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
