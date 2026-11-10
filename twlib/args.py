"""Command-line option checking: reject typos instead of silently ignoring them."""
import difflib, sys

# option -> does it take a value? Register every new CLI option here (and in USAGE).
FLAGS = {
    "--project": True, "--sessions": True, "--since": True, "--until": True,
    "--budget": True, "--period": True, "--export": True, "--theme": True,
    "--json": False, "--open": False, "--today": False, "--week": False, "--daily": False,
    "--help": False, "-h": False,
}

USAGE = """tokenwatch: where your Claude Code tokens go (local, read-only)

usage: python3 tokenwatch.py [options]

  --project NAME            only projects whose path contains NAME
  --sessions N              sessions shown per project (default 5)
  --today | --week          only today / the last 7 days
  --since DATE [--until DATE]   a date window (YYYY-MM-DD, by session start day)
  --daily                   per-day cost table with a sparkline
  --budget N [--period day|week|month]   spending budget (or TOKENWATCH_BUDGET=N/period)
  --json                    machine-readable output
  --open                    build the HTML dashboard and open it in your browser
  --export html [PATH]      write a self-contained HTML dashboard (add --open to also open it)
  --theme classic|weather   dashboard look (weather = parody forecast); with --open or --export
  -h, --help                this help
"""

HINT = "Run `python3 tokenwatch.py --help` for the list of options."


def find_problem(tokens):
    """The first problem in the option list as a message, or None. Pure, so it is easy to test."""
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in FLAGS:
            if t == "--export":
                if i + 1 >= len(tokens) or tokens[i + 1] != "html":
                    return "--export needs 'html' (usage: --export html [PATH])"
                i += 2
                if i < len(tokens) and not tokens[i].startswith("--"): i += 1   # optional PATH
                continue
            if FLAGS[t]:
                if i + 1 >= len(tokens) or tokens[i + 1] in FLAGS:
                    return f"{t} needs a value"
                i += 2                      # the value may look odd (e.g. a negative budget): validated later
                continue
            i += 1
            continue
        name = t.split("=", 1)[0]
        if "=" in t and FLAGS.get(name):
            return f"unknown option '{t}' (write the value as a separate word: {name} {t.split('=', 1)[1]})"
        if not t.startswith("-"):
            return f"unexpected argument '{t}' (options start with --)"
        guess = difflib.get_close_matches(t.rstrip(",.;:"), [f for f in FLAGS if f.startswith("--")], n=1, cutoff=0.6)
        return f"unknown option '{t}'" + (f" (did you mean {guess[0]}?)" if guess else "")
    return None


def check(argv):
    """Exit 0 after --help, or exit 2 with a message on a bad option; return quietly when all is well."""
    tokens = argv[1:]
    if "--help" in tokens or "-h" in tokens:
        print(USAGE)
        sys.exit(0)
    problem = find_problem(tokens)
    if problem:
        print(f"tokenwatch: {problem}\n{HINT}", file=sys.stderr)
        sys.exit(2)
