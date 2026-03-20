English Coach v2.0
==================

This package is prepared for local testing of the Open Source edition.

Recommended test order
----------------------

1. Start the app
2. Complete Setup
3. Check Home and today's coach plan
4. Test Vocabulary / Grammar / Reading / Listening
5. Check Progress and History after one finished session
6. Add your own API key if you want to test Chat / Writing / Speaking

Recommended release check
-------------------------

Run:

`python scripts/smoke_test_release.py --keep-temp`

This verifies:

- portable exe startup
- setup installer startup
- first-run Setup
- offline Reading / Listening completion
- Home / Progress / History writeback after real sessions

Notes
-----

- No real API key is shipped in this release.
- User data should stay outside the release package.
- If you do not configure AI, the offline learning path should still work.
- Coach tasks can jump directly into real training pages.
