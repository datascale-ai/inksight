# AI Chat Mode Development Guide

AI Chat Mode (AI_CHAT) is a new voice interaction feature in InkSight that allows users to trigger voice conversations by pressing buttons on the device, enabling real-time voice communication with an AI assistant. This mode is designed for devices equipped with microphones and speakers, and leverages Alibaba's Bailian (百炼) platform for real-time ASR, streaming TTS, and LLM capabilities to deliver an end-to-end voice conversation experience.

## 1. Feature Overview

The core pipeline of AI Chat Mode is:

```
User speaks → Device microphone captures → Backend STT speech recognition → LLM generates response → TTS streaming synthesis → Device speaker plays audio
```

Key capabilities include:

- **Real-time Speech-to-Text (STT)**: Uses Bailian's `qwen3-asr-flash-realtime` model, uploads audio streams in real-time via WebSocket, supports Chinese recognition, and can return intermediate results (partial transcripts) during recognition
- **Streaming Text-to-Speech (TTS)**: Uses Bailian's `cosyvoice-v3-plus` model, synthesizes speech in streaming mode, supports playback-while-generating to reduce first-byte latency
- **LLM Response Generation**: Reuses LLM models already configured by users or the system (supports Qwen, Bailian, Deepseek, Moonshot, and other providers), generating concise, conversational responses
- **Voice Mode Switching**: During conversations, users can switch device display modes via voice commands (e.g., "switch to weather mode"), with the system intelligently recognizing intent
- **E-Ink Conversation Card**: After the conversation completes, the device renders a BMP image containing the user's question and AI response, displayed on the e-ink screen

### Two Interaction Modes

AI Chat Mode supports two usage paths:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Button Interaction** | User presses the device button to speak; after releasing, the device sends audio to the backend and plays the AI response | Physical device with microphone and speaker |
| **HTTP Request** | Upload PCM audio via HTTP POST to get recognized text, response text, response audio, and conversation image | Limited device capability or web integration |

## 2. Hardware Wiring

AI Chat Mode is currently only available on the **ESP32-WROOM32E** development board. Voice functionality support for ESP32-C3 series is on the roadmap, but the current firmware does not yet include it.

### 2.1 Recommended Audio Modules

| Module | Role | Interface | Description |
|--------|------|-----------|-------------|
| **INMP441** | Microphone (I2S input) | I2S | Omnidirectional MEMS microphone, 16kHz sampling, I2S interface |
| **MAX98357A** | Speaker amplifier (I2S output) | I2S | Class D amplifier module, directly drives 3W 8Ω speaker |

### 2.2 Pin Mapping

The voice-related pins of ESP32-WROOM-32E are defined in the firmware as follows:

**Microphone (INMP441)**

| INMP441 Pin | ESP32-WROOM-32E GPIO | Description |
|-------------|---------------------|-------------|
| VCC | 3.3V | Power supply |
| GND | GND | Ground |
| SCK | GPIO 18 | I2S clock |
| WS | GPIO 19 | I2S word select |
| SD | GPIO 33 | I2S data output |

**Speaker (MAX98357A)**

| MAX98357A Pin | ESP32-WROOM-32E GPIO | Description |
|---------------|---------------------|-------------|
| VCC | 3.3V | Power supply (MAX98357A supports 3.3V-5V) |
| GND | Do not connect | Connecting will cause no sound detection |
| BCK (DIN/BCLK) | GPIO 17 | I2S bit clock |
| LCK (WS/FS) | GPIO 16 | I2S word select |
| DIN (DOUT) | GPIO 22 | I2S data input |

### 2.3 Voice Trigger Button

| Function | ESP32-WROOM-32E GPIO | Description |
|----------|---------------------|-------------|
| One side of button | **GPIO 23** | Long press 3 seconds to enter AI Chat Mode |
| Other side of button | GND | Short press to enter network pairing mode |

> `PIN_AI_CHAT_SW` is defined as GPIO 23 in `firmware/src/config.h`. To customize the button pin, modify this macro definition.

### 2.4 Wiring Diagram

```
ESP32-WROOM-32E
┌─────────────────────────────────┐
│                           3.3V  │────────────── VCC (INMP441) VCC (MAX98357A)
│                             GND │────────────── GND (INMP441)
│                        GPIO 18 │────────────── SCK  (INMP441)
│                        GPIO 19 │────────────── WS   (INMP441)
│                        GPIO 33 │────────────── SD   (INMP441)
│                        GPIO 17 │────────────── BCK  (MAX98357A)
│                        GPIO 16 │────────────── LCK  (MAX98357A)
│                        GPIO 22 │────────────── DIN  (MAX98357A)
│                        GPIO 23 │────────────── Voice trigger button (other end to GND)
│                         ...    │
└─────────────────────────────────┘
```

### 2.5 Firmware Configuration Macros

In `firmware/platformio.ini`, ensure the build target corresponds to `WROOM32E`, for example, using the environment `epd_42_wsv2_ssd1683_wroom32e`.

If you want the device to automatically enter AI Chat Mode on power-up, define in `platformio.ini`:

```ini
build_flags =
    ...
    -D AUTO_BOOT_AI_CHAT=1
```

Voice-related firmware parameters:

| Macro | Default Value | Description |
|-------|---------------|-------------|
| `SAMPLE_RATE` | 16000 | Sample rate (Hz), must be 16kHz |
| `ENABLE_OPUS` | Optional | Enable Opus codec (saves bandwidth, requires backend support) |
| `AI_CHAT_BTN_HOLD_MS` | 3000 | Duration for long press to trigger AI chat (milliseconds) |

### 2.6 Audio Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Sample rate | 16kHz | Used by both STT and TTS |
| Microphone bit depth | 32-bit I2S | INMP441 outputs 24-bit, firmware takes high 16-bit |
| Speaker bit depth | 16-bit | MAX98357A requires 16-bit stereo input |
| Opus frame length | 60ms | When Opus is enabled, each frame is 60ms (960 samples) |
| I2S DMA buffer | 240 samples | Input/output DMA buffer size |

## 3. Prerequisites

### Hardware Requirements

- ESP32 series device (WROOM32E recommended or models with larger Flash)
- Microphone module (supporting 16kHz PCM audio capture)
- Speaker or audio output module
- Wi-Fi connected

### Server Requirements

- InkSight backend service deployed and accessible
- Alibaba Bailian account with valid API Key
- Device already paired and bound

### Bailian API Key Application

1. Visit [Alibaba Cloud Bailian Platform](https://bailian.console.aliyun.com), register and log in
2. Create a new API Key in "API-KEY Management"
3. Ensure the Key has enabled the following services:
   - **Speech Recognition (ASR)**: `qwen3-asr-flash-realtime`
   - **Speech Synthesis (TTS)**: `cosyvoice-v3-plus`
   - **Model Service**: The LLM model you plan to use

## 4. .env Configuration (For Development)

All voice-related parameters are configured in the backend `.env` file. The following explains each parameter's function, default value, and tuning suggestions grouped by feature.

### 4.1 API Key Configuration

```
# Bailian API Key (shared by STT/TTS, falls back to DASHSCOPE_API_KEY if empty)
VOICE_DASHSCOPE_API_KEY=

# Optional: Configure separate keys for STT / TTS individually
VOICE_STT_API_KEY=
VOICE_TTS_API_KEY=
```

**Explanation**: `VOICE_DASHSCOPE_API_KEY` takes priority. If left empty, it automatically uses `DASHSCOPE_API_KEY`. To use different keys for STT and TTS separately, use `VOICE_STT_API_KEY` and `VOICE_TTS_API_KEY`.

### 4.2 Speech Recognition (STT) Configuration

```
# Real-time ASR model (usually no need to change)
VOICE_REALTIME_ASR_MODEL=qwen3-asr-flash-realtime

# Bailian ASR WebSocket address (usually no need to change)
VOICE_REALTIME_ASR_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/realtime

# ASR recognition language
VOICE_REALTIME_ASR_LANGUAGE=zh

# Idle timeout (seconds), automatically ends recognition if no new audio after this time
VOICE_REALTIME_ASR_IDLE_TIMEOUT_SECONDS=20

# ASR WebSocket maximum bytes per message
VOICE_REALTIME_ASR_MAX_EVENT_BYTES=15728640
```

**Tuning suggestions**:
- `VOICE_REALTIME_ASR_IDLE_TIMEOUT_SECONDS`: If users have longer pauses between speaking, increase this value (e.g., to 30); if there are many false triggers, decrease it (e.g., to 15)
- `VOICE_REALTIME_ASR_LANGUAGE`: Currently only supports `zh` (Chinese); change to `en` for English

### 4.3 Text-to-Speech (TTS) Configuration

```
# Enable streaming TTS (1=enable, 0=disable)
VOICE_STREAMING_TTS_ENABLED=1

# TTS model
VOICE_STREAMING_TTS_MODEL=cosyvoice-v3-plus

# Voice timbre (longanyang is the default Chinese voice, can replace with other voice IDs)
VOICE_STREAMING_TTS_VOICE=longanyang

# TTS WebSocket address (usually no need to change)
VOICE_STREAMING_TTS_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference

# Output audio sample rate (Hz)
VOICE_STREAMING_TTS_SAMPLE_RATE=16000

# Volume (0-100)
VOICE_STREAMING_TTS_VOLUME=50

# Pitch (1.0 is standard pitch)
VOICE_STREAMING_TTS_PITCH=1.0

# Speed (1.0 is standard speed)
VOICE_STREAMING_TTS_SPEED=1.0

# TTS WebSocket maximum bytes per message
VOICE_STREAMING_TTS_MAX_EVENT_BYTES=4194304
```

**Tuning suggestions**:
- `VOICE_STREAMING_TTS_VOLUME`: Adjust according to speaker sensitivity; reduce to 30-40 if too loud
- `VOICE_STREAMING_TTS_SPEED`: Reduce to 0.8-0.9 if speaking too fast; increase to 1.1-1.2 if too slow
- `VOICE_STREAMING_TTS_PITCH`: Fine-tune for different voice styles (best results in 0.8-1.2 range)
- Bailian supports multiple voice IDs; check the Bailian console for available voice list and replace `VOICE_STREAMING_TTS_VOICE`

### 4.4 Streaming Synthesis and Warmup Control

These parameters control the coordination strategy between LLM streaming generation and TTS streaming synthesis, affecting conversation response speed and fluency.

```
# Enable LLM streaming output (1=enable, 0=generate complete response before synthesis)
VOICE_LLM_STREAMING=1

# Enable TTS streaming synthesis (1=enable, 0=synthesize after complete text generation)
VOICE_TTS_STREAMING=1

# TTS streaming minimum segment characters (single segment triggers synthesis only after reaching this many characters)
VOICE_TTS_STREAM_MIN_CHARS=12

# TTS streaming maximum segment characters (single segment caps at this many characters)
VOICE_TTS_STREAM_MAX_CHARS=36

# Delta segment minimum characters (consider segmentation only when LLM output delta reaches this length)
VOICE_TTS_DELTA_MIN_CHARS=6

# Delta segment maximum characters
VOICE_TTS_DELTA_MAX_CHARS=16

# Delta segment idle interval (milliseconds), force segmentation if LLM output pause exceeds this time
VOICE_TTS_DELTA_IDLE_MS=320

# Warmup minimum characters (start warmup when partial ASR result reaches this length)
VOICE_WS_PARTIAL_WARMUP_MIN_CHARS=2

# Warmup stable threshold (milliseconds), start warmup LLM/TTS after ASR partial result is stable for this duration
VOICE_WS_PARTIAL_WARMUP_STABLE_MS=180

# WebSocket audio chunk size (bytes), affects network transmission efficiency
VOICE_WS_AUDIO_CHUNK_BYTES=2048
```

**Tuning suggestions**:
- If fast response is critical (want to start playback while speaking), keep `VOICE_LLM_STREAMING=1` and `VOICE_TTS_STREAMING=1`
- If device processing power is limited or network is unstable, set both to `0` for non-streaming mode (slower but more stable)
- `VOICE_TTS_DELTA_IDLE_MS`: AI thinking pauses exceeding 320ms trigger segmented playback to avoid long user waits
- `VOICE_WS_PARTIAL_WARMUP_STABLE_MS`: Start generating responses 180ms after ASR recognition stabilizes, reducing perceived latency

### 4.5 Server-side VAD (Voice Activity Detection)

Server-side VAD allows the backend to automatically trigger speech recognition submission when silence is detected, without waiting for the device to actively send a commit signal.

```
# Enable server-side VAD (1=enable, 0=disable)
VOICE_SERVER_VAD_ENABLED=1

# Silence detection threshold (milliseconds), considered as user finished speaking after this duration of silence
VOICE_SERVER_VAD_SILENCE_MS=800
```

**Explanation**: After enabling server-side VAD, even if the device firmware does not actively commit voice, the backend can automatically process after 800ms of silence. This helps improve experience when network is unstable, but may increase false triggers. If the device firmware has implemented local VAD, it is recommended to set `VOICE_SERVER_VAD_ENABLED` to `0`.

### 4.6 Session Cache Configuration

```
# Voice session cache retention duration (seconds), automatically cleared after this
VOICE_TURN_TTL_SECONDS=900
```

**Explanation**: Each voice conversation generates a turn record containing recognized text, response text, audio data, and conversation image. This data can be retrieved via API within the TTL for playback, breakpoint resume, and other scenarios. 900 seconds (~15 minutes) is sufficient for daily use without frequent modifications.

## 5. Mode Switching Commands

Users can switch device modes through natural language commands during conversations. The system recognizes the following types of commands:

| Trigger Words | Target Mode | Example |
|---------------|-------------|---------|
| Weather, Weather Dashboard | WEATHER | "Switch to weather mode" |
| Calendar, Monthly Calendar | CALENDAR | "Switch to calendar mode" |
| Daily Recommendation, Daily | DAILY | "Switch to daily recommendation mode" |

**Explanation**: After the device detects a mode switching command, it generates a brief confirmation voice (e.g., "Okay, switching for you") and then automatically switches to the target mode.

## 6. Usage Flow

### 6.1 Initial Configuration

1. Apply for an API Key on Alibaba Bailian platform, ensuring ASR, TTS, and LLM services are enabled
2. Configure `VOICE_DASHSCOPE_API_KEY` in the backend `.env` (or configure `VOICE_STT_API_KEY` and `VOICE_TTS_API_KEY` separately)
3. Adjust TTS parameters (voice, volume, speed) and streaming control parameters as needed
4. Restart the backend service to apply configurations
5. In the WebApp device configuration page, switch the device mode to "AI Chat"
6. Ensure the device has the firmware with voice functionality flashed

### 6.2 Daily Use

1. Long press the device button to enter AI Chat Mode
2. Speak into the device microphone (audio is automatically sent after releasing the button or timing out)
3. Wait for the AI response and play through the speaker
4. To continue the conversation, press the button and speak again
5. To switch modes, simply say the switching command (e.g., "Switch to weather")
6. Say "Exit conversation" or "Close mode" to end the conversation

## 7. Troubleshooting

### Common Issues

**1. Speech recognition not responding or returning empty text**
- Check if `VOICE_DASHSCOPE_API_KEY` is correctly configured
- Confirm that ASR service is enabled in your Bailian account
- Check if audio format is 16kHz PCM (mono)
- Check backend logs for `[VOICE_STT]` related output

**2. TTS playback abnormal (no sound or noise)**
- Confirm `VOICE_STREAMING_TTS_SAMPLE_RATE` matches device audio sample rate (usually 16000Hz)
- Check if `VOICE_STREAMING_TTS_ENABLED` is set to 1
- Confirm device audio driver supports PCM format decoding

**3. Mode switching not working**
- Check if trigger words are in the supported list (see Section 5)
- Confirm firmware implements `switch_to_mode` handling logic

**4. High response latency**
- Confirm stable network connection to Bailian service
- Try reducing `VOICE_TTS_DELTA_IDLE_MS` (e.g., to 200) to speed up segmentation
- Check if `VOICE_WS_PARTIAL_WARMUP_STABLE_MS` is reasonable

**5. Server-side VAD false triggers**
- If device firmware has implemented local VAD, set `VOICE_SERVER_VAD_ENABLED` to `0`
- If server-side VAD is needed, appropriately increase `VOICE_SERVER_VAD_SILENCE_MS` (e.g., to 1200)

## 8. Related Documentation

- [Device Configuration Guide](config.md)
- [Custom Mode Development Guide](custom-mode-dev.md)
- [Deployment Guide](deploy.md)
- [FAQ](faq.md)
