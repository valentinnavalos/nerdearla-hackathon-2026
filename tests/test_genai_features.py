"""Guards against google-genai versions without the Live fields the engines rely on (T1.2)."""

from google.genai import types


def test_translation_config_exists():
    assert {"target_language_code", "echo_target_language"} <= set(types.TranslationConfig.model_fields)


def test_audio_transcription_config_fields():
    assert {"custom_vocabulary", "mode"} <= set(types.AudioTranscriptionConfig.model_fields)


def test_interim_input_transcription_field():
    assert "interim_input_transcription" in types.LiveServerContent.model_fields
