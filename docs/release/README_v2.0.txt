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
8. Restart once and confirm coach continuity and review counts still remain
9. In Chat, try explicit or auto learner-memory actions and verify the next session still sees them

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
- single-instance protection for repeated launch
- first-run Setup
- offline Reading / Listening completion
- Home / Progress / History writeback after real sessions
- memory and review continuity after restart
- chat memory context and practice recommendation endpoints
- Start Menu shortcut target after install
- Desktop shortcut target after install
- clean smoke exit without leftover `english-coach-opensource` processes

Notes
-----

- No real API key is shipped in this release.
- User data should stay outside the release package.
- If you do not configure AI, the offline learning path should still work.
- Coach tasks can jump directly into real training pages.
- Long-term learner memory now includes profile continuity, vocab state, and heartbeat signals.
- With AI configured, Chat can now read learner context and explicitly write learner facts / word states.
- User word books now support visible post-add editing directly from each word row via an `Edit` action.
- Installer upgrades now use a single replace-old-version choice instead of repeated confirmation popups.
