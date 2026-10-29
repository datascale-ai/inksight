#include "epd_driver.h"
#include "config.h"

#if defined(EPD_PANEL_583_GDEY0583Z21)

// GDEY0583Z21  5.83" Black/White/Yellow tri-color e-ink panel
// Init sequence follows the GDEQ0583Z31 (5.83" BWR) reference from GxEPD2,
// which is the tri-color sibling of the GDEQ0583T31 used in epd_583_wroom32e.
// Reference: GxEPD2 src/gdeq3c/GxEPD2_583c_GDEQ0583Z31.cpp

#include <SPI.h>

#ifndef EPD_GXEPD2_SPI_HZ
#define EPD_GXEPD2_SPI_HZ 4000000
#endif

static bool gdey0583_initialized = false;

static uint8_t* epdColorPlaneBuffer() {
    return colorBuf + IMG_BUF_LEN;
}

// ── Low-level SPI helpers ────────────────────────────────────

static void gdey0583BeginTransfer(bool data_mode) {
    digitalWrite(PIN_EPD_DC, data_mode ? HIGH : LOW);
    digitalWrite(PIN_EPD_CS, LOW);
    SPI.beginTransaction(SPISettings(EPD_GXEPD2_SPI_HZ, MSBFIRST, SPI_MODE0));
}

static void gdey0583EndTransfer() {
    SPI.endTransaction();
    digitalWrite(PIN_EPD_CS, HIGH);
}

static void gdey0583WriteCommand(uint8_t cmd) {
    gdey0583BeginTransfer(false);
    SPI.transfer(cmd);
    gdey0583EndTransfer();
}

static void gdey0583WriteData(uint8_t data) {
    gdey0583BeginTransfer(true);
    SPI.transfer(data);
    gdey0583EndTransfer();
}

// BUSY=LOW means panel is busy; wait for HIGH (same polarity as GDEQ0583Z31)
static void gdey0583WaitBusy(unsigned long timeout_ms = 30000) {
    const unsigned long t0 = millis();
    while (digitalRead(PIN_EPD_BUSY) == LOW) {
        delay(10);
        if (millis() - t0 > timeout_ms) {
            Serial.println("GDEY0583Z21 busy timeout");
            return;
        }
    }
}

// ── Controller init (follows GDEQ0583Z31 _InitDisplay) ──────
// Power on is NOT done here; it is done inside gdey0583Refresh()
// before the refresh command, matching GxEPD2's _Update_Full flow.

static void gdey0583InitController() {
    if (gdey0583_initialized) return;

    SPI.begin(PIN_EPD_SCK, -1, PIN_EPD_MOSI, PIN_EPD_CS);

    // Hardware reset
    digitalWrite(PIN_EPD_RST, HIGH); delay(10);
    digitalWrite(PIN_EPD_RST, LOW);  delay(10);
    digitalWrite(PIN_EPD_RST, HIGH); delay(10);
    gdey0583WaitBusy();

    gdey0583WriteCommand(0x00);  // PSR: BWR/BWY 3-color mode, LUT from OTP
    gdey0583WriteData(0x0F);     // (GDEQ0583T31 BW uses 0x1F; 0x0F selects 3-color)

    gdey0583WriteCommand(0x50);  // CDI: VCOM and data interval (from GDEQ0583Z31)
    gdey0583WriteData(0x11);
    gdey0583WriteData(0x07);

    gdey0583_initialized = true;
}

// ── Partial RAM area (0x90 window command, GDEQ0583Z31 format) ─

static void gdey0583SetWindow(uint16_t x, uint16_t y, uint16_t w, uint16_t h) {
    const uint16_t xe = (x + w - 1) | 0x0007;
    const uint16_t ye = y + h - 1;
    x &= 0xFFF8;

    gdey0583WriteCommand(0x90);
    gdey0583WriteData(x >> 8);
    gdey0583WriteData(x & 0xFF);
    gdey0583WriteData(xe >> 8);
    gdey0583WriteData(xe & 0xFF);
    gdey0583WriteData(y >> 8);
    gdey0583WriteData(y & 0xFF);
    gdey0583WriteData(ye >> 8);
    gdey0583WriteData(ye & 0xFF);
    gdey0583WriteData(0x01);
}

// ── Image plane writers ──────────────────────────────────────

static void gdey0583WritePlane(uint8_t command, const uint8_t* buffer, uint8_t fill, bool invert) {
    gdey0583WriteCommand(command);
    gdey0583BeginTransfer(true);
    for (int i = 0; i < IMG_BUF_LEN; i++) {
        uint8_t value = buffer ? buffer[i] : fill;
        if (invert) value = ~value;
        SPI.transfer(value);
    }
    gdey0583EndTransfer();
}

// Write black + color planes into panel RAM.
// 0x10 (black): standard polarity — decode 0=black matches panel 0=black, no invert.
// 0x13 (color): inverted polarity — decode 0=yellow but panel reads 1=yellow, so invert.
static void gdey0583WriteImage(const uint8_t* black_plane, const uint8_t* color_plane) {
    gdey0583WriteCommand(0x91);  // partial in
    gdey0583SetWindow(0, 0, W, H);
    gdey0583WritePlane(0x10, black_plane, 0xFF, false); // standard polarity: 0=black, 1=white
    gdey0583WritePlane(0x13, color_plane, 0xFF, true);  // inverted polarity: 1=yellow, 0=white
    gdey0583WriteCommand(0x92);  // partial out
}

// ── Refresh (follows GDEQ0583Z31 _PowerOn + _Update_Full) ───
// Power on is done here, immediately before the refresh command.
// Full refresh for tri-color takes up to 30 seconds.

static void gdey0583Refresh() {
    gdey0583WriteCommand(0x04);  // power on
    gdey0583WaitBusy(5000);      // ~140ms typical (GDEQ0583Z31 power_on_time=140ms)

    gdey0583WriteCommand(0x12);  // display refresh
    delay(100);
    gdey0583WaitBusy(35000);     // tri-color full refresh up to 30s (Z31 full_refresh_time=30000ms)
}

// ── 2bpp decode ──────────────────────────────────────────────
// Reads raw2bpp backwards so that color_plane (upper half of colorBuf)
// does not clobber unread 2bpp source bytes.

static void decodeRaw2bppToTriColorPlanes(const uint8_t* raw2bpp, uint8_t* black_plane, uint8_t* color_plane) {
    memset(black_plane, 0xFF, IMG_BUF_LEN);

    for (int out = IMG_BUF_LEN - 1; out >= 0; out--) {
        const uint8_t src0 = raw2bpp[out * 2];
        const uint8_t src1 = raw2bpp[out * 2 + 1];
        uint8_t black_byte = 0xFF;
        uint8_t color_byte = 0xFF;

        for (int px = 0; px < 4; px++) {
            const uint8_t code = (src0 >> (6 - px * 2)) & 0x03;
            const uint8_t mask = 0x80 >> px;
            if (code == 0x00)       black_byte &= ~mask;
            else if (code >= 0x02)  color_byte &= ~mask;
        }
        for (int px = 0; px < 4; px++) {
            const uint8_t code = (src1 >> (6 - px * 2)) & 0x03;
            const uint8_t mask = 0x08 >> px;
            if (code == 0x00)       black_byte &= ~mask;
            else if (code >= 0x02)  color_byte &= ~mask;
        }

        black_plane[out] = black_byte;
        color_plane[out] = color_byte;
    }
}

static void epdDisplayPreparedPlanes(const uint8_t* black_plane, const uint8_t* color_plane) {
    gdey0583InitController();
    gdey0583WriteImage(black_plane, color_plane);
    gdey0583Refresh();
}

static void epdDisplayMonoFrame(const uint8_t* image) {
    memset(epdColorPlaneBuffer(), 0xFF, IMG_BUF_LEN);
    epdDisplayPreparedPlanes(image, epdColorPlaneBuffer());
}

// ── Public epd* contract ─────────────────────────────────────

void gpioInit() {
    pinMode(PIN_EPD_BUSY, INPUT);
    pinMode(PIN_EPD_RST,  OUTPUT);
    pinMode(PIN_EPD_DC,   OUTPUT);
    pinMode(PIN_EPD_CS,   OUTPUT);
    pinMode(PIN_EPD_SCK,  OUTPUT);
    pinMode(PIN_EPD_MOSI, OUTPUT);
    pinMode(PIN_CFG_BTN,  INPUT_PULLUP);
    digitalWrite(PIN_EPD_RST, HIGH);
    digitalWrite(PIN_EPD_CS,  HIGH);
    digitalWrite(PIN_EPD_SCK, LOW);
}

void epdInit() {
    gdey0583InitController();
}

void epdInitFast() {
    epdInit();
}

void epdDisplay(const uint8_t* image) {
    epdDisplayMonoFrame(image);
}

void epdDisplay2bpp(const uint8_t* image2bpp) {
    decodeRaw2bppToTriColorPlanes(image2bpp, imgBuf, epdColorPlaneBuffer());
    epdDisplayPreparedPlanes(imgBuf, epdColorPlaneBuffer());
}

void epdDisplayFast(const uint8_t* image) {
    epdDisplay(image);
}

void epdPartialDisplay(uint8_t* data, int xStart, int yStart, int xEnd, int yEnd) {
    (void)data; (void)xStart; (void)yStart; (void)xEnd; (void)yEnd;
    epdDisplay(imgBuf);
}

void epdSleep() {
    if (!gdey0583_initialized) return;
    gdey0583WriteCommand(0x02);  // power off (GDEQ0583Z31 _PowerOff)
    gdey0583WaitBusy(5000);
    gdey0583WriteCommand(0x07);  // deep sleep (GDEQ0583Z31 hibernate)
    gdey0583WriteData(0xA5);
    delay(20);
    gdey0583_initialized = false;
}

#endif
