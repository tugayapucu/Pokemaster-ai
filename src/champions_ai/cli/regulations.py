"""Has a new Champions regulation appeared upstream yet?

The project is built for one regulation at a time, and a new one is the single
event that most changes what this software has to do: a different dex, a
different metagame, a corpus that no longer describes the format being played.
Finding out late is expensive, so this asks.

**It reports what it observes and nothing else.** No guesses about what a
future regulation will contain, no placeholder entries, no assumptions about
its dex or its rules. If a name appears upstream that this build does not have,
that is what gets printed -- the name, and where it was seen.

Three sources, earliest first:

  github master   `config/formats.ts` on smogon/pokemon-showdown. Formats land
                  here first, often well before a release.
  npm            when it becomes *installable*, which is when this project can
                  actually simulate it.
  the local sim  what the installed build already accepts, asked of the engine
                  rather than hand-kept, because a hand-kept list of engine
                  facts is what drifts.

The gap between the first and second is the useful part: it says a regulation
exists and is not yet usable here, which is exactly when to start preparing.
"""

import re
import urllib.error
import urllib.request

from champions_ai.simulator import ShowdownBridge

MASTER_FORMATS = (
    "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/config/formats.ts"
)
NPM_LATEST = "https://registry.npmjs.org/pokemon-showdown/latest"
TIMEOUT = 25

# Names look like "[Gen 9 Champions] VGC 2026 Reg M-B". Deliberately broad: a
# regulation that breaks this shape should show up as a parse miss rather than
# be silently skipped, so the count is printed too.
CHAMPIONS_NAME = re.compile(r'name:\s*"(\[Gen 9 Champions\][^"]*)"')
COMPETITIVE = re.compile(r"\b(VGC|BSS)\b")


def _fetch(url: str) -> str | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "champions-ai"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _slug(name: str) -> str:
    """Showdown derives an id by lowercasing and dropping non-alphanumerics."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def check(*, competitive_only: bool = True) -> int:
    installed: list[dict] = []
    try:
        with ShowdownBridge() as bridge:
            installed = bridge.formats("champions")
    except Exception as error:  # noqa: BLE001 - the report is still useful offline
        print(f"  could not ask the local simulator: {error}")

    local_ids = {entry["id"] for entry in installed}
    local_shown = [
        entry
        for entry in installed
        if not competitive_only or re.search(r"vgc|bss", entry["id"])
    ]

    print("\n  Installed simulator")
    if not installed:
        print("    unavailable")
    elif not local_shown:
        print("    (no competitive Champions formats)")
    else:
        for entry in sorted(local_shown, key=lambda e: e["id"]):
            print(f"    {entry['id']:<32} mod={entry['mod']}")

    body = _fetch(MASTER_FORMATS)
    print("\n  Upstream (smogon/pokemon-showdown master)")
    if body is None:
        print("    unreachable -- offline, or GitHub is refusing. Nothing is concluded")
        print("    from that: this cannot tell you a regulation has *not* appeared.")
        return 2

    names = sorted(set(CHAMPIONS_NAME.findall(body)))
    if not names:
        print("    no Champions formats matched. The file's shape may have changed,")
        print("    which is a reason to look rather than to conclude nothing is there.")
        return 2

    interesting = [n for n in names if COMPETITIVE.search(n)] if competitive_only else names
    unknown = [n for n in interesting if _slug(n) not in local_ids]

    for name in interesting:
        mark = "NEW" if _slug(name) not in local_ids else "   "
        print(f"    {mark} {name}")
    print(f"    ({len(names)} Champions formats parsed in total)")

    print("\n  Verdict")
    if not unknown:
        print("    Nothing upstream that this build does not already have.")
        return 0

    print(f"    {len(unknown)} format(s) upstream and not in the installed simulator:")
    for name in unknown:
        print(f"      {name}")

    npm = _fetch(NPM_LATEST)
    version = None
    if npm:
        match = re.search(r'"version"\s*:\s*"([^"]+)"', npm)
        version = match.group(1) if match else None
    print()
    if version:
        print(f"    npm latest is {version}. If that is newer than the installed")
        print("    build, `npm install pokemon-showdown@latest` may bring it in;")
        print("    formats reach master before they are released, so a gap here")
        print("    means it exists but is not yet simulatable by this project.")
    else:
        print("    npm was unreachable, so whether it is installable is unknown.")

    print()
    print("    What this does NOT tell you: anything about the new regulation's")
    print("    dex, rules, or metagame. Nothing here inspects those, and nothing")
    print("    in this project should assume them before the mod is installable.")
    return 1
