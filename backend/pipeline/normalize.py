import asyncio


async def normalize_file(path: str) -> bytes:
    """Decode any audio file to 16kHz mono s16le PCM using ffmpeg."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-i", path,
        "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {err.decode(errors='replace')}")
    return out
