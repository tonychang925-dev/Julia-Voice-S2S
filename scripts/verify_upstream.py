#!/usr/bin/env python3
"""Verify that running S2S matches UPSTREAM.lock."""
import importlib.metadata as m
import inspect
import speech_to_speech

print("speech-to-speech version:", m.version("speech-to-speech"))
print("Package path:", speech_to_speech.__file__)

from speech_to_speech.api.openai_realtime import websocket_router
print("WebSocket router:", inspect.getfile(websocket_router))
