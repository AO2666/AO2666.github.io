#!/usr/bin/env python3
"""
update_publications.py — refresh data/publications.json for the Antonio Ortega site.

Pulls the author record and the most recent works from OpenAlex (free, no key
required) and writes a small JSON file that index.html reads at load time.

Usage:
    python3 scripts/update_publications.py                 # writes data/publications.json
    python3 scripts/update_publications.py --since 2024-01-01 --limit 30
    python3 scripts/update_publications.py --print-js      # also print a JS fallback array

Environment (all optional):
    OPENALEX_API_KEY   free key from https://openalex.org/settings/api
    OPENALEX_MAILTO    your e-mail (polite pool, faster + more reliable)
    AUTHOR_ID          OpenAlex author id, default A5040001106 (Antonio Ortega, USC)
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

AUTHOR_ID = os.environ.get("AUTHOR_ID", "A5040001106")
API = "https://api.openalex.org"

# Short, human-readable venue names for the sources that show up most often.
VENUE_MAP = {
    "Proceedings - International Conference on Image Processing": "IEEE ICIP",
    "ICASSP, IEEE International Conference on Acoustics, Speech and Signal Processing - Proceedings": "IEEE ICASSP",
    "Proceedings of the IEEE International Conference on Acoustics, Speech, and Signal Processing": "IEEE ICASSP",
    "arXiv (Cornell University)": "arXiv",
    "arXiv": "arXiv",
    "IEEE Transactions on Signal Processing": "IEEE Trans. Signal Processing",
    "IEEE Transactions on Image Processing": "IEEE Trans. Image Processing",
    "IEEE Transactions on Multimedia": "IEEE Trans. Multimedia",
    "IEEE Transactions on Circuits and Systems for Video Technology": "IEEE Trans. CSVT",
    "IEEE Journal of Selected Topics in Signal Processing": "IEEE JSTSP",
    "IEEE Transactions on Signal and Information Processing over Networks": "IEEE TSIPN",
    "Proceedings of the IEEE": "Proc. IEEE",
    "IEEE Signal Processing Magazine": "IEEE Signal Processing Magazine",
    "Data Compression Conference": "DCC",
    "Proceedings of the Data Compression Conference": "DCC",
    "International Conference on Machine Learning": "ICML",
    "Proceedings of the 41st International Conference on Machine Learning": "ICML",
    "European Signal Processing Conference": "EUSIPCO",
    "Proceedings of the European Signal Processing Conference": "EUSIPCO",
    "IEEE International Workshop on Machine Learning for Signal Processing": "IEEE MLSP",
    "Proceedings of the IEEE International Workshop on Machine Learning for Signal Processing": "IEEE MLSP",
    "IEEE International Conference on Multimedia and Expo": "IEEE ICME",
    "Proceedings of the IEEE International Conference on Multimedia and Expo": "IEEE ICME",
    "IEEE International Workshop on Multimedia Signal Processing": "IEEE MMSP",
    "IEEE International Workshop on Multimedia Signal Processing (MMSP)": "IEEE MMSP",
    "Picture Coding Symposium": "PCS",
    "Proceedings of the AAAI Conference on Artificial Intelligence": "AAAI",
    "Findings of the Association for Computational Linguistics: EMNLP (Findings of EMNLP)": "EMNLP (Findings)",
    "IEEE Open Journal of Signal Processing": "IEEE Open J. Signal Processing",
    "SPIE Applications of Digital Image Processing": "SPIE ADIP",
    "Proceedings of the IEEE International Workshop on Multimedia Signal Processing": "IEEE MMSP",
    "IEEE International Conference on Acoustics, Speech, and Signal Processing": "IEEE ICASSP",
    "IEEE International Conference on Acoustics Speech and Signal Processing": "IEEE ICASSP",
    "Machine learning for signal processing ...": "IEEE MLSP",
    "Proceedings of the ACM on Networking": "ACM CoNEXT",
    "Signal Processing Image Communication": "Signal Process.: Image Comm.",
    "Asilomar Conference on Signals, Systems and Computers (ACSSC)": "Asilomar (ACSSC)",
    "IEEE International Symposium on Information Theory": "IEEE ISIT",
    "IEEE Transactions on Computational Imaging": "IEEE Trans. Computational Imaging",
    "IEEE Transactions on Geoscience and Remote Sensing": "IEEE Trans. Geoscience and Remote Sensing",
    "Remote Sensing": "Remote Sensing",
    "Measurement": "Measurement",
    "Signal Processing": "Signal Processing",
    "Applied and Computational Harmonic Analysis": "Appl. Comput. Harmon. Anal.",
}


def get(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ortega-site-updater/1.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def base_params():
    p = {}
    key = os.environ.get("OPENALEX_API_KEY")
    mail = os.environ.get("OPENALEX_MAILTO")
    if key:
        p["api_key"] = key
    if mail:
        p["mailto"] = mail
    return p


def short_author(raw, display):
    """'Zhao, Yanan' -> 'Y. Zhao'; falls back to the display name."""
    if raw and "," in raw:
        last, first = raw.split(",", 1)
        last, first = last.strip(), first.strip()
        if first:
            initials = " ".join(w[0] + "." for w in re.split(r"[\s\-]+", first) if w)
            return f"{initials} {last}"
        return last
    if display:
        parts = display.split()
        if len(parts) > 1:
            return f"{parts[0][0]}. {' '.join(parts[1:])}"
    return display or ""


def format_authors(authorships, max_names=8):
    names = []
    for a in authorships:
        nm = short_author(a.get("raw_author_name"), (a.get("author") or {}).get("display_name"))
        if nm:
            names.append(nm)
    if len(names) > max_names:
        return ", ".join(names[:max_names]) + ", et al."
    return ", ".join(names)


def venue_of(work):
    loc = work.get("primary_location") or {}
    src = (loc.get("source") or {}).get("display_name") or ""
    if not src:
        return ""
    return VENUE_MAP.get(src, src)


def belongs_to_usc(work):
    """True when this author's affiliation on the work is USC or unknown."""
    for a in work.get("authorships") or []:
        aid = ((a.get("author") or {}).get("id") or "")
        if not aid.endswith(AUTHOR_ID):
            continue
        insts = [i.get("display_name") or "" for i in (a.get("institutions") or [])]
        if not insts:
            return True
        return any("Southern California" in i for i in insts)
    return True


def build(since, limit):
    author = get(f"{API}/authors/{AUTHOR_ID}", base_params())
    stats = author.get("summary_stats") or {}

    works = get(
        f"{API}/works",
        {
            **base_params(),
            "filter": f"author.id:{AUTHOR_ID},from_publication_date:{since}",
            "sort": "publication_date:desc",
            "per_page": str(min(200, max(limit * 2, 50))),
            "select": "id,doi,title,publication_year,publication_date,authorships,primary_location,type",
        },
    )

    recent = []
    seen = set()
    for w in works.get("results", []):
        title = (w.get("title") or "").strip()
        if not title:
            continue
        # OpenAlex sometimes merges namesakes. Keep a work only when this
        # author's affiliation is USC or unrecorded (never another university).
        if not belongs_to_usc(w):
            continue
        key = re.sub(r"[^a-z0-9]", "", title.lower())[:70]
        if key in seen:
            continue
        seen.add(key)
        venue = venue_of(w)
        year = w.get("publication_year")
        doi = w.get("doi") or ""
        recent.append(
            {
                "title": title,
                "authors": format_authors(w.get("authorships") or []),
                "venue": venue,
                "year": year,
                "doi": doi,
                "type": w.get("type") or "",
            }
        )
        if len(recent) >= limit:
            break

    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "OpenAlex",
        "author_id": AUTHOR_ID,
        "author_name": author.get("display_name"),
        "profile_url": f"https://openalex.org/{AUTHOR_ID}",
        "stats": {
            "works": author.get("works_count"),
            "citations": author.get("cited_by_count"),
            "h_index": stats.get("h_index"),
            "i10_index": stats.get("i10_index"),
        },
        "recent": recent,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2024-01-01")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--out", default="data/publications.json")
    ap.add_argument("--print-js", action="store_true")
    args = ap.parse_args()

    data = build(args.since, args.limit)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    s = data["stats"]
    print(f"wrote {args.out}: {len(data['recent'])} recent works, "
          f"{s['works']} works / {s['citations']} citations / h={s['h_index']} / i10={s['i10_index']}")

    if args.print_js:
        print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"update_publications.py failed: {e}", file=sys.stderr)
        sys.exit(1)
