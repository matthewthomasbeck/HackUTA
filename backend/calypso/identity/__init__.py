"""Identity: face prints, voiceprints, and the face-first/voice-second fusion rule."""


class ModelUnavailable(RuntimeError):
    """A model file is missing or failed to load. Callers degrade safely (no match)."""
