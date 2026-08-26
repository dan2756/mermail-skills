#!/usr/bin/env python3
"""Extract a trial/renewal brief from a raw email text file. Untrusted data in, JSON out."""
from __future__ import annotations

import json, re, sys
from pathlib import Path

VENDOR_HINTS = [
    ("notion", "Notion"),
    ("figma", "Figma"),
    ("slack", "Slack"),
    ("github", "GitHub"),
    ("linear", "Linear"),
    ("vercel", "Vercel"),
    ("openai", "OpenAI"),
    ("cursor", "Cursor"),
    ("stripe", "Stripe"),
]

TRIAL_MARKERS = re.compile(
    r"trial ending|trial ends|free trial|trial expires|auto-?renew|renews on|"
    r"subscription will renew|your trial",
    re.I,
)
AMOUNT = re.compile(r"(?:usd|usdc|\$)\s*([0-9]+(?:\.[0-9]{1,2})?)|([0-9]+(?:\.[0-9]{1,2})?)\s*(?:usd|usdc)", re.I)
DATE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2}(?:,?\s*\d{4})?|\d{4}-\d{2}-\d{2}",
    re.I,
)
URL = re.compile(r"https?://([^/\s]+)", re.I)
OTP = re.compile(r"\b(one[- ]time (code|password)|verification code|security code)\b", re.I)


def vendor_from(text: str) -> str | None:
    low = text.lower()
    for needle, name in VENDOR_HINTS:
        if needle in low:
            return name
    m = re.search(r"^From:\s*.*@([A-Za-z0-9.-]+)", text, re.M)
    if m:
        host = m.group(1).lower().split(".")
        if len(host) >= 2:
            return host[-2].title()
    return None


def extract(text: str) -> dict:
    if OTP.search(text) and not TRIAL_MARKERS.search(text):
        return {"action": "skip", "reason": "otp_or_verification_not_trial"}
    if not TRIAL_MARKERS.search(text):
        return {"action": "skip", "reason": "no trial/renewal markers"}

    am = AMOUNT.search(text)
    amount = None
    currency = None
    if am:
        amount = am.group(1) or am.group(2)
        currency = "USD"
    dm = DATE.search(text)
    url_host = None
    um = URL.search(text)
    if um:
        url_host = um.group(1).lower()
        if url_host.startswith("www."):
            url_host = url_host[4:]

    vendor = vendor_from(text)
    evidence = []
    tm = TRIAL_MARKERS.search(text)
    if tm:
        evidence.append(tm.group(0))
    if dm:
        evidence.append(dm.group(0))
    if amount:
        evidence.append(f"{amount} {currency}")

    missing = [k for k, v in (("vendor", vendor), ("date", dm), ("amount", amount)) if not v]
    action = "ask"
    confidence = "high" if not missing else ("medium" if len(missing) == 1 else "low")

    return {
        "vendor": vendor,
        "kind": "trial_ending",
        "ends_on": dm.group(0) if dm else None,
        "amount": amount,
        "currency": currency,
        "cancel_url_host": url_host,
        "payee_present": False,
        "action": action,
        "confidence": confidence,
        "evidence": evidence,
        "missing": missing,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: extract_trial.py <email.txt>", file=sys.stderr)
        return 2
    text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    print(json.dumps(extract(text), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
