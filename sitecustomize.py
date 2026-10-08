try:
    import mediapipe as mp
    from mediapipe_compat import ensure_mediapipe_solutions_compat
    ensure_mediapipe_solutions_compat(mp)
except Exception:
    pass

try:
    import av
    _orig_av_open = av.open
    def _compat_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _compat_av_open
except Exception:
    pass
