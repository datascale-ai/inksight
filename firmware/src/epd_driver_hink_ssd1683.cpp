#include "epd_driver.h"
#include "config.h"

#if defined(EPD_PANEL_42_HINK_SSD1683)

// HINK 4.2" Black/White/Red tri-color e-ink panel
// Controller: SSD1683
// Reference: GxEPD2 src/gdey3c/GxEPD2_420c_GDEY042Z98.cpp (SSD1683)
// BUSY=HIGH means busy; wait for LOW.

#include <SPI.h>

#ifndef EPD_GXEPD2_SPI_HZ
#define EPD_GXEPD2_SPI_HZ 4000000
#endif

static bool ssd1683_initialized = false;

static uint8_t* epdColorPlaneBuffer() {
    return colorBuf + IMG_BUF_LEN;
}

// ── Low-level SPI helpers ────────────────────────────────────

static void ssd1683BeginTransfer(bool data_mode) {
    digitalWrite(PIN_EPD_DC, data_mode ? HIGH : LOW);
    digitalWrite(PIN_EPD_CS, LOW);
    SPI.beginTransaction(SPISettings(EPD_GXEPD2_SPI_HZ, MSBFIRST, SPI_MODE0));
}

static void ssd1683EndTransfer() {
    SPI.endTransaction();
    digitalWrite(PIN_EPD_CS, HIGH);
}

static void ssd1683WriteCommand(uint8_t cmd) {
    ssd1683BeginTransfer(false);
    SPI.transfer(cmd);
    ssd1683EndTransfer();
}

static void ssd1683WriteData(uint8_t data) {
    ssd1683BeginTransfer(true);
    SPI.transfer(data);
    ssd1683EndTransfer();
}

static void ssd1683WaitBusy(unsigned long timeout_ms = 30000) {
    const unsigned long t0 = millis();
    while (digitalRead(PIN_EPD_BUSY) == HIGH) {
        delay(10);
        if (millis() - t0 > timeout_ms) {
            Serial.println("SSD1683 busy timeout");
            return;
        }
    }
}

static void ssd1683Reset() {
    delay(20);
    digitalWrite(PIN_EPD_RST, LOW);
    delay(20);
    digitalWrite(PIN_EPD_RST, HIGH);
    delay(130);
}

// ── 2bpp decode ──────────────────────────────────────────────
// raw2bpp lives in colorBuf[0..COLOR_BUF_LEN-1].
// color_plane reuses the upper half (colorBuf + IMG_BUF_LEN).
// DO NOT memset color_plane: it would clobber unread 2bpp source bytes
// for out >= IMG_BUF_LEN/2, producing a solid-black bottom half.
// Active-LOW convention (matches uc8179/gdey0583): 0=black/color, 1=white/no-color.
// Loop runs backward so writes to color_plane never overtake reads from raw2bpp.

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
            if (code == 0x00)      black_byte &= ~mask;
            else if (code >= 0x02) color_byte &= ~mask;
        }
        for (int px = 0; px < 4; px++) {
            const uint8_t code = (src1 >> (6 - px * 2)) & 0x03;
            const uint8_t mask = 0x08 >> px;
            if (code == 0x00)      black_byte &= ~mask;
            else if (code >= 0x02) color_byte &= ~mask;
        }

        black_plane[out] = black_byte;
        color_plane[out] = color_byte;
    }
}

// ── RAM window + pointer reset ───────────────────────────────
// Called before each plane write (matches GDEY042Z98/SSD1683 reference).
// SSD1683 requires full window re-declaration to correctly reset
// the Y address counter after a previous plane write.

static void ssd1683SetFullWindowAndPointer() {
    ssd1683WriteCommand(0x11);  // data entry mode: X inc, Y inc
    ssd1683WriteData(0x03);
    ssd1683WriteCommand(0x44);  // RAM X window
    ssd1683WriteData(0x00);
    ssd1683WriteData((W - 1) / 8);
    ssd1683WriteCommand(0x45);  // RAM Y window
    ssd1683WriteData(0x00);
    ssd1683WriteData(0x00);
    ssd1683WriteData((H - 1) & 0xFF);
    ssd1683WriteData(((H - 1) >> 8) & 0xFF);
    ssd1683WriteCommand(0x4E);  // X address counter
    ssd1683WriteData(0x00);
    ssd1683WriteCommand(0x4F);  // Y address counter
    ssd1683WriteData(0x00);
    ssd1683WriteData(0x00);
}

// ── Controller init (follows GDEY042Z98/SSD1683 _InitDisplay) ─

static void ssd1683InitController() {
    if (ssd1683_initialized) return;

    const uint16_t y_end = H - 1;

    SPI.begin(PIN_EPD_SCK, -1, PIN_EPD_MOSI, PIN_EPD_CS);
    ssd1683Reset();

    ssd1683WriteCommand(0x12);  // software reset
    delay(10);                  // SSD1683 datasheet: wait ≥10ms after SWRESET

    ssd1683WriteCommand(0x01);  // driver output control
    ssd1683WriteData(y_end & 0xFF);
    ssd1683WriteData((y_end >> 8) & 0xFF);
    ssd1683WriteData(0x00);

    ssd1683WriteCommand(0x3C);  // border waveform
    ssd1683WriteData(0x05);

    ssd1683WriteCommand(0x18);  // internal temperature sensor
    ssd1683WriteData(0x80);

    ssd1683SetFullWindowAndPointer();

    ssd1683_initialized = true;
}

// ── Frame write ──────────────────────────────────────────────
// 0x24 BW RAM:    active-LOW (0=black, 1=white)
// 0x26 color RAM: active-HIGH (1=red/color, 0=no-color)
// black_plane/color_plane from decode: active-LOW (0=black/color, 1=white/no-color)
// → 0x24: write directly; 0x26: invert before writing.

static void ssd1683WriteFrame(const uint8_t* black_plane, const uint8_t* color_plane) {
    ssd1683InitController();

    ssd1683SetFullWindowAndPointer();
    ssd1683WriteCommand(0x26);  // color RAM (active-HIGH) ← invert active-LOW color_plane
    ssd1683BeginTransfer(true);
    for (int i = 0; i < IMG_BUF_LEN; i++) {
        SPI.transfer(color_plane ? static_cast<uint8_t>(~color_plane[i]) : 0x00);
    }
    ssd1683EndTransfer();

    ssd1683SetFullWindowAndPointer();
    ssd1683WriteCommand(0x24);  // BW RAM (active-LOW) ← write directly
    ssd1683BeginTransfer(true);
    for (int i = 0; i < IMG_BUF_LEN; i++) {
        SPI.transfer(black_plane ? black_plane[i] : 0xFF);
    }
    ssd1683EndTransfer();

    ssd1683WriteCommand(0x22);  // display update sequence: clock+analog, load LUT+temp, display, disable
    ssd1683WriteData(0xF7);
    ssd1683WriteCommand(0x20);  // master activation
    ssd1683WaitBusy();
}

static void ssd1683DisplayMonoFrame(const uint8_t* image) {
    ssd1683InitController();

    ssd1683SetFullWindowAndPointer();
    ssd1683WriteCommand(0x26);  // color RAM: all 0x00 = no color
    ssd1683BeginTransfer(true);
    for (int i = 0; i < IMG_BUF_LEN; i++) {
        SPI.transfer(0x00);
    }
    ssd1683EndTransfer();

    ssd1683SetFullWindowAndPointer();
    ssd1683WriteCommand(0x24);  // BW RAM: image is 0=black (active-LOW), write directly
    ssd1683BeginTransfer(true);
    for (int i = 0; i < IMG_BUF_LEN; i++) {
        SPI.transfer(image[i]);
    }
    ssd1683EndTransfer();

    ssd1683WriteCommand(0x22);
    ssd1683WriteData(0xF7);
    ssd1683WriteCommand(0x20);
    ssd1683WaitBusy();
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
    ssd1683InitController();
}

void epdInitFast() {
    epdInit();
}

void epdDisplay(const uint8_t* image) {
    ssd1683DisplayMonoFrame(image);
}

void epdDisplay2bpp(const uint8_t* image2bpp) {
    decodeRaw2bppToTriColorPlanes(image2bpp, imgBuf, epdColorPlaneBuffer());
    ssd1683WriteFrame(imgBuf, epdColorPlaneBuffer());
}

void epdDisplayFast(const uint8_t* image) {
    epdDisplay(image);
}

void epdPartialDisplay(uint8_t* data, int xStart, int yStart, int xEnd, int yEnd) {
    (void)data; (void)xStart; (void)yStart; (void)xEnd; (void)yEnd;
    epdDisplay(imgBuf);
}

void epdSleep() {
    if (!ssd1683_initialized) return;
    ssd1683WriteCommand(0x10);  // deep sleep
    ssd1683WriteData(0x11);
    delay(20);
    ssd1683_initialized = false;
}

#endif
