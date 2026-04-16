#ifndef INKSIGHT_CONFIG_H
#define INKSIGHT_CONFIG_H

#include <Arduino.h>

#if defined(BOARD_PROFILE_ESP32_C3)
#define PIN_EPD_MOSI   6
#define PIN_EPD_SCK    4
#define PIN_EPD_CS     7
#define PIN_EPD_DC     1
#define PIN_EPD_RST    2
#define PIN_EPD_BUSY   10
#define PIN_BAT_ADC    0
#define PIN_CFG_BTN    9
#define PIN_LED        3
#elif defined(BOARD_PROFILE_ESP32_WROOM32E)
#define PIN_EPD_MOSI   14
#define PIN_EPD_SCK    13
#define PIN_EPD_CS     15
#define PIN_EPD_DC     27
#define PIN_EPD_RST    26
#define PIN_EPD_BUSY   25
#define PIN_BAT_ADC    35
#define PIN_CFG_BTN    0
#define PIN_LED        2
#elif defined(BOARD_PROFILE_XIAO_ESP32S3)
#define PIN_EPD_MOSI   9
#define PIN_EPD_SCK    7
#define PIN_EPD_CS     44
#define PIN_EPD_DC     10
#define PIN_EPD_RST    38
#define PIN_EPD_BUSY   4
// Seeed XIAO ESP32S3 onboard ADC_BAT shares GPIO10 with the current EPD_DC
// wiring, so battery sampling must only happen while the display bus is idle.
#define PIN_BAT_ADC    10
#define PIN_CFG_BTN    2
#define PIN_LED        LED_BUILTIN
#else
#error "Unsupported board profile"
#endif

// ── Display constants ────────────────────────────────────────
// Default for 4.2" E-Paper (400x300, 1-bit).
// Override via build flags: -D EPD_WIDTH=800 -D EPD_HEIGHT=480
// Supported configurations:
//   4.2"  (400x300) - default
//   2.9"  (296x128)
//   5.83" (648x480)
//   7.5"  (800x480)
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

#ifndef EPD_BPP
#define EPD_BPP 1
#endif

#if defined(EPD_PANEL_75_GDEY075Z08) || defined(EPD_PANEL_583_GDEY0583Z21) || defined(EPD_PANEL_42_UC8176) || defined(EPD_PANEL_42_HINK_SSD1683)
#define EPD_COLOR_CAPABILITY 3
#elif EPD_BPP >= 2
#define EPD_COLOR_CAPABILITY 4
#else
#define EPD_COLOR_CAPABILITY 2
#endif

static const int COLOR_BUF_LEN = (W * H) / 4;  // 2bpp: 4 pixels per byte

// Shared framebuffers (defined in main.cpp)
extern uint8_t imgBuf[];
#if EPD_BPP >= 2
extern uint8_t colorBuf[];
extern bool useColorBuf;
#endif

// ── Refresh strategy ─────────────────────────────────────────
static const int FULL_REFRESH_INTERVAL = 10;  // Full refresh every N updates to clear ghosting

// ── Config defaults ─────────────────────────────────────────
static const char *DEFAULT_SERVER  = "";  // Must be set via captive portal
static const int   WIFI_TIMEOUT    = 15000;   // ms
static const int   HTTP_TIMEOUT    = 30000;   // ms
static const int   CFG_BTN_HOLD_MS = 2000;    // Long press duration to trigger config mode
static const int   SHORT_PRESS_MIN_MS = 50;   // Minimum short press duration (debounce)
static const int   LIVE_POLL_MS = 5000;       // Poll interval for pending remote actions
static const int   LIVE_WIFI_RETRY_MS = 5000; // Retry interval when WiFi is disconnected
static const unsigned long HEARTBEAT_INTERVAL_MS = 10UL * 60UL * 1000UL;
static const int   MAX_RETRY_COUNT = 5;       // Max retries before deep sleep
// Progressive retry delays in seconds: 5s, 15s, 30s, 60s, 120s
static const int   RETRY_DELAYS[] = {5, 15, 30, 60, 120};

// ── Time zone ───────────────────────────────────────────────
#define NTP_UTC_OFFSET  (8 * 3600)  // UTC+8 (China Standard Time), adjust for your region

// ── Debug mode ──────────────────────────────────────────────
#define DEBUG_MODE 0  // Set to 1 for fast refresh (1 min), 0 for user config
#if DEBUG_MODE
static const int DEBUG_REFRESH_MIN = 1;  // 1 minute for debugging
#endif

// ── Time display region (partial refresh area) ──────────────
// Proportional to screen size (scales across 2.9"/4.2"/7.5")
#define TIME_RGN_X0   (0)
#define TIME_RGN_X1   ((W * 14 / 100) & ~7)
#define TIME_RGN_Y0   (H * 2 / 100)
#define TIME_RGN_Y1   (H * 8 / 100)

#define TIME_TEXT_X   (W * 1 / 100)
#define TIME_TEXT_Y   (H * 4 / 100)

#endif // INKSIGHT_CONFIG_H
