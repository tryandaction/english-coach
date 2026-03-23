English Coach v2.0
==================

This package is prepared for local testing of the desktop editions.

- `english-coach-opensource*` = Open Source edition
- `english-coach-cloud*` = Cloud edition

Recommended test order
----------------------

1. Start the app
2. Complete Setup
3. Check Home and today's coach plan
4. Test Vocabulary / Grammar / Reading / Listening
5. Check Progress and History after one finished session
6. Add your own API key if you want to test Chat / Writing / Speaking
7. If this is a Cloud build with activation settings, test License activation too

Recommended release check
-------------------------

Run:

`python build_opensource.py`

This rebuilds:

- `english-coach-opensource.exe`
- `english-coach-opensource-setup.exe`
- `english-coach-v2.0.0-opensource.zip`

Then run:

`python scripts/smoke_test_release.py --keep-temp`

This verifies:

- portable exe startup
- setup installer startup
- first-run Setup
- offline Reading / Listening completion
- Home / Progress / History writeback after real sessions
- clean smoke exit without leftover `english-coach-opensource` processes

Notes
-----

- No real API key is shipped in this release.
- User data should stay outside the release package.
- If you do not configure AI, the offline learning path should still work.
- Coach tasks can jump directly into real training pages.
