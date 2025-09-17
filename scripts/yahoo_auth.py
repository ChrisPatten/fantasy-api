#!/usr/bin/env python3
"""Yahoo OAuth helper script.

This script guides you through creating/refreshing Yahoo OAuth2 tokens
and writes them to a JSON file (default: oauth2.json).

It respects corporate TLS settings via the standard Requests env vars:
  - SSL_CERT_FILE
  - REQUESTS_CA_BUNDLE

Usage:
  python scripts/yahoo_auth.py --client-secret client_secret.json --output oauth2.json

Prereqs:
  pip install yahoo-oauth requests

Note:
  If your network uses TLS inspection with a self-signed corporate CA,
  set SSL_CERT_FILE/REQUESTS_CA_BUNDLE to a bundle that includes your CA.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import json
from typing import Optional

import requests


def tls_sanity_check(url: str = "https://api.login.yahoo.com") -> None:
    """Perform a simple HTTPS request to validate TLS/CA trust.

    We only care that certificate verification succeeds; HTTP 4xx/5xx
    (e.g., 429 Too Many Requests) are acceptable for this preflight.

    Raises:
        requests.exceptions.SSLError: if certificate validation fails.
    """
    try:
        resp = requests.get(url, timeout=10)
        # Any status code means TLS handshake succeeded; don't raise.
        _ = resp.status_code  # noqa: F841
    except requests.exceptions.SSLError:
        raise
    except requests.RequestException:
        # Network hiccups/timeouts shouldn't block the auth flow; continue.
        return


def run_oauth(client_secret_path: Path, output_path: Path) -> None:
    """Run yahoo-oauth flow and write tokens to output_path."""
    try:
        # Import inside to avoid hard dependency if user only wants TLS check.
        from yahoo_oauth import OAuth2  # type: ignore
    except Exception as exc:  # pragma: no cover
        print("error: yahoo-oauth is not installed. Run: pip install yahoo-oauth", file=sys.stderr)
        raise SystemExit(2) from exc

    # yahoo-oauth writes tokens back to the same file given via `from_file`.
    # To keep client credentials separate, copy client_secret to the desired
    # output path first, then run using `from_file=output_path`.
    try:
        with client_secret_path.open("r", encoding="utf-8") as f:
            creds = json.load(f)
    except Exception as e:
        print(f"error: failed to read client secret JSON: {e}", file=sys.stderr)
        raise SystemExit(2)

    if not isinstance(creds, dict) or not creds.get("consumer_key") or not creds.get("consumer_secret"):
        print("error: client secret JSON must contain keys: consumer_key, consumer_secret", file=sys.stderr)
        raise SystemExit(2)

    # Ensure the output file exists with the base credentials.
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump({
                "consumer_key": creds["consumer_key"],
                "consumer_secret": creds["consumer_secret"],
            }, f, indent=2)
    except Exception as e:
        print(f"error: failed to write seed output file: {e}", file=sys.stderr)
        raise SystemExit(2)

    oauth = OAuth2(None, None, from_file=str(output_path))
    # This will drive interactive flow as needed
    if not oauth.token_is_valid():
        oauth.refresh_access_token()
    # Tokens are now persisted back to `output_path` by yahoo-oauth itself.


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Yahoo OAuth helper")
    parser.add_argument(
        "--client-secret",
        default="client_secret.json",
        help="Path to Yahoo client secret JSON (default: client_secret.json)",
    )
    parser.add_argument(
        "--output",
        default="oauth2.json",
        help="Path to write OAuth tokens JSON (default: oauth2.json)",
    )
    parser.add_argument(
        "--skip-tls-check",
        action="store_true",
        help="Skip the preflight HTTPS TLS sanity check (not recommended)",
    )
    args = parser.parse_args(argv)

    client_secret = Path(args.client_secret).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    if not client_secret.exists():
        print(f"error: client secret file not found: {client_secret}", file=sys.stderr)
        return 2

    # Show TLS-related env to aid debugging on managed devices
    ssl_cert_file = os.getenv("SSL_CERT_FILE")
    requests_ca_bundle = os.getenv("REQUESTS_CA_BUNDLE")
    if ssl_cert_file:
        print(f"SSL_CERT_FILE={ssl_cert_file}")
    if requests_ca_bundle:
        print(f"REQUESTS_CA_BUNDLE={requests_ca_bundle}")

    if not args.skip_tls_check:
        try:
            tls_sanity_check()
        except requests.exceptions.SSLError as e:
            print(
                "TLS verification failed talking to Yahoo.\n"
                "Ensure your corporate CA is appended to a cert bundle and set:\n"
                "  export SSL_CERT_FILE=/path/to/corp-bundle.pem\n"
                "  export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE\n"
                "Then rerun this script.",
                file=sys.stderr,
            )
            print(f"details: {e}", file=sys.stderr)
            return 1
        except requests.RequestException as e:
            print(f"network error: {e}", file=sys.stderr)
            return 1

    try:
        run_oauth(client_secret, output)
    except requests.exceptions.SSLError as e:
        print(
            "TLS verification failed during token request. See guidance above.",
            file=sys.stderr,
        )
        print(f"details: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # pragma: no cover
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"Saved tokens to {output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
