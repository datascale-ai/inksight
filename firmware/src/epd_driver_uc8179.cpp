#include "epd_driver.h"
#include "config.h"

#if defined(EPD_PANEL_75_GDEY075Z08)

#include <SPI.h>

#ifndef EPD_GXEPD2_SPI_HZ
#define EPD_GXEPD2_SPI_HZ 4000000
#endif

static bool uc8179_initialized = false;

// The 7.5" UC8179 path still implements the same public epd* contract used by
// the rest of the project. These helpers only prepare the controller-specific
// black/red planes behind that interface.
static uint8_t* epdColorPlaneBuffer() {
    return colorBuf + IMG_BUF_LEN;
}

static void uc8179BeginTransfer(bool data_mode) {
    digitalWrite(PIN_EPD_DC, data_mode ? HIGH : LOW);
    digitalWrite(PIN_EPD_CS, LOW);
    SPI.beginTransaction(SPISettings(EPD_GXEPD2_SPI_HZ, MSBFIRST, SPI_MODE0));
}

static void uc8179EndTransfer() {
    SPI.endTransaction();
    digitalWrite(PIN_EPD_CS, HIGH);
}

static void uc8179WriteCommand(uint8_t cmd) {
    uc8179BeginTransfer(false);
    SPI.transfer(cmd);
    uc8179EndTransfer();
}

static void uc8179WriteData(uint8_t data) {
    uc8179BeginTransfer(true);
    SPI.transfer(data);
    uc8179EndTransfer();
}

static void uc8179WaitBusy(unsigned long timeout_ms = 30000) {
    const unsigned long t0 = millis();
    while (digitalRead(PIN_EPD_BUSY) == LOW) {
        delay(10);
        if (millis() - t0 > timeout_ms) {
            Serial.println("UC8179 busy timeout");
            return;
        }
    }
}

static void uc8179Reset() {
    digitalWrite(PIN_EPD_RST, HIGH);
    delay(10);
    digitalWrite(PIN_EPD_RST, LOW);
    delay(10);
    digitalWrite(PIN_EPD_RST, HIGH);
    delay(10);
}

static void uc8179WriteWindow(uint16_t x, uint16_t y, uint16_t w, uint16_t h) {
    const uint16_t xe = (x + w - 1) | 0x0007;
    const uint16_t ye = y + h - 1;
    x &= 0xFFF8;

    uc8179WriteCommand(0x90);
    uc8179WriteData(x >> 8);
    uc8179WriteData(x & 0xFF);
    uc8179WriteData(xe >> 8);
    uc8179WriteData(xe & 0xFF);
    uc8179WriteData(y >> 8);
    uc8179WriteData(y & 0xFF);
    uc8179WriteData(ye >> 8);
    uc8179WriteData(ye & 0xFF);
    uc8179WriteData(0x00);
}

static void uc8179PowerOn() {
    uc8179WriteCommand(0x04);
    uc8179WaitBusy(500);
}

static void uc8179PowerOff() {
    uc8179WriteCommand(0x02);
    uc8179WaitBusy(500);
}

static void uc8179InitController() {
    if (uc8179_initialized) return;

    SPI.begin(PIN_EPD_SCK, -1, PIN_EPD_MOSI, PIN_EPD_CS);

    uc8179Reset();

    uc8179WriteCommand(0x01);
    uc8179WriteData(0x07);
    uc8179WriteData(0x07);
    uc8179WriteData(0x3F);
    uc8179WriteData(0x3F);

    uc8179WriteCommand(0x00);
    uc8179WriteData(0x0F);

    uc8179WriteCommand(0x61);
    uc8179WriteData(W >> 8);
    uc8179WriteData(W & 0xFF);
    uc8179WriteData(H >> 8);
    uc8179WriteData(H & 0xFF);

    uc8179WriteCommand(0x15);
    uc8179WriteData(0x00);

    // Match the known-good UC8179 reference implementation.
    uc8179WriteCommand(0x50);
    uc8179WriteData(0x77);

    uc8179WriteCommand(0x60);
    uc8179WriteData(0x22);

    uc8179_initialized = true;
}

static void decodeRaw2bppToTriColorPlanes(const uint8_t* raw2bpp, uint8_t* black_plane, uint8_t* color_plane) {
    // raw2bpp lives in colorBuf(), and color_plane reuses its upper half.
    // Clearing color_plane here would destroy unread 2bpp source bytes and
    // turns the lower part of mixed images into solid red (0xFF => 0b11).
    memset(black_plane, 0xFF, IMG_BUF_LEN);

    for (int out = IMG_BUF_LEN - 1; out >= 0; out--) {
        const uint8_t src0 = raw2bpp[out * 2];
        const uint8_t src1 = raw2bpp[out * 2 + 1];
        uint8_t black_byte = 0xFF;
        uint8_t color_byte = 0xFF;

        for (int px = 0; px < 4; px++) {
            const uint8_t code = (src0 >> (6 - px * 2)) & 0x03;
            const uint8_t mask = 0x80 >> px;
            if (code == 0x00) {
                black_byte &= ~mask;
            } else if (code >= 0x02) {
                color_byte &= ~mask;
            }
        }
        for (int px = 0; px < 4; px++) {
            const uint8_t code = (src1 >> (6 - px * 2)) & 0x03;
            const uint8_t mask = 0x08 >> px;
            if (code == 0x00) {
                black_byte &= ~mask;
            } else if (code >= 0x02) {
                color_byte &= ~mask;
            }
        }

        black_plane[out] = black_byte;
        color_plane[out] = color_byte;
    }
}

static void uc8179WritePlane(uint8_t command, const uint8_t* buffer, uint8_t fill, bool invert = false) {
    uc8179WriteCommand(command);
    uc8179BeginTransfer(true);
    for (int i = 0; i < IMG_BUF_LEN; i++) {
        uint8_t value = buffer ? buffer[i] : fill;
        if (invert) value = ~value;
        SPI.transfer(value);
    }
    uc8179EndTransfer();
}

static void uc8179WriteImage(const uint8_t* black_plane, const uint8_t* color_plane, bool invert_color = false) {
    uc8179WriteCommand(0x91);
    uc8179WriteWindow(0, 0, W, H);
    uc8179WritePlane(0x10, black_plane, 0xFF, false);
    uc8179WritePlane(0x13, color_plane, 0xFF, invert_color);
    uc8179WriteCommand(0x92);
}

static void uc8179Refresh() {
    uc8179PowerOn();
    uc8179WriteWindow(0, 0, W, H);
    uc8179WriteCommand(0x12);
    delay(100);
    uc8179WaitBusy(30000);
    uc8179PowerOff();
}

static void uc8179ClearWhite() {
    uc8179WriteImage(nullptr, nullptr, false);
    uc8179Refresh();
}

static void epdDisplayPreparedPlanes(const uint8_t* black_plane, const uint8_t* color_plane) {
    uc8179InitController();
    uc8179WriteImage(black_plane, color_plane, false);
    uc8179Refresh();
}

static void epdDisplayMonoFrame(const uint8_t* image) {
    memset(epdColorPlaneBuffer(), 0xFF, IMG_BUF_LEN);
    epdDisplayPreparedPlanes(image, epdColorPlaneBuffer());
}

void gpioInit() {
    pinMode(PIN_EPD_BUSY, INPUT);
    pinMode(PIN_EPD_RST, OUTPUT);
    pinMode(PIN_EPD_DC, OUTPUT);
    pinMode(PIN_EPD_CS, OUTPUT);
    pinMode(PIN_EPD_SCK, OUTPUT);
    pinMode(PIN_EPD_MOSI, OUTPUT);
    pinMode(PIN_CFG_BTN, INPUT_PULLUP);
    digitalWrite(PIN_EPD_RST, HIGH);
    digitalWrite(PIN_EPD_CS, HIGH);
    digitalWrite(PIN_EPD_SCK, LOW);
}

void epdInit() {
    uc8179InitController();
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
    // This panel path currently uses the same stable full-refresh flow for fast
    // refresh requests, matching the project's existing "safe fallback" style.
    epdDisplay(image);
}

void epdPartialDisplay(uint8_t* data, int xStart, int yStart, int xEnd, int yEnd) {
    (void)data;
    (void)xStart;
    (void)yStart;
    (void)xEnd;
    (void)yEnd;
    // Partial refresh is not implemented for the UC8179 tri-color path yet, so
    // keep using the project's existing full-frame fallback behavior.
    epdDisplay(imgBuf);
}

void epdSleep() {
    if (!uc8179_initialized) return;
    uc8179PowerOff();
    uc8179WriteCommand(0x07);
    uc8179WriteData(0xA5);
    delay(20);
    uc8179_initialized = false;
}

#endif
