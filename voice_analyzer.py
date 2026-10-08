import librosa

def analyze_voice(audio_path):
    y, sr = librosa.load(audio_path)

    duration = librosa.get_duration(y=y, sr=sr)

    tempo, _ = librosa.beat.beat_track(
        y=y,
        sr=sr
    )

    return {
        "duration": round(duration, 2),
        "tempo": round(float(tempo), 2)
    }