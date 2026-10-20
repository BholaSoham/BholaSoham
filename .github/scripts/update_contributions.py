#!/usr/bin/env python3
"""Refresh the profile's all-time GitHub contribution SVG using the GraphQL API."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

API_URL = "https://api.github.com/graphql"
USERNAME = os.environ.get("GITHUB_USERNAME", "BholaSoham")
TOKEN = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUTPUT = Path("assets/all-time-contributions.svg")


def graphql(query: str, variables: dict) -> dict:
    if not TOKEN:
        raise RuntimeError("No GitHub token found in PROFILE_TOKEN or GITHUB_TOKEN.")

    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "BholaSoham-Profile-Stats",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach GitHub GraphQL: {exc}") from exc

    if data.get("errors"):
        raise RuntimeError("GitHub GraphQL error: " + json.dumps(data["errors"]))
    return data.get("data") or {}


def to_iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_all_time_contributions() -> int:
    profile = graphql(
        "query ProfileCreatedAt($login: String!) { user(login: $login) { createdAt } }",
        {"login": USERNAME},
    ).get("user")
    if not profile or not profile.get("createdAt"):
        raise RuntimeError(f"Could not find GitHub user {USERNAME!r}.")

    created_at = datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    cursor = datetime.combine(created_at.date(), time.min, tzinfo=timezone.utc)
    total = 0

    # GitHub limits a contributionsCollection range to one year. Keep each
    # request to 364 days, aligned to UTC day boundaries to avoid overlap.
    query = """
    query ContributionsInRange($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
        }
      }
    }
    """

    while cursor < now:
        next_boundary = cursor + timedelta(days=364)
        is_last_chunk = now <= next_boundary
        end = now if is_last_chunk else next_boundary - timedelta(seconds=1)
        result = graphql(
            query,
            {"login": USERNAME, "from": to_iso_z(cursor), "to": to_iso_z(end)},
        ).get("user")
        if result is None:
            raise RuntimeError(f"GitHub returned no contribution data for {USERNAME!r}.")
        count = result["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        total += int(count)
        print(f"Counted {count} contributions from {cursor.date()} through {end.date()}.")

        if is_last_chunk:
            break
        cursor = next_boundary

    return total


def render_svg(total: int) -> str:
    formatted = f"{total:,}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="180" viewBox="0 0 900 180" role="img" aria-labelledby="title desc">
  <title id="title">{formatted} all-time GitHub contributions</title>
  <desc id="desc">All-time GitHub contributions for {USERNAME}, refreshed daily by GitHub Actions.</desc>
  <defs>
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#58a6ff" />
      <stop offset="100%" stop-color="#3fb950" />
    </linearGradient>
    <radialGradient id="glow">
      <stop offset="0%" stop-color="#3fb950" stop-opacity=".25" />
      <stop offset="100%" stop-color="#3fb950" stop-opacity="0" />
    </radialGradient>
  </defs>
  <rect x="1" y="1" width="898" height="178" rx="16" fill="#0d1117" stroke="#30363d" />
  <rect x="1.5" y="1.5" width="897" height="4" rx="2" fill="url(#edge)" />
  <circle cx="92" cy="91" r="48" fill="url(#glow)">
    <animate attributeName="r" values="42;50;42" dur="3s" repeatCount="indefinite" />
    <animate attributeName="opacity" values=".65;1;.65" dur="3s" repeatCount="indefinite" />
  </circle>
  <g transform="translate(64 63)" fill="none" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M28 2 34 14 47 16 37.5 25.5 40 39 28 32.5 16 39 18.5 25.5 9 16 22 14Z" />
    <path d="M28 2V10M47 16 39 19M40 39 34 31M16 39 22 31M9 16 17 19" opacity=".55" />
  </g>
  <text x="160" y="47" fill="#8b949e" font-family="'Segoe UI', Arial, sans-serif" font-size="15" font-weight="700" letter-spacing="2.5">GITHUB CONTRIBUTIONS</text>
  <text x="156" y="117" fill="#c9d1d9" font-family="'Segoe UI', Arial, sans-serif" font-size="56" font-weight="750">{formatted}</text>
  <text x="162" y="146" fill="#3fb950" font-family="'Segoe UI', Arial, sans-serif" font-size="14" font-weight="600" letter-spacing=".5">ALL TIME · AND COUNTING</text>
  <line x1="590" y1="38" x2="590" y2="142" stroke="#30363d" />
  <text x="622" y="69" fill="#58a6ff" font-family="'Segoe UI', Arial, sans-serif" font-size="16" font-weight="650">Not just the last 12 months</text>
  <text x="622" y="96" fill="#8b949e" font-family="'Segoe UI', Arial, sans-serif" font-size="14">Counts the contribution calendar</text>
  <text x="622" y="117" fill="#8b949e" font-family="'Segoe UI', Arial, sans-serif" font-size="14">across your account history.</text>
  <text x="622" y="145" fill="#6e7681" font-family="'Segoe UI', Arial, sans-serif" font-size="12">↻ Refreshed daily by GitHub Actions</text>
</svg>
'''


def main() -> int:
    total = get_all_time_contributions()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_svg(total), encoding="utf-8")
    print(f"Updated {OUTPUT} with {total:,} all-time contributions.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # fail the workflow rather than silently writing a stale count
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
