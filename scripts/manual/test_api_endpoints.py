"""
HTTP smoke test for the currently exposed AI-heavy API endpoints.

Notes:
- This script only verifies the endpoints listed below.
- It requires a running local server.
- It uses ASCII-only output so it works in Windows GBK terminals.
"""
from __future__ import annotations

import argparse
import sys

import requests


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test selected English Coach API endpoints.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Server base URL")
    return parser.parse_args()


def test_endpoint(name, method, url, payload=None):
    """Test a single endpoint and return result."""
    try:
        if method == "GET":
            response = requests.get(url, timeout=30)
        else:
            response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 200:
            _ = response.json()
            print(f"[OK] {name}: SUCCESS")
            return True
        else:
            print(f"[FAIL] {name}: FAILED (status {response.status_code})")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"[FAIL] {name}: ERROR - {str(e)[:100]}")
        return False


def main() -> int:
    args = _parse_args()
    base_url = args.base_url.rstrip("/")

    print("=" * 70)
    print("English Coach API Smoke Test - 15 Endpoints")
    print("=" * 70)

    results = []

    # ── Reading Endpoints (9) ──────────────────────────────────────────
    print("\nREADING ENDPOINTS (9)")
    print("-" * 70)

    # 1. Complete Words (TOEFL 2026 NEW)
    results.append(test_endpoint(
        "1. Complete Words",
        "POST",
        f"{base_url}/api/reading/toefl2026/complete-words",
        {"cefr_level": "B2"}
    ))

    # 2. Daily Life (TOEFL 2026 NEW)
    results.append(test_endpoint(
        "2. Daily Life Reading",
        "POST",
        f"{base_url}/api/reading/toefl2026/daily-life",
        {"text_type": "email", "cefr_level": "B2"}
    ))

    # 3. Negative Factual
    results.append(test_endpoint(
        "3. Negative Factual",
        "POST",
        f"{base_url}/api/reading/toefl/negative-factual",
        {"cefr_level": "B2"}
    ))

    # 4. Rhetorical Purpose
    results.append(test_endpoint(
        "4. Rhetorical Purpose",
        "POST",
        f"{base_url}/api/reading/toefl/rhetorical-purpose",
        {"cefr_level": "B2"}
    ))

    # 5. Reference
    results.append(test_endpoint(
        "5. Reference",
        "POST",
        f"{base_url}/api/reading/toefl/reference",
        {"cefr_level": "B2"}
    ))

    # 6. Sentence Simplification
    results.append(test_endpoint(
        "6. Sentence Simplification",
        "POST",
        f"{base_url}/api/reading/toefl/sentence-simplification",
        {"cefr_level": "B2"}
    ))

    # 7. Insert Text
    results.append(test_endpoint(
        "7. Insert Text",
        "POST",
        f"{base_url}/api/reading/toefl/insert-text",
        {"cefr_level": "B2"}
    ))

    # 8. Prose Summary
    results.append(test_endpoint(
        "8. Prose Summary",
        "POST",
        f"{base_url}/api/reading/toefl/prose-summary",
        {"cefr_level": "B2"}
    ))

    # 9. Fill Table
    results.append(test_endpoint(
        "9. Fill Table",
        "POST",
        f"{base_url}/api/reading/toefl/fill-table",
        {"cefr_level": "B2"}
    ))

    # ── Listening Endpoints (1) ────────────────────────────────────────
    print("\nLISTENING ENDPOINTS (1)")
    print("-" * 70)

    # 10. TOEFL Listening by Type
    results.append(test_endpoint(
        "10. TOEFL Listening by Type",
        "POST",
        f"{base_url}/api/listening/toefl/generate-by-type",
        {
            "question_types": ["gist_content", "detail"],
            "dialogue_type": "conversation",
            "cefr_level": "B2"
        }
    ))

    # ── Speaking Endpoints (2) ─────────────────────────────────────────
    print("\nSPEAKING ENDPOINTS (2)")
    print("-" * 70)

    # 11. Listen & Repeat (TOEFL 2026 NEW)
    results.append(test_endpoint(
        "11. Listen & Repeat",
        "POST",
        f"{base_url}/api/speaking/toefl2026/listen-repeat",
        {"cefr_level": "B2", "num_sentences": 7}
    ))

    # 12. Virtual Interview (TOEFL 2026 NEW)
    results.append(test_endpoint(
        "12. Virtual Interview",
        "POST",
        f"{base_url}/api/speaking/toefl2026/virtual-interview",
        {"cefr_level": "B2", "num_questions": 5}
    ))

    # ── Writing Endpoints (3) ──────────────────────────────────────────
    print("\nWRITING ENDPOINTS (3)")
    print("-" * 70)

    # 13. Build Sentence (TOEFL 2026 NEW)
    results.append(test_endpoint(
        "13. Build Sentence",
        "POST",
        f"{base_url}/api/writing/toefl2026/build-sentence",
        {"cefr_level": "B2", "num_tasks": 5}
    ))

    # 14. Write Email (TOEFL 2026 NEW)
    results.append(test_endpoint(
        "14. Write Email",
        "POST",
        f"{base_url}/api/writing/toefl2026/write-email",
        {"cefr_level": "B2"}
    ))

    # 15. Academic Discussion (TOEFL 2026 NEW)
    results.append(test_endpoint(
        "15. Academic Discussion",
        "POST",
        f"{base_url}/api/writing/toefl2026/academic-discussion",
        {"cefr_level": "B2"}
    ))

    # ── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    print(f"Success Rate: {passed/total*100:.1f}%")

    if passed == total:
        print("\n[OK] All listed endpoints returned 200.")
    else:
        print(f"\n[WARN] {total - passed} endpoints need attention.")

    return 0 if passed == total else 1

if __name__ == "__main__":
    print("Make sure the server is running first: python -m gui.main")
    raise SystemExit(main())
