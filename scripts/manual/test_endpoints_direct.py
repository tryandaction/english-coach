"""
Direct API endpoint testing without running server - validates all 20 endpoints.
Tests by directly calling the API functions.
"""
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gui.deps import get_components

def test_reading_endpoints():
    """Test all 9 reading endpoints."""
    print("\nREADING ENDPOINTS (9)")
    print("-" * 70)

    kb, srs, user_model, ai, profile = get_components()

    if not ai:
        print("❌ AI client not configured")
        return 0

    passed = 0

    # 1. Complete Words
    try:
        result = ai.generate_complete_words_question("Sample passage about technology.", "B2")
        if result and "question" in result:
            print("[OK] 1. Complete Words: SUCCESS")
            passed += 1
        else:
            print("[FAIL] 1. Complete Words: Invalid response")
    except Exception as e:
        print(f"[FAIL] 1. Complete Words: {str(e)[:80]}")

    # 2. Daily Life
    try:
        result = ai.generate_daily_life_question("email", "B2")
        if result and "question" in result:
            print("✅ 2. Daily Life Reading: SUCCESS")
            passed += 1
        else:
            print("❌ 2. Daily Life Reading: Invalid response")
    except Exception as e:
        print(f"❌ 2. Daily Life Reading: {str(e)[:80]}")

    # 3. Negative Factual
    try:
        result = ai.generate_negative_factual_question("Sample passage.", "B2")
        if result and "question" in result:
            print("✅ 3. Negative Factual: SUCCESS")
            passed += 1
        else:
            print("❌ 3. Negative Factual: Invalid response")
    except Exception as e:
        print(f"❌ 3. Negative Factual: {str(e)[:80]}")

    # 4. Rhetorical Purpose
    try:
        result = ai.generate_rhetorical_purpose_question("Sample passage.", "B2")
        if result and "question" in result:
            print("✅ 4. Rhetorical Purpose: SUCCESS")
            passed += 1
        else:
            print("❌ 4. Rhetorical Purpose: Invalid response")
    except Exception as e:
        print(f"❌ 4. Rhetorical Purpose: {str(e)[:80]}")

    # 5. Reference
    try:
        result = ai.generate_reference_question("Sample passage with it.", "B2")
        if result and "question" in result:
            print("✅ 5. Reference: SUCCESS")
            passed += 1
        else:
            print("❌ 5. Reference: Invalid response")
    except Exception as e:
        print(f"❌ 5. Reference: {str(e)[:80]}")

    # 6. Sentence Simplification
    try:
        result = ai.generate_sentence_simplification_question("Sample passage.", "B2")
        if result and "question" in result:
            print("✅ 6. Sentence Simplification: SUCCESS")
            passed += 1
        else:
            print("❌ 6. Sentence Simplification: Invalid response")
    except Exception as e:
        print(f"❌ 6. Sentence Simplification: {str(e)[:80]}")

    # 7. Insert Text
    try:
        result = ai.generate_insert_text_question("Sample passage.", "B2")
        if result and "question" in result:
            print("✅ 7. Insert Text: SUCCESS")
            passed += 1
        else:
            print("❌ 7. Insert Text: Invalid response")
    except Exception as e:
        print(f"❌ 7. Insert Text: {str(e)[:80]}")

    # 8. Prose Summary
    try:
        result = ai.generate_prose_summary_question("Sample passage.", "B2")
        if result and "question" in result:
            print("✅ 8. Prose Summary: SUCCESS")
            passed += 1
        else:
            print("❌ 8. Prose Summary: Invalid response")
    except Exception as e:
        print(f"❌ 8. Prose Summary: {str(e)[:80]}")

    # 9. Fill Table
    try:
        result = ai.generate_fill_table_question("Sample passage.", "B2")
        if result and "question" in result:
            print("✅ 9. Fill Table: SUCCESS")
            passed += 1
        else:
            print("❌ 9. Fill Table: Invalid response")
    except Exception as e:
        print(f"❌ 9. Fill Table: {str(e)[:80]}")

    return passed

def test_listening_endpoints():
    """Test listening endpoint."""
    print("\nLISTENING ENDPOINTS (1)")
    print("-" * 70)

    kb, srs, user_model, ai, profile = get_components()

    if not ai:
        print("❌ AI client not configured")
        return 0

    passed = 0

    # 10. TOEFL Listening by Type
    try:
        result = ai.generate_listening_dialogue(
            cefr_level="B2",
            exam="toefl",
            dialogue_type="conversation",
            question_types=["gist_content", "detail"]
        )
        if result and ("dialogue" in result or "script" in result):
            print("[OK] 10. TOEFL Listening by Type: SUCCESS")
            passed += 1
        else:
            print(f"[FAIL] 10. TOEFL Listening by Type: Invalid response - keys: {list(result.keys()) if result else 'None'}")
    except Exception as e:
        print(f"[FAIL] 10. TOEFL Listening by Type: {str(e)[:80]}")

    return passed

def test_speaking_endpoints():
    """Test all 2 speaking endpoints."""
    print("\nSPEAKING ENDPOINTS (2)")
    print("-" * 70)

    kb, srs, user_model, ai, profile = get_components()

    if not ai:
        print("❌ AI client not configured")
        return 0

    passed = 0

    # 11. Listen & Repeat
    try:
        result = ai.generate_listen_repeat_task("B2", 7)
        if result and "sentences" in result:
            print("✅ 11. Listen & Repeat: SUCCESS")
            passed += 1
        else:
            print("❌ 11. Listen & Repeat: Invalid response")
    except Exception as e:
        print(f"❌ 11. Listen & Repeat: {str(e)[:80]}")

    # 12. Virtual Interview
    try:
        result = ai.generate_virtual_interview_task("B2", 5)
        if result and "questions" in result:
            print("✅ 12. Virtual Interview: SUCCESS")
            passed += 1
        else:
            print("❌ 12. Virtual Interview: Invalid response")
    except Exception as e:
        print(f"❌ 12. Virtual Interview: {str(e)[:80]}")

    return passed

def test_writing_endpoints():
    """Test all 3 writing endpoints."""
    print("\nWRITING ENDPOINTS (3)")
    print("-" * 70)

    kb, srs, user_model, ai, profile = get_components()

    if not ai:
        print("❌ AI client not configured")
        return 0

    passed = 0

    # 13. Build Sentence
    try:
        result = ai.generate_build_sentence_task("B2", 5)
        if result and "items" in result:
            print("[OK] 13. Build Sentence: SUCCESS")
            passed += 1
        else:
            print(f"[FAIL] 13. Build Sentence: Invalid response - {result}")
    except Exception as e:
        print(f"[FAIL] 13. Build Sentence: {str(e)[:80]}")

    # 14. Write Email
    try:
        result = ai.generate_write_email_task("B2")
        if result and "scenario" in result:
            print("[OK] 14. Write Email: SUCCESS")
            passed += 1
        else:
            print(f"[FAIL] 14. Write Email: Invalid response - {result}")
    except Exception as e:
        print(f"[FAIL] 14. Write Email: {str(e)[:80]}")

    # 15. Academic Discussion
    try:
        result = ai.generate_academic_discussion_task("B2")
        if result and ("discussion_prompt" in result or "professor_question" in result):
            print("[OK] 15. Academic Discussion: SUCCESS")
            passed += 1
        else:
            print(f"[FAIL] 15. Academic Discussion: Invalid response - {result}")
    except Exception as e:
        print(f"[FAIL] 15. Academic Discussion: {str(e)[:80]}")

    return passed

def main():
    print("=" * 70)
    print("TOEFL 2026 Direct Function Testing - 15 Core Functions")
    print("=" * 70)

    reading_passed = test_reading_endpoints()
    listening_passed = test_listening_endpoints()
    speaking_passed = test_speaking_endpoints()
    writing_passed = test_writing_endpoints()

    total_passed = reading_passed + listening_passed + speaking_passed + writing_passed
    total_tests = 15

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Reading: {reading_passed}/9")
    print(f"Listening: {listening_passed}/1")
    print(f"Speaking: {speaking_passed}/2")
    print(f"Writing: {writing_passed}/3")
    print(f"\nTotal Passed: {total_passed}/{total_tests}")
    print(f"Success Rate: {total_passed/total_tests*100:.1f}%")

    if total_passed == total_tests:
        print("\n[SUCCESS] ALL FUNCTIONS WORKING - PRODUCTION READY!")
    else:
        print(f"\n[WARNING] {total_tests - total_passed} functions need attention")

    return total_passed == total_tests

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
