from __future__ import annotations

import argparse
import json
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path

try:
    import msvcrt
except ImportError:
    msvcrt = None

import numpy as np
import pyaudio
from faster_whisper import WhisperModel

DEFAULT_DOWNLOAD_ROOT = Path("models") / "faster_whisper"
DEFAULT_PROFILE = "manual-small"
DEFAULT_CORRECTIONS_PATH = Path("config") / "live_stt_corrections.json"
MANUAL_SEGMENT_SEC = 3.2
MANUAL_SEGMENT_OVERLAP_SEC = 1.0
MANUAL_SEGMENT_MIN_SEC = 0.60
MANUAL_LONG_RECORDING_SEC = 5.5
DEFAULT_TARGETED_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bаликс\b", "Алекс"),
    (r"\bалис\b", "Алекс"),
    (r"\bалиц\b", "Алекс"),
    (r"\bтимас\b", "дела"),
    (r"\bвоспредведения\b", "воспроизведения"),
    (r"\bвоспредъявить\b", "воспроизвести"),
    (r"\bиспознательная\b", "распознавания"),
    (r"\bтвой дела\b", "твои дела"),
    (r"\bтвоей дела\b", "твои дела"),
    (r"\bкак твой\b", "как твои"),
)


def _pick_input_device(p: pyaudio.PyAudio, preferred: int | None) -> tuple[int, str]:
    if preferred is not None:
        info = p.get_device_info_by_index(preferred)
        if int(info.get("maxInputChannels", 0)) <= 0:
            raise RuntimeError(f"Device {preferred} has no input channels")
        return preferred, str(info.get("name", "unknown"))

    try:
        info = p.get_default_input_device_info()
        idx = int(info["index"])
        return idx, str(info.get("name", "unknown"))
    except Exception:
        pass

    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if int(info.get("maxInputChannels", 0)) > 0:
            return i, str(info.get("name", "unknown"))
    raise RuntimeError("No input audio devices found")


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("unicode_escape").decode("ascii"))


def _match_case(sample: str, replacement: str) -> str:
    if sample.isupper():
        return replacement.upper()
    if sample[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement.lower()


def _load_targeted_replacements(path: Path) -> tuple[tuple[str, str], ...]:
    if not path.exists():
        return DEFAULT_TARGETED_REPLACEMENTS

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _safe_print(f"Corrections file load failed for '{path}': {exc}")
        return DEFAULT_TARGETED_REPLACEMENTS

    entries = payload.get("replacements")
    if not isinstance(entries, list):
        _safe_print(f"Corrections file '{path}' has invalid format, using defaults")
        return DEFAULT_TARGETED_REPLACEMENTS

    loaded: list[tuple[str, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        pattern = item.get("pattern")
        replacement = item.get("replacement")
        if isinstance(pattern, str) and isinstance(replacement, str) and pattern and replacement:
            loaded.append((pattern, replacement))

    return tuple(loaded) if loaded else DEFAULT_TARGETED_REPLACEMENTS


def _apply_targeted_post_corrections(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    corrected = " ".join(text.split())
    for pattern, replacement in replacements:
        corrected = re.sub(
            pattern,
            lambda match: _match_case(match.group(0), replacement),
            corrected,
            flags=re.IGNORECASE,
        )

    words = corrected.split()
    deduped: list[str] = []
    for word in words:
        normalized = re.sub(r"[^\wа-яА-ЯёЁ-]+", "", word).lower()
        previous = re.sub(r"[^\wа-яА-ЯёЁ-]+", "", deduped[-1]).lower() if deduped else None
        if normalized and normalized == previous:
            continue
        deduped.append(word)

    corrected = " ".join(deduped)
    corrected = re.sub(r"\s+([,.;:!?])", r"\1", corrected)
    return corrected.strip()


def _normalized_merge_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for word in text.split():
        normalized = re.sub(r"[^\wа-яА-ЯёЁ-]+", "", word).lower()
        if normalized:
            tokens.append(normalized)
    return tokens


def _normalize_audio(audio_i16: np.ndarray, boost: float, target_rms: float) -> np.ndarray:
    audio = audio_i16.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(audio**2))) if audio.size else 0.0
    gain = float(boost)
    if rms > 1e-6:
        gain = min(gain, target_rms / rms)
    boosted = np.clip(audio * gain, -1.0, 1.0)
    return boosted.astype(np.float32)


def _speech_band_ratio(audio_i16: np.ndarray, rate: int) -> float:
    if audio_i16.size == 0:
        return 0.0

    audio = audio_i16.astype(np.float32)
    if not np.any(audio):
        return 0.0

    window = np.hanning(audio.size).astype(np.float32)
    spectrum = np.fft.rfft(audio * window)
    power = np.abs(spectrum) ** 2
    if not np.any(power):
        return 0.0

    freqs = np.fft.rfftfreq(audio.size, d=1.0 / rate)
    speech_mask = (freqs >= 180.0) & (freqs <= 3800.0)
    total_energy = float(power.sum())
    speech_energy = float(power[speech_mask].sum())
    return speech_energy / total_energy if total_energy > 0 else 0.0


def _calibrate_noise_floor(stream, *, chunk: int, calibrate_sec: float) -> float:
    if calibrate_sec <= 0:
        return 0.0

    _safe_print(f"Calibrating noise floor for {calibrate_sec:.1f}s. Keep silent.")
    rms_values: list[float] = []
    deadline = time.perf_counter() + calibrate_sec
    while time.perf_counter() < deadline:
        data = stream.read(chunk, exception_on_overflow=False)
        arr = np.frombuffer(data, dtype=np.int16)
        audio = arr.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio**2))) if audio.size else 0.0
        rms_values.append(rms)

    if not rms_values:
        return 0.0
    rms_values = sorted(rms_values)
    keep_count = max(1, int(len(rms_values) * 0.7))
    trimmed = rms_values[:keep_count]
    return float(np.median(trimmed))


def _looks_like_hallucination(text: str, avg_logprob: float, *, manual_mode: bool = False) -> bool:
    cleaned = " ".join(text.strip().split()).lower()
    if not cleaned:
        return True
    avg_logprob_threshold = -0.90 if manual_mode else -0.25
    if avg_logprob < avg_logprob_threshold:
        return True

    blocked_substrings = (
        "редактор субтитров",
        "корректор",
        "субтитры",
    )
    if any(part in cleaned for part in blocked_substrings):
        return True

    words = re.findall(r"[a-zа-я0-9]+", cleaned)
    if not words:
        return True
    allowed_short_phrases = {
        "привет",
        "добрый день",
        "спасибо",
        "проверка связи",
        "меня зовут алекс",
        "что такое тестирование",
    }
    if cleaned in allowed_short_phrases:
        return False

    if len(words) < 3:
        return True
    if len(words) == 3 and avg_logprob < (-0.55 if manual_mode else -0.10):
        return True
    if len(words) >= 6 and len(set(words)) / len(words) < 0.45:
        return True

    repeated_pairs = sum(1 for i in range(len(words) - 1) if words[i] == words[i + 1])
    if repeated_pairs >= 2:
        return True

    return False


def _load_model(
    model_name: str,
    *,
    download_root: Path,
    local_files_only: bool,
) -> tuple[WhisperModel, float]:
    download_root.mkdir(parents=True, exist_ok=True)
    started_at = time.perf_counter()
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        download_root=str(download_root),
        local_files_only=local_files_only,
    )
    return model, time.perf_counter() - started_at


def _warmup_model(
    model_name: str,
    *,
    rate: int,
    download_root: Path,
    local_files_only: bool,
) -> int:
    _safe_print(f"Warming model: {model_name}")
    _safe_print(f"Model cache: {download_root}")
    model, load_sec = _load_model(
        model_name,
        download_root=download_root,
        local_files_only=local_files_only,
    )
    _safe_print(f"Model loaded: {model_name} in {load_sec:.2f}s")

    silence = np.zeros(rate, dtype=np.float32)
    decode_started_at = time.perf_counter()
    segments, _ = model.transcribe(
        silence,
        language="ru",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=1.0,
    )
    list(segments)
    _safe_print(f"Warmup decode complete in {time.perf_counter() - decode_started_at:.2f}s")
    return 0


def _apply_profile_defaults(args: argparse.Namespace) -> argparse.Namespace:
    profiles = {
        "manual-small": {
            "model": "small",
            "manual_mode": True,
            "cafe_mode": True,
            "local_files_only": True,
        },
        "manual-base": {
            "model": "base",
            "manual_mode": True,
            "cafe_mode": True,
            "local_files_only": False,
        },
        "auto-base": {
            "model": "base",
            "manual_mode": False,
            "cafe_mode": False,
            "local_files_only": False,
        },
    }
    selected = profiles[args.profile]
    if args.model is None:
        args.model = selected["model"]
    if args.manual_mode is None:
        args.manual_mode = selected["manual_mode"]
    if args.cafe_mode is None:
        args.cafe_mode = selected["cafe_mode"]
    if args.local_files_only is None:
        args.local_files_only = selected["local_files_only"]
    return args


def _transcribe_phrase(
    *,
    model: WhisperModel,
    audio_i16: np.ndarray,
    rate: int,
    boost: float,
    band_threshold_phrase: float,
    debug_rms: bool,
    last_text: str,
    replacements: tuple[tuple[str, str], ...],
    manual_mode: bool = False,
) -> tuple[str | None, str | None, str | None]:
    audio_f32 = _normalize_audio(audio_i16, boost=boost, target_rms=0.09)
    phrase_band_ratio = _speech_band_ratio(audio_i16, rate)
    effective_band_threshold = min(band_threshold_phrase, 0.35) if manual_mode else band_threshold_phrase

    segments, info = model.transcribe(
        audio_f32,
        language="ru",
        beam_size=5,
        best_of=3,
        patience=1.0,
        repetition_penalty=1.15,
        no_repeat_ngram_size=3,
        temperature=0.0,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.8,
        condition_on_previous_text=False,
        suppress_blank=True,
        suppress_tokens=[-1],
        word_timestamps=True,
        vad_filter=not manual_mode,
        vad_parameters={"min_silence_duration_ms": 350},
        max_new_tokens=48,
        hallucination_silence_threshold=0.15,
    )
    segment_list = list(segments)
    text = _apply_targeted_post_corrections(" ".join([s.text for s in segment_list]).strip(), replacements)
    avg_logprob = (
        sum(float(s.avg_logprob) for s in segment_list) / len(segment_list)
        if segment_list
        else -10.0
    )
    if phrase_band_ratio < effective_band_threshold:
        reason = f"band_ratio={phrase_band_ratio:.2f} < {effective_band_threshold:.2f}"
        if debug_rms and text:
            _safe_print(f"[DROP] {reason} avg_logprob={avg_logprob:.3f} text={text!r}")
        return None, None, reason
    if not text or text == last_text or _looks_like_hallucination(text, avg_logprob, manual_mode=manual_mode):
        if not text:
            reason = "empty transcript"
        elif text == last_text:
            reason = "same as previous text"
        else:
            reason = f"hallucination gate avg_logprob={avg_logprob:.3f}"
        if debug_rms and text:
            _safe_print(f"[DROP] avg_logprob={avg_logprob:.3f} text={text!r}")
        return None, None, reason
    lang = getattr(info, "language", "ru")
    return lang, text, None


def _merge_segment_texts(texts: list[str]) -> str:
    merged: list[str] = []
    for text in texts:
        normalized = " ".join(text.split())
        if not normalized:
            continue
        if not merged:
            merged.append(normalized)
            continue

        prev_words = merged[-1].split()
        curr_words = normalized.split()
        prev_norm = _normalized_merge_tokens(merged[-1])
        curr_norm = _normalized_merge_tokens(normalized)
        overlap = 0
        max_overlap = min(6, len(prev_norm), len(curr_norm))
        for size in range(max_overlap, 0, -1):
            prev_tail = prev_norm[-size:]
            curr_head = curr_norm[:size]
            if prev_tail == curr_head:
                overlap = size
                break

        if overlap > 0:
            tail = " ".join(curr_words[overlap:]).strip()
            if tail:
                merged[-1] = f"{merged[-1]} {tail}".strip()
            continue

        # Skip a segment that is effectively contained in the previous one.
        if curr_norm and len(curr_norm) >= 3:
            prev_joined = " ".join(prev_norm)
            curr_joined = " ".join(curr_norm)
            if curr_joined in prev_joined:
                continue

        if normalized.lower() == merged[-1].lower():
            continue
        merged.append(normalized)

    return " ".join(merged).strip()


def _transcribe_manual_segments(
    *,
    model: WhisperModel,
    audio_i16: np.ndarray,
    rate: int,
    boost: float,
    band_threshold_phrase: float,
    debug_rms: bool,
    last_text: str,
    replacements: tuple[tuple[str, str], ...],
) -> tuple[str | None, str | None, str | None]:
    segment_sec = MANUAL_SEGMENT_SEC
    overlap_sec = MANUAL_SEGMENT_OVERLAP_SEC
    segment_samples = int(rate * segment_sec)
    step_samples = max(1, int(rate * (segment_sec - overlap_sec)))

    texts: list[str] = []
    detected_lang: str | None = None
    last_reason: str | None = None
    previous_segment_text = ""

    for start in range(0, len(audio_i16), step_samples):
        end = min(len(audio_i16), start + segment_samples)
        chunk_audio = audio_i16[start:end]
        if chunk_audio.size < int(rate * MANUAL_SEGMENT_MIN_SEC):
            continue
        lang, text, reason = _transcribe_phrase(
            model=model,
            audio_i16=chunk_audio,
            rate=rate,
            boost=boost,
            band_threshold_phrase=band_threshold_phrase,
            debug_rms=debug_rms,
            last_text=previous_segment_text or last_text,
            replacements=replacements,
            manual_mode=True,
        )
        if text:
            texts.append(text)
            detected_lang = detected_lang or lang
            previous_segment_text = text
        elif reason:
            last_reason = reason

        if end >= len(audio_i16):
            break

    merged_text = _merge_segment_texts(texts)
    if merged_text:
        return detected_lang or "ru", merged_text, None
    return None, None, last_reason or "segmented decode produced no accepted text"


def _trim_manual_audio(
    *,
    frames: list[np.ndarray],
    rate: int,
    chunk: int,
    noise_floor: float,
    speech_rms: float,
    band_threshold_start: float,
    focus_mode: bool = True,
    max_manual_sec_override: float | None = None,
) -> tuple[np.ndarray, float, float, str]:
    if not frames:
        return np.array([], dtype=np.int16), 0.0, 0.0, "empty manual frames"

    total_audio = np.concatenate(frames)
    total_duration = total_audio.size / rate
    rms_gate = max(noise_floor * 6.0, min(speech_rms * 0.55, 0.0050), 0.0012)
    band_gate = max(min(band_threshold_start, 0.72), 0.60)

    active_indices: list[int] = []
    rms_values: list[float] = []
    for i, frame in enumerate(frames):
        audio = frame.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio**2))) if audio.size else 0.0
        rms_values.append(rms)
        band_ratio = _speech_band_ratio(frame, rate)
        if rms >= rms_gate and band_ratio >= band_gate:
            active_indices.append(i)

    if not active_indices:
        return total_audio, total_duration, total_duration, "no active speech window"

    # In focused mode keep the strongest contiguous speech span. In wide mode keep
    # a broader active window as a fallback when the focused slice is too short.
    spans: list[tuple[int, int]] = []
    span_start = active_indices[0]
    span_end = active_indices[0]
    max_gap = 2
    for idx in active_indices[1:]:
        if idx - span_end <= max_gap:
            span_end = idx
            continue
        spans.append((span_start, span_end))
        span_start = idx
        span_end = idx
    spans.append((span_start, span_end))

    def _span_score(span: tuple[int, int]) -> tuple[float, int]:
        start_idx, end_idx = span
        score = sum(rms_values[start_idx : end_idx + 1])
        length = end_idx - start_idx + 1
        return score, length

    if focus_mode:
        best_start, best_end = max(spans, key=_span_score)
        pad_chunks = 1
        start = max(0, best_start - pad_chunks)
        end = min(len(frames), best_end + pad_chunks + 1)
        max_manual_sec = 2.4
    else:
        start = max(0, active_indices[0] - 4)
        end = min(len(frames), active_indices[-1] + 5)
        max_manual_sec = 5.8
    if max_manual_sec_override is not None:
        max_manual_sec = max_manual_sec_override

    max_chunks = max(1, int(rate / chunk * max_manual_sec))
    if end - start > max_chunks:
        if focus_mode:
            end = min(len(frames), start + max_chunks)
        else:
            center = (start + end) // 2
            start = max(0, center - max_chunks // 2)
            end = min(len(frames), start + max_chunks)
            start = max(0, end - max_chunks)

    trimmed_audio = np.concatenate(frames[start:end])
    trimmed_duration = trimmed_audio.size / rate
    mode_name = "focused" if focus_mode else "fallback"
    reason = f"{mode_name} trim {total_duration:.2f}s -> {trimmed_duration:.2f}s"
    return trimmed_audio, total_duration, trimmed_duration, reason


def run_live(
    device: int | None,
    model_name: str,
    rate: int,
    chunk: int,
    boost: float,
    speech_rms: float,
    silence_rms: float,
    min_speech_sec: float,
    end_silence_sec: float,
    calibrate_sec: float,
    preroll_sec: float,
    debug_rms: bool,
    cafe_mode: bool,
    band_threshold_start: float,
    band_threshold_hold: float,
    band_threshold_phrase: float,
    manual_mode: bool,
    local_files_only: bool,
    download_root: Path,
    replacements: tuple[tuple[str, str], ...],
) -> None:
    p = pyaudio.PyAudio()
    stream = None
    max_rms_seen = 0.0
    try:
        dev_idx, dev_name = _pick_input_device(p, device)
        safe_name = dev_name.encode("ascii", "ignore").decode("ascii") or dev_name
        _safe_print(f"Device: {dev_idx} - {safe_name}")
        _safe_print(f"Loading model: {model_name}")

        try:
            model, load_sec = _load_model(
                model_name,
                download_root=download_root,
                local_files_only=local_files_only,
            )
            _safe_print(f"Model: {model_name} | load_time={load_sec:.2f}s")
        except Exception as exc:
            fallback = "base"
            _safe_print(f"Model load failed for '{model_name}': {exc}")
            _safe_print(f"Falling back to: {fallback}")
            model, load_sec = _load_model(
                fallback,
                download_root=download_root,
                local_files_only=local_files_only,
            )
            _safe_print(f"Model: {fallback} | load_time={load_sec:.2f}s")

        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=rate,
            input=True,
            input_device_index=dev_idx,
            frames_per_buffer=chunk,
        )

        noise_floor = _calibrate_noise_floor(stream, chunk=chunk, calibrate_sec=calibrate_sec)
        if cafe_mode:
            min_speech_sec = max(min_speech_sec, 0.38)
            end_silence_sec = max(end_silence_sec, 0.85)
            auto_speech_rms = max(noise_floor * 3.2, 0.0075)
            auto_silence_rms = max(noise_floor * 2.1, 0.0045)
            speech_rms = min(max(speech_rms, auto_speech_rms), 0.0200)
            silence_rms = min(max(silence_rms, auto_silence_rms), 0.0120)
            band_threshold_start = max(band_threshold_start, 0.68)
            band_threshold_hold = max(band_threshold_hold, 0.58)
            band_threshold_phrase = max(band_threshold_phrase, 0.62)
        else:
            auto_speech_rms = max(noise_floor * 2.0, 0.0015)
            auto_silence_rms = max(noise_floor * 1.35, 0.0009)
            speech_rms = min(max(speech_rms, auto_speech_rms), 0.0080)
            silence_rms = min(max(silence_rms, auto_silence_rms), 0.0045)
        _safe_print(
            f"Noise floor: {noise_floor:.5f} | speech_rms: {speech_rms:.5f} | silence_rms: {silence_rms:.5f}"
        )
        if cafe_mode:
            _safe_print("Cafe mode: ON")
        if manual_mode:
            if msvcrt is None:
                raise RuntimeError("Manual mode is only supported on Windows consoles")
            _safe_print("Manual mode: ON | Press Enter to start and stop recording")

        out_dir = Path("logs")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"live_stt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        min_speech_chunks = max(1, int(rate / chunk * min_speech_sec))
        end_silence_chunks = max(1, int(rate / chunk * end_silence_sec))
        preroll_chunks = max(1, int(rate / chunk * preroll_sec))

        speaking = False
        speech_frames: list[np.ndarray] = []
        speech_chunk_count = 0
        silence_chunk_count = 0
        pending_speech_count = 0
        last_text = ""
        preroll_frames: deque[np.ndarray] = deque(maxlen=preroll_chunks)
        idle_rms_history: deque[float] = deque(maxlen=80)
        last_status_at = time.perf_counter()
        start_trigger_chunks = 2 if cafe_mode else 1
        manual_recording = False
        manual_frames: list[np.ndarray] = []

        _safe_print("LIVE STARTED. Speak in Russian. Press Ctrl+C to stop.")
        _safe_print(f"Transcript log: {out_path}")

        with out_path.open("w", encoding="utf-8") as f:
            while True:
                data = stream.read(chunk, exception_on_overflow=False)
                arr = np.frombuffer(data, dtype=np.int16)

                audio = arr.astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(audio**2))) if audio.size else 0.0
                band_ratio = _speech_band_ratio(arr, rate)
                max_rms_seen = max(max_rms_seen, rms)
                preroll_frames.append(arr)

                if not speaking:
                    idle_rms_history.append(rms)

                if idle_rms_history:
                    adaptive_noise = float(np.percentile(list(idle_rms_history), 75))
                else:
                    adaptive_noise = noise_floor
                effective_speech_rms = speech_rms
                effective_silence_rms = silence_rms
                if cafe_mode:
                    effective_speech_rms = min(max(speech_rms, adaptive_noise * 2.8), 0.0200)
                    effective_silence_rms = min(max(silence_rms, adaptive_noise * 1.9), 0.0120)
                else:
                    effective_speech_rms = min(max(speech_rms, adaptive_noise * 1.8), 0.0080)
                    effective_silence_rms = min(max(silence_rms, adaptive_noise * 1.25), 0.0045)

                now = time.perf_counter()
                if debug_rms and now - last_status_at >= 1.0:
                    state = "speech" if speaking else "idle"
                    _safe_print(
                        f"[RMS] current={rms:.5f} peak={max_rms_seen:.5f} speech>={effective_speech_rms:.5f} "
                        f"silence>={effective_silence_rms:.5f} band={band_ratio:.2f} state={state}"
                    )
                    last_status_at = now

                if manual_mode:
                    toggle_requested = False
                    while msvcrt is not None and msvcrt.kbhit():
                        key = msvcrt.getwch()
                        if key == "\r":
                            toggle_requested = True
                    if toggle_requested:
                        manual_recording = not manual_recording
                        if manual_recording:
                            manual_frames = list(preroll_frames)
                            _safe_print("[MANUAL] recording: ON")
                        else:
                            _safe_print("[MANUAL] recording: OFF")
                            if manual_frames:
                                audio_i16, total_duration_sec, trimmed_duration_sec, trim_reason = _trim_manual_audio(
                                    frames=manual_frames,
                                    rate=rate,
                                    chunk=chunk,
                                    noise_floor=noise_floor,
                                    speech_rms=effective_speech_rms,
                                    band_threshold_start=band_threshold_start,
                                    focus_mode=True,
                                )
                                min_manual_samples = int(rate * min_speech_sec)
                                if audio_i16.size >= min_manual_samples:
                                    if debug_rms:
                                        _safe_print(f"[MANUAL] {trim_reason}")
                                    lang, text, reason = _transcribe_phrase(
                                        model=model,
                                        audio_i16=audio_i16,
                                        rate=rate,
                                        boost=boost,
                                        band_threshold_phrase=band_threshold_phrase,
                                        debug_rms=debug_rms,
                                        last_text=last_text,
                                        replacements=replacements,
                                        manual_mode=True,
                                    )
                                    long_manual_recording = total_duration_sec >= MANUAL_LONG_RECORDING_SEC
                                    should_retry_wide = (
                                        not text
                                        and reason is not None
                                        and (
                                            trimmed_duration_sec < 1.40
                                            or reason == "empty transcript"
                                            or reason.startswith("hallucination gate")
                                        )
                                    )
                                    if should_retry_wide or long_manual_recording:
                                        fallback_i16, _, fallback_duration_sec, fallback_reason = _trim_manual_audio(
                                            frames=manual_frames,
                                            rate=rate,
                                            chunk=chunk,
                                            noise_floor=noise_floor,
                                            speech_rms=effective_speech_rms,
                                            band_threshold_start=band_threshold_start,
                                            focus_mode=False,
                                            max_manual_sec_override=9.2 if long_manual_recording else None,
                                        )
                                        if fallback_duration_sec > trimmed_duration_sec + 0.20:
                                            if long_manual_recording:
                                                if debug_rms:
                                                    _safe_print(f"[MANUAL] retry segmented with {fallback_reason}")
                                                lang, retry_text, retry_reason = _transcribe_manual_segments(
                                                    model=model,
                                                    audio_i16=fallback_i16,
                                                    rate=rate,
                                                    boost=boost,
                                                    band_threshold_phrase=band_threshold_phrase,
                                                    debug_rms=debug_rms,
                                                    last_text=last_text,
                                                    replacements=replacements,
                                                )
                                            else:
                                                if debug_rms:
                                                    _safe_print(f"[MANUAL] retry with {fallback_reason}")
                                                lang, retry_text, retry_reason = _transcribe_phrase(
                                                    model=model,
                                                    audio_i16=fallback_i16,
                                                    rate=rate,
                                                    boost=boost,
                                                    band_threshold_phrase=band_threshold_phrase,
                                                    debug_rms=debug_rms,
                                                    last_text=last_text,
                                                    replacements=replacements,
                                                    manual_mode=True,
                                                )
                                            if retry_text:
                                                text = retry_text
                                                reason = None
                                                trimmed_duration_sec = fallback_duration_sec
                                            else:
                                                reason = retry_reason or reason
                                                trimmed_duration_sec = fallback_duration_sec
                                    if text:
                                        ts = datetime.now().strftime("%H:%M:%S")
                                        line = f"[{ts}] ({lang}) {text}"
                                        _safe_print(line)
                                        f.write(line + "\n")
                                        f.flush()
                                        last_text = text
                                    else:
                                        _safe_print(
                                            f"[MANUAL] dropped after {trimmed_duration_sec:.2f}s "
                                            f"(raw {total_duration_sec:.2f}s): {reason or 'filtered'}"
                                        )
                                else:
                                    _safe_print(
                                        f"[MANUAL] too short after trim: {audio_i16.size / rate:.2f}s "
                                        f"< {min_speech_sec:.2f}s"
                                    )
                            manual_frames = []
                    if manual_recording:
                        manual_frames.append(arr)
                    continue

                if not speaking:
                    start_candidate = rms >= effective_speech_rms and band_ratio >= band_threshold_start
                    if start_candidate:
                        pending_speech_count += 1
                    else:
                        pending_speech_count = 0

                    if pending_speech_count >= start_trigger_chunks:
                        speaking = True
                        speech_frames = list(preroll_frames)
                        speech_chunk_count = pending_speech_count
                        silence_chunk_count = 0
                        pending_speech_count = 0
                        continue

                    continue

                is_speech = rms >= effective_silence_rms and band_ratio >= band_threshold_hold
                if is_speech:
                    speech_frames.append(arr)
                    speech_chunk_count += 1
                    silence_chunk_count = 0
                    continue

                if not speaking:
                    continue

                speech_frames.append(arr)
                silence_chunk_count += 1

                if silence_chunk_count < end_silence_chunks:
                    continue

                speaking = False
                if speech_chunk_count < min_speech_chunks:
                    continue

                audio_i16 = np.concatenate(speech_frames)
                lang, text, _ = _transcribe_phrase(
                    model=model,
                    audio_i16=audio_i16,
                    rate=rate,
                    boost=boost,
                    band_threshold_phrase=band_threshold_phrase,
                    debug_rms=debug_rms,
                    last_text=last_text,
                    replacements=replacements,
                )
                if not text:
                    continue

                ts = datetime.now().strftime("%H:%M:%S")
                line = f"[{ts}] ({lang}) {text}"
                _safe_print(line)
                f.write(line + "\n")
                f.flush()
                last_text = text

    except KeyboardInterrupt:
        _safe_print("Stopped by user.")
        _safe_print(f"Max RMS observed: {max_rms_seen:.5f}")
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        p.terminate()


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Russian STT monitor.")
    parser.add_argument("--device", type=int, default=None, help="Input device index")
    parser.add_argument(
        "--profile",
        type=str,
        default=DEFAULT_PROFILE,
        choices=["manual-small", "manual-base", "auto-base"],
        help="Startup profile",
    )
    parser.add_argument("--model", type=str, default=None, help="Whisper model name")
    parser.add_argument("--rate", type=int, default=16000, help="Sample rate")
    parser.add_argument("--chunk", type=int, default=1024, help="Audio chunk size")
    parser.add_argument("--boost", type=float, default=20.0, help="Maximum software gain")
    parser.add_argument("--speech-rms", type=float, default=0.004, help="Speech start RMS threshold")
    parser.add_argument("--silence-rms", type=float, default=0.002, help="Speech end RMS threshold")
    parser.add_argument("--min-speech-sec", type=float, default=0.22, help="Minimum speech duration")
    parser.add_argument("--end-silence-sec", type=float, default=0.70, help="Silence required to flush phrase")
    parser.add_argument("--calibrate-sec", type=float, default=1.5, help="Ambient noise calibration time")
    parser.add_argument("--preroll-sec", type=float, default=0.25, help="Audio kept before speech trigger")
    parser.add_argument("--debug-rms", action="store_true", help="Print RMS and dropped segments")
    parser.add_argument(
        "--cafe-mode",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Stricter thresholds for cafe/music background",
    )
    parser.add_argument(
        "--manual-mode",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Record phrase manually with Enter toggle",
    )
    parser.add_argument("--warmup-only", action="store_true", help="Preload model into local cache and exit")
    parser.add_argument(
        "--local-files-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Load models from local cache only",
    )
    parser.add_argument("--download-root", type=Path, default=DEFAULT_DOWNLOAD_ROOT, help="Local model cache directory")
    parser.add_argument("--corrections-file", type=Path, default=DEFAULT_CORRECTIONS_PATH, help="JSON file with targeted post-corrections")
    parser.add_argument("--band-threshold-start", type=float, default=0.58, help="Speech-band ratio to start phrase")
    parser.add_argument("--band-threshold-hold", type=float, default=0.52, help="Speech-band ratio to keep phrase alive")
    parser.add_argument("--band-threshold-phrase", type=float, default=0.54, help="Speech-band ratio for whole phrase")
    args = parser.parse_args()
    args = _apply_profile_defaults(args)
    replacements = _load_targeted_replacements(args.corrections_file)

    if args.warmup_only:
        try:
            raise SystemExit(
                _warmup_model(
                    args.model,
                    rate=args.rate,
                    download_root=args.download_root,
                    local_files_only=args.local_files_only,
                )
            )
        except Exception as exc:
            _safe_print(f"Warmup failed for '{args.model}': {exc}")
            raise SystemExit(1)

    run_live(
        device=args.device,
        model_name=args.model,
        rate=args.rate,
        chunk=args.chunk,
        boost=args.boost,
        speech_rms=args.speech_rms,
        silence_rms=args.silence_rms,
        min_speech_sec=args.min_speech_sec,
        end_silence_sec=args.end_silence_sec,
        calibrate_sec=args.calibrate_sec,
        preroll_sec=args.preroll_sec,
        debug_rms=args.debug_rms,
        cafe_mode=args.cafe_mode,
        band_threshold_start=args.band_threshold_start,
        band_threshold_hold=args.band_threshold_hold,
        band_threshold_phrase=args.band_threshold_phrase,
        manual_mode=args.manual_mode,
        local_files_only=args.local_files_only,
        download_root=args.download_root,
        replacements=replacements,
    )


if __name__ == "__main__":
    main()
