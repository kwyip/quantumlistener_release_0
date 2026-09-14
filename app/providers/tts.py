from __future__ import annotations

import math
import os
import struct
import subprocess
import wave
from pathlib import Path


class MockTTS:
    """Deterministic credential-free narration tone; never impersonates human speech."""

    def synthesize(self, text: str, destination: Path, *, ssml: bool = False) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        wav = destination.with_suffix(".wav")
        seconds = max(1.0, min(8.0, len(text) / 120))
        rate = 16_000
        with wave.open(str(wav), "wb") as stream:
            stream.setparams((1, 2, rate, int(rate * seconds), "NONE", "not compressed"))
            for i in range(int(rate * seconds)):
                value = int(3200 * math.sin(2 * math.pi * 220 * i / rate))
                stream.writeframesraw(struct.pack("<h", value))
        if destination.suffix == ".mp3":
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-loglevel",
                        "error",
                        "-i",
                        str(wav),
                        "-af",
                        "loudnorm=I=-16:TP=-1.5:LRA=11",
                        str(destination),
                    ],
                    check=True,
                    timeout=60,
                )
                wav.unlink()
            except (FileNotFoundError, subprocess.CalledProcessError):
                # A WAV container remains playable and makes the environment limitation explicit.
                destination.write_bytes(wav.read_bytes())
                wav.unlink()
        else:
            wav.replace(destination)
        return destination


class PollyTTS:
    def __init__(self, client=None, voice_id: str | None = None):
        if client is None:
            import boto3

            client = boto3.client("polly", region_name=os.getenv("AWS_REGION", "us-east-1"))
        self.client = client
        self.voice_id = voice_id or os.getenv("POLLY_VOICE_ID", "Joanna")

    def synthesize(self, text: str, destination: Path, *, ssml: bool = False) -> Path:
        response = self.client.synthesize_speech(
            Text=text,
            TextType="ssml" if ssml else "text",
            OutputFormat="mp3",
            VoiceId=self.voice_id,
            Engine=os.getenv("POLLY_ENGINE", "neural"),
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response["AudioStream"].read())
        return destination
