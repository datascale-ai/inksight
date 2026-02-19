#ifndef INKSIGHT_CONFIG_H
#define INKSIGHT_CONFIG_H

#include <Arduino.h>

// ── Pin mapping (ESP32-C3 -> E-Ink) ─────────────────────────
#define PIN_EPD_MOSI   6   // SPI data (DIN)
#define PIN_EPD_SCK    4   // SPI clock (CLK)
#define PIN_EPD_CS     7   // Chip select
#define PIN_EPD_DC     1   // Data/Command select
#define PIN_EPD_RST    2   // Reset
#define PIN_EPD_BUSY   10  // Busy signal
#define PIN_BAT_ADC    0   // Battery voltage ADC
#define PIN_CFG_BTN    9   // GPIO9 (BOOT button) - hold to force config portal

// ── Display constants ────────────────────────────────────────
// Default for 4.2" E-Paper (400x300, 1-bit).
// Override via build flags: -D EPD_WIDTH=800 -D EPD_HEIGHT=480
#ifndef EPD_WIDTH
#define EPD_WIDTH  400
#endif
#ifndef EPD_HEIGHT
#define EPD_HEIGHT 300
#endif

static const int W = EPD_WIDTH;
static const int H = EPD_HEIGHT;
static const int ROW_BYTES   = W / 8;
static const int ROW_STRIDE  = (ROW_BYTES + 3) & ~3;  // BMP row stride (4-byte aligned)
static const int IMG_BUF_LEN = ROW_BYTES * H;

// Shared framebuffer (defined in main.cpp)
extern uint8_t imgBuf[];

// ── Refresh strategy ─────────────────────────────────────────
static const int FULL_REFRESH_INTERVAL = 10;  // Full refresh every N updates to clear ghosting

// ── Config defaults ─────────────────────────────────────────
static const char *DEFAULT_SERVER  = "http://192.168.3.30:8080";  // Set via captive portal
static const int   WIFI_TIMEOUT    = 15000;   // ms
static const int   HTTP_TIMEOUT    = 30000;   // ms
static const int   CFG_BTN_HOLD_MS = 2000;    // Long press duration to trigger config mode
static const int   SHORT_PRESS_MIN_MS = 50;   // Minimum short press duration (debounce)
static const int   DOUBLE_CLICK_MS = 500;     // Max interval between clicks for double-click
static const int   MAX_RETRY_COUNT = 5;       // Max retries before deep sleep
static const int   RETRY_DELAY_SEC = 10;      // Delay between retries (seconds)

// ── Time zone ───────────────────────────────────────────────
#define NTP_UTC_OFFSET  (8 * 3600)  // UTC+8 (China Standard Time), adjust for your region

// ── Debug mode ──────────────────────────────────────────────
#define DEBUG_MODE 1  // Set to 1 for fast refresh (1 min), 0 for user config
#if DEBUG_MODE
static const int DEBUG_REFRESH_MIN = 1;  // 1 minute for debugging
#endif

// ── Time display region (partial refresh area) ──────────────
#define TIME_RGN_X0   8
#define TIME_RGN_X1   64
#define TIME_RGN_Y0   6
#define TIME_RGN_Y1   24

#endif // INKSIGHT_CONFIG_H
