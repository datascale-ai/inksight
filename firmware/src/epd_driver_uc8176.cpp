#include "epd_driver.h"
#include "config.h"

#if defined(EPD_PANEL_42_UC8176)

#include <SPI.h>
#include <GxEPD2_3C.h>
#include <epd3c/GxEPD2_420c.h>

#ifndef EPD_GXEPD2_SPI_HZ
#define EPD_GXEPD2_SPI_HZ 4000000
#endif

// Use the 4.2" UC8176 tri-color path for 400x300 black/white/red panels.
static GxEPD2_3C<GxEPD2_420c, GxEPD2_420c::HEIGHT / 4> display(
    GxEPD2_420c(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));

static bool uc8176_initialized = false;

static uint8_t* epdColorPlaneBuffer() {
    return colorBuf + IMG_BUF_LEN;
}

static void decodeRaw2bppToTriColorPlanes(const uint8_t* raw2bpp, uint8_t* black_plane, uint8_t* color_plane) {
    // raw2bpp lives in colorBuf(), and color_plane reuses its upper half.
    // Clearing color_plane here would destroy unread 2bpp source bytes.
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

static void uc8176WriteFrame(const uint8_t* black_plane, const uint8_t* color_plane) {
    display.writeImage(black_plane, color_plane, 0, 0, W, H, false, false, false);
    display.refresh(false);
    display.powerOff();
}

static void uc8176DisplayMonoFrame(const uint8_t* image) {
    memset(epdColorPlaneBuffer(), 0xFF, IMG_BUF_LEN);
    uc8176WriteFrame(image, epdColorPlaneBuffer());
}

void gpioInit() {
    pinMode(PIN_CFG_BTN, INPUT_PULLUP);
    SPI.begin(PIN_EPD_SCK, -1, PIN_EPD_MOSI, PIN_EPD_CS);
}

void epdInit() {
    if (uc8176_initialized) return;

    display.epd2.selectSPI(SPI, SPISettings(EPD_GXEPD2_SPI_HZ, MSBFIRST, SPI_MODE0));
    display.init(0);
    display.setRotation(0);
    uc8176_initialized = true;
}

void epdInitFast() {
    epdInit();
}

void epdDisplay(const uint8_t* image) {
    epdInit();
    uc8176DisplayMonoFrame(image);
}

void epdDisplay2bpp(const uint8_t* image2bpp) {
    epdInit();
    decodeRaw2bppToTriColorPlanes(image2bpp, imgBuf, epdColorPlaneBuffer());
    uc8176WriteFrame(imgBuf, epdColorPlaneBuffer());
}

void epdDisplayFast(const uint8_t* image) {
    epdDisplay(image);
}

void epdPartialDisplay(uint8_t* data, int xStart, int yStart, int xEnd, int yEnd) {
    (void)data;
    (void)xStart;
    (void)yStart;
    (void)xEnd;
    (void)yEnd;
    epdDisplay(imgBuf);
}

void epdSleep() {
    if (!uc8176_initialized) return;
    display.hibernate();
    uc8176_initialized = false;
}

#endif
