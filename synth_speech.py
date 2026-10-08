"""
Generate synthetic speech WAV files using Windows SAPI/SpeechSynthesizer for testing.
"""
import os
import subprocess
from pathlib import Path


def synthesize_speech(text: str, output_path: str):
    ps1_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile("{Path(output_path).resolve()}")
$synth.Speak("{text}")
$synth.Dispose()
"""
    script_path = Path("temp_synth.ps1")
    script_path.write_text(ps1_script, encoding="utf-8")
    try:
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            check=True,
            capture_output=True,
        )
    finally:
        if script_path.exists():
            script_path.unlink()


if __name__ == "__main__":
    synthesize_speech("Hello world, this is a test.", "test_out.wav")
    print("Created test_out.wav, exists:", os.path.exists("test_out.wav"))
    if os.path.exists("test_out.wav"):
        print("Size:", os.path.getsize("test_out.wav"))
