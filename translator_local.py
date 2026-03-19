"""
Traduction EN->FR locale via CTranslate2 + opus-mt-tc-big-en-fr.
GPU NVIDIA (CUDA) si disponible, sinon CPU.
Utilise uniquement en local (pas en CI GitHub Actions).

Tokenizer : MarianTokenizer (transformers) — requis pour opus-mt-tc-big.
DLL CUDA  : nvidia-cublas-cu12 + nvidia-cuda-runtime-cu12 via pip,
            injectees dans PATH avant l import de ctranslate2.
"""
import os
import sys
from pathlib import Path

# ── Injecter les DLL nvidia pip dans PATH AVANT import ctranslate2 ────────
# Necessaire sur Windows sans CUDA Toolkit installe (driver seul insuffisant).
if sys.platform == "win32":
    _nvidia = Path(sys.executable).parent / "Lib" / "site-packages" / "nvidia"
    if _nvidia.exists():
        _dll_dirs = [
            str(b) for b in _nvidia.rglob("bin")
            if b.is_dir() and any(b.glob("*.dll"))
        ]
        if _dll_dirs:
            os.environ["PATH"] = ";".join(_dll_dirs) + ";" + os.environ.get("PATH", "")

# ── Chemins modele ────────────────────────────────────────────────────────
_MODEL_DIR = Path(os.environ.get(
    "OPUS_MT_MODEL_DIR",
    Path.home() / "dev" / "models" / "opus-mt-tc-big-en-fr-ct2"
))
_TOKENIZER_DIR = Path(os.environ.get(
    "OPUS_MT_TOKENIZER_DIR",
    Path.home() / "dev" / "models" / "opus-mt-tc-big-en-fr-src"
))

_translator = None
_tokenizer = None


def _load():
    global _translator, _tokenizer
    if _translator is not None:
        return True
    if not _MODEL_DIR.exists() or not _TOKENIZER_DIR.exists():
        return False
    try:
        import ctranslate2
        from transformers import MarianTokenizer

        device = "cpu"
        try:
            if ctranslate2.get_cuda_device_count() > 0:
                device = "cuda"
        except Exception:
            pass

        inter_threads = 1 if device == "cuda" else 4
        print(f"  [CT2] Chargement modele opus-mt-tc-big sur {device.upper()}...")
        _translator = ctranslate2.Translator(
            str(_MODEL_DIR),
            device=device,
            inter_threads=inter_threads,
            intra_threads=4,
        )
        _tokenizer = MarianTokenizer.from_pretrained(str(_TOKENIZER_DIR))
        print(f"  [CT2] Modele pret ({device.upper()})")
        return True
    except Exception as e:
        print(f"  [CT2] Erreur chargement: {e}")
        return False


def translate_local(texts: list[str]) -> list[str] | None:
    """
    Traduit une liste de textes EN->FR via CTranslate2 (GPU/CPU local).
    Retourne None si le modele n est pas disponible.
    """
    if not _load():
        return None
    try:
        indices = [i for i, t in enumerate(texts) if t and len(t.strip()) > 3]
        if not indices:
            return list(texts)

        to_translate = [texts[i][:500] for i in indices]

        # Tokenisation via MarianTokenizer
        inputs = _tokenizer(to_translate, return_tensors="pt", padding=True)
        tokenized = [
            _tokenizer.convert_ids_to_tokens(ids)
            for ids in inputs["input_ids"].tolist()
        ]

        results = _translator.translate_batch(
            tokenized,
            beam_size=4,
            max_batch_size=32,
            max_decoding_length=200,
        )

        out = list(texts)
        for pos, (idx, r) in enumerate(zip(indices, results)):
            decoded = _tokenizer.convert_tokens_to_string(r.hypotheses[0])
            out[idx] = decoded if decoded.strip() else texts[idx]
        return out
    except Exception as e:
        print(f"  [CT2] Erreur traduction: {e}")
        return None


def is_available() -> bool:
    """Verifie si le modele local est installe (sans le charger)."""
    return _MODEL_DIR.exists() and _TOKENIZER_DIR.exists()
