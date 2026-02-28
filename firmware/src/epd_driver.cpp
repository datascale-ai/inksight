#include "epd_driver.h"
#include "config.h"
#include <SPI.h>

// ── GxEPD2 display driver selection ─────────────────────────
// Select the appropriate GxEPD2 driver class based on panel type.
// Panel type is set via build flags in platformio.ini.

#include <GxEPD2_BW.h>

#if defined(EPD_PANEL_42)
  // Waveshare 4.2" V2 (SSD1683), 400x300
  #include <epd/GxEPD2_420_GDEY042T81.h>
  GxEPD2_BW<GxEPD2_420_GDEY042T81, GxEPD2_420_GDEY042T81::HEIGHT> display(
      GxEPD2_420_GDEY042T81(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));

#elif defined(EPD_PANEL_29)
  // Waveshare 2.9" (SSD1680), 296x128
  #include <epd/GxEPD2_290_GDEY029T94.h>
  GxEPD2_BW<GxEPD2_290_GDEY029T94, GxEPD2_290_GDEY029T94::HEIGHT> display(
      GxEPD2_290_GDEY029T94(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));

#elif defined(EPD_PANEL_583)
  // Waveshare 5.83" V2 (GDEY0583T81 / GDEQ0583T31), 648x480
  // Use reduced page buffer height to save RAM on ESP32-C3
  #include <epd/GxEPD2_583_GDEQ0583T31.h>
  GxEPD2_BW<GxEPD2_583_GDEQ0583T31, GxEPD2_583_GDEQ0583T31::HEIGHT / 4> display(
      GxEPD2_583_GDEQ0583T31(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));

#elif defined(EPD_PANEL_75)
  // Waveshare 7.5" (GDEW075T7 / GD7965), 800x480
  // Use reduced page buffer height to save RAM on ESP32-C3
  #include <epd/GxEPD2_750_T7.h>
  GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT / 4> display(
      GxEPD2_750_T7(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));

#else
  #error "No EPD panel type defined. Use -DEPD_PANEL_42, -DEPD_PANEL_29, -DEPD_PANEL_583, or -DEPD_PANEL_75"
#endif

// ── Track initialization state ──────────────────────────────
static bool _initialized = false;

// ── GPIO & SPI initialization ───────────────────────────────

void gpioInit() {
    pinMode(PIN_CFG_BTN, INPUT_PULLUP);

    // Configure hardware SPI with the project's pin mapping
    SPI.begin(PIN_EPD_SCK, -1, PIN_EPD_MOSI, PIN_EPD_CS);
}

// ── EPD initialization (full refresh mode) ──────────────────

void epdInit() {
    if (!_initialized) {
        display.init(0);  // 0 = no debug serial output from GxEPD2
        display.setRotation(0);
        _initialized = true;
    }
}

// ── EPD initialization (fast refresh mode) ──────────────────

void epdInitFast() {
    epdInit();  // GxEPD2 handles fast mode internally
}

// ── Full-screen display with full refresh ───────────────────
// Clears all ghosting but has visible black-white flash.

void epdDisplay(const uint8_t *image) {
    epdInit();
    display.writeImage(image, 0, 0, W, H, false, false, true);
    display.refresh(false);  // false = full refresh
    display.powerOff();
}

// ── Full-screen display with fast refresh ───────────────────
// Less flashing, may accumulate ghosting over time.

void epdDisplayFast(const uint8_t *image) {
    epdInit();
    display.writeImage(image, 0, 0, W, H, false, false, true);
    display.refresh(true);  // true = partial/fast refresh mode
    display.powerOff();
}

// ── Partial display refresh ─────────────────────────────────
// Updates only a rectangular region of the display.

void epdPartialDisplay(uint8_t *data, int xStart, int yStart, int xEnd, int yEnd) {
    epdInit();
    int w = xEnd - xStart;
    int h = yEnd - yStart;
    display.writeImage(data, xStart, yStart, w, h, false, false, true);
    display.refresh(xStart, yStart, w, h);
    display.powerOff();
}

// ── EPD deep sleep ──────────────────────────────────────────

void epdSleep() {
    display.hibernate();
    _initialized = false;
}
