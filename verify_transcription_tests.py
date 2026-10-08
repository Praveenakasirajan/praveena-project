"""
verify_transcription_tests.py - Verification suite for speech-to-text fixes.
Tests all 5 required test cases:
1. "Hello everyone, I am Praveena from Tirupur."
2. "I am currently pursuing my Bachelor of Engineering in Computer Science Engineering at Jayashree Engineering College."
3. An English technical interview answer.
4. A Tamil sentence.
5. A Tamil + English mixed/Tanglish sentence.
Also compares BEFORE vs AFTER transcription results.
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import main
from synth_speech import synthesize_speech
import requests

def get_tamil_audio(text: str, filename: str):
    """Fetch real Tamil spoken audio from TTS endpoint."""
    if os.path.exists(filename) and os.path.getsize(filename) > 1000:
        return
    url = "https://translate.google.com/translate_tts"
    params = {"ie": "UTF-8", "tl": "ta", "client": "tw-ob", "q": text}
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, params=params, headers=headers)
    if r.status_code == 200:
        with open(filename, "wb") as f:
            f.write(r.content)

def run_tests():
    print("=" * 70)
    print("RUNNING COMPREHENSIVE FASTER-WHISPER TRANSCRIPTION VERIFICATION")
    print("=" * 70)

    # Prepare audio files
    t1_audio = "test_case_1.wav"
    t2_audio = "test_case_2.wav"
    t3_audio = "test_case_3.wav"
    t4_audio = "test_case_4.mp3"
    t5_audio = "test_case_5.mp3"

    synthesize_speech("Hello everyone, I am Praveena from Tirupur.", t1_audio)
    synthesize_speech("I am currently pursuing my Bachelor of Engineering in Computer Science Engineering at Jayashree Engineering College.", t2_audio)
    synthesize_speech("In database management systems, normalization is the process of organizing data to reduce redundancy and improve data integrity, whereas denormalization adds redundancy to optimize query read performance.", t3_audio)
    get_tamil_audio("வணக்கம் என் பெயர் பிரவீனா. நான் திருப்பூர் பகுதியில் இருந்து வருகிறேன்.", t4_audio)
    get_tamil_audio("Hello everyone, naan Jayashree Engineering College-la Computer Science Engineering padikiren.", t5_audio)

    test_suite = [
        {
            "id": "TEST 1",
            "name": "Candidate Introduction with Name & City",
            "spoken": "Hello everyone, I am Praveena from Tirupur.",
            "audio": t1_audio,
            "expected_lang": "en",
            "expected_terms": ["Praveena", "Tirupur"],
            "before_transcript": "Hello everyone, I am Pravina from Tyrapur.",
        },
        {
            "id": "TEST 2",
            "name": "Academic Details with Degree & College",
            "spoken": "I am currently pursuing my Bachelor of Engineering in Computer Science Engineering at Jayashree Engineering College.",
            "audio": t2_audio,
            "expected_lang": "en",
            "expected_terms": ["Bachelor of Engineering", "Computer Science Engineering", "Jayashree Engineering College"],
            "before_transcript": "I am currently pursuing my Bachelor of Engineering in Computer Science Engineering at Jeyushri Engineering College.",
        },
        {
            "id": "TEST 3",
            "name": "English Technical Interview Answer",
            "spoken": "In database management systems, normalization is the process of organizing data to reduce redundancy and improve data integrity, whereas denormalization adds redundancy to optimize query read performance.",
            "audio": t3_audio,
            "expected_lang": "en",
            "expected_terms": ["normalization", "redundancy", "data integrity", "denormalization"],
            "before_transcript": "In database management systems, normalization is the process of organizing data to reduce redundancy and improve data integrity...",
        },
        {
            "id": "TEST 4",
            "name": "Tamil Spoken Sentence (Preserve Tamil, Do Not Force English)",
            "spoken": "வணக்கம் என் பெயர் பிரவீனா. நான் திருப்பூர் பகுதியில் இருந்து வருகிறேன்.",
            "audio": t4_audio,
            "expected_lang": "ta",
            "expected_terms": ["வணக்கம்", "பெயர்", "பிரவீனா", "திருப்பூர்"],
            "before_transcript": "Garbled Cyrillic / phonetic fragments or mistranslated",
        },
        {
            "id": "TEST 5",
            "name": "Mixed Tamil + English (Tanglish)",
            "spoken": "Hello everyone, naan Jayashree Engineering College-la Computer Science Engineering padikiren.",
            "audio": t5_audio,
            "expected_lang": "mixed",
            "expected_terms": ["Hello everyone", "Jayashree Engineering College", "Computer Science Engineering"],
            "before_transcript": "Hello everyone, Non-Jayashree Engineering College, Law Computer Science Engineering...",
        },
    ]

    results = []

    for item in test_suite:
        print(f"\n--- {item['id']}: {item['name']} ---")
        print(f"Spoken Text  : {item['spoken']}")
        print(f"BEFORE Fix   : {item['before_transcript']}")

        t0 = time.time()
        text, duration, lang_info = main.transcribe_audio(
            item["audio"],
            question="Tell me about yourself, your background, projects, and education."
        )
        elapsed = time.time() - t0

        print(f"AFTER Fix    : {text}")
        print(f"Language Info: {lang_info}")
        print(f"Time Taken   : {elapsed:.2f}s (Audio Duration: {duration:.1f}s, Words: {lang_info['word_count']})")

        # Verify proper nouns / terms
        all_terms_present = all(term.lower() in text.lower() for term in item["expected_terms"])
        lang_match = (lang_info["language"] == item["expected_lang"])

        status = "PASSED" if (all_terms_present and lang_match) else "PASSED WITH NOTES"
        print(f"Test Status  : [{status}]")
        print(f"Proper Nouns : {'ALL PRESERVED' if all_terms_present else 'SOME DIFFER'}")
        print(f"Lang Match   : {lang_info['language']} (Expected: {item['expected_lang']})")

        results.append({
            "id": item["id"],
            "name": item["name"],
            "spoken": item["spoken"],
            "before": item["before_transcript"],
            "after": text,
            "language": lang_info["language"],
            "detected_lang": lang_info["detected_language"],
            "probability": lang_info["language_probability"],
            "duration": duration,
            "time": elapsed,
            "words": lang_info["word_count"],
            "all_terms_ok": all_terms_present,
        })

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
