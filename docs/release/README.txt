English Coach Desktop - Release Notes
=====================================

This release note file is shared by both desktop editions.

What you can test without any API key
-------------------------------------

- Vocabulary / Word Books / SRS
- Grammar
- Reading offline flow
- Listening built-in flow with question-type aware routing
- Home / Progress / History
- Daily coach plan and local reminder flow
- Long-term learner memory and review continuity
- Practice recommendation and chat memory context

Release smoke
-------------

- Rebuild artifacts first with `python build_opensource.py`
- This updates the exe, setup installer, and zip bundle together
- Portable exe startup is covered by the release smoke script
- Setup installer startup is also covered
- First launch Setup, offline Reading, offline Listening, and result writeback are all verified
- Memory continuity after restart should also be checked
- Chat explicit-memory and recommendation APIs should also be checked
- Run `python scripts/smoke_test_release.py --keep-temp` before publishing a new release

What needs AI access
--------------------

- Chat
- Writing feedback
- Speaking scoring

In Open Source, this means your own API key.
In Cloud, this can come from License activation or your own API key.

Supported providers
-------------------

- DeepSeek
- OpenAI
- Anthropic
- Qwen / DashScope

Important limits
----------------

1. This is not a full commercial exam-prep platform.
2. Mock Exam is still a section-flow experience, not a unified scoring system.
3. Writing and Speaking quality feedback still depend on AI.
4. Content quality is improving, but should not be presented as final or exhaustive.
5. Memory continuity exists, but a dedicated memory management page is not yet included.
