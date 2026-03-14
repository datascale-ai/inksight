#include "epd_driver.h"
#include "config.h"

#if defined(EPD_PANEL_42)

// ── Software SPI (bit-bang) for 4.2" Waveshare V2 (SSD1683) ──
// Avoids Busy Timeout on ESP32-C3 with non-default pins; no GxEPD2 dependency.

static void spiWriteByte(uint8_t data) {
    for (int i = 0; i < 8; i++) {
        digitalWrite(PIN_EPD_MOSI, (data & 0x80) ? HIGH : LOW);
        data <<= 1;
        digitalWrite(PIN_EPD_SCK, HIGH);
        digitalWrite(PIN_EPD_SCK, LOW);
    }
}

static void epdSendCommand(uint8_t cmd) {
    digitalWrite(PIN_EPD_DC, LOW);   // DC low = command
    digitalWrite(PIN_EPD_CS, LOW);
    spiWriteByte(cmd);
    digitalWrite(PIN_EPD_CS, HIGH);
}

static void epdSendData(uint8_t data) {
    digitalWrite(PIN_EPD_DC, HIGH);  // DC high = data
    digitalWrite(PIN_EPD_CS, LOW);
    spiWriteByte(data);
    digitalWrite(PIN_EPD_CS, HIGH);
}

static void epdWaitBusy() {
    unsigned long t0 = millis();
    while (digitalRead(PIN_EPD_BUSY) == HIGH) {
        delay(10);
        if (millis() - t0 > 10000) {
            Serial.println("EPD busy TIMEOUT!");
            return;
        }
    }
}

static void epdReset() {
    digitalWrite(PIN_EPD_RST, HIGH); delay(100);
    digitalWrite(PIN_EPD_RST, LOW);  delay(2);
    digitalWrite(PIN_EPD_RST, HIGH); delay(100);
}

// ── Helper: configure RAM window for full screen ────────────

static void epdSetFullWindow() {
    epdSendCommand(0x11);  // Data Entry Mode Setting
    epdSendData(0x03);     //   X increment, Y increment

    epdSendCommand(0x44);  // Set RAM X address range
    epdSendData(0x00);
    epdSendData((W - 1) / 8);

    epdSendCommand(0x45);  // Set RAM Y address range
    epdSendData(0x00);
    epdSendData(0x00);
    epdSendData((H - 1) & 0xFF);
    epdSendData(((H - 1) >> 8) & 0xFF);

    epdSendCommand(0x4E);  // Set RAM X address counter
    epdSendData(0x00);

    epdSendCommand(0x4F);  // Set RAM Y address counter
    epdSendData(0x00);
    epdSendData(0x00);
}

// ── GPIO initialization ─────────────────────────────────────

void gpioInit() {
    pinMode(PIN_EPD_BUSY, INPUT);
    pinMode(PIN_EPD_RST,  OUTPUT);
    pinMode(PIN_EPD_DC,   OUTPUT);
    pinMode(PIN_EPD_CS,   OUTPUT);
    pinMode(PIN_EPD_SCK,  OUTPUT);
    pinMode(PIN_EPD_MOSI, OUTPUT);
    pinMode(PIN_CFG_BTN,  INPUT_PULLUP);
    digitalWrite(PIN_EPD_CS,  HIGH);
    digitalWrite(PIN_EPD_SCK, LOW);
}

// ── EPD full init (standard mode, Waveshare 4.2" V2 SSD1683) ──

void epdInit() {
    epdReset();
    epdWaitBusy();

    epdSendCommand(0x12);  // Software Reset
    epdWaitBusy();

    epdSendCommand(0x21);  // Display Update Control 1
    epdSendData(0x40);     //   Source output mode
    epdSendData(0x00);

    epdSendCommand(0x3C);  // Border Waveform Control
    epdSendData(0x05);

    epdSetFullWindow();
    epdWaitBusy();
}

// ── EPD fast init (loads fast-refresh LUT via temperature register) ──
// Based on official Waveshare epd4in2_V2 Init_Fast() implementation.
// The 0x1A register sets a temperature value that selects faster internal LUT.
// 0x6E = ~1.5s refresh, 0x5A = ~1s refresh.

void epdInitFast() {
    epdReset();
    epdWaitBusy();

    epdSendCommand(0x12);  // Software Reset
    epdWaitBusy();

    epdSendCommand(0x21);  // Display Update Control 1
    epdSendData(0x40);
    epdSendData(0x00);

    epdSendCommand(0x3C);  // Border Waveform Control
    epdSendData(0x05);

    epdSendCommand(0x1A);  // Write to temperature register
    epdSendData(0x6E);     //   Value for ~1.5s fast refresh

    epdSendCommand(0x22);  // Display Update Control 2
    epdSendData(0x91);     //   Load temperature + Load LUT, then power down
    epdSendCommand(0x20);  // Master Activation
    epdWaitBusy();

    epdSetFullWindow();
    epdWaitBusy();
}

// ── EPD full-screen display (standard full refresh, 0xF7) ───
// Clears all ghosting but has visible black-white flash (~3-4s).

void epdDisplay(const uint8_t *image) {
    epdInit();

    int w = W / 8;

    epdSendCommand(0x24);  // Write Black/White RAM
    for (int j = 0; j < H; j++)
        for (int i = 0; i < w; i++)
            epdSendData(image[i + j * w]);

    epdSendCommand(0x26);  // Write RED RAM (old data for refresh)
    for (int j = 0; j < H; j++)
        for (int i = 0; i < w; i++)
            epdSendData(image[i + j * w]);

    epdSendCommand(0x22);  // Display Update Control 2
    epdSendData(0xF7);     //   Full update sequence
    epdSendCommand(0x20);  // Activate Display Update Sequence
    epdWaitBusy();
}

// ── EPD full-screen display (fast refresh, 0xC7) ────────────
// Much less flashing than full refresh (~1.5s).
// Requires epdInitFast() to be called first to load the fast LUT.

void epdDisplayFast(const uint8_t *image) {
    epdInitFast();

    int w = W / 8;

    epdSendCommand(0x24);  // Write Black/White RAM
    for (int j = 0; j < H; j++)
        for (int i = 0; i < w; i++)
            epdSendData(image[i + j * w]);

    epdSendCommand(0x26);  // Write RED RAM
    for (int j = 0; j < H; j++)
        for (int i = 0; i < w; i++)
            epdSendData(image[i + j * w]);

    epdSendCommand(0x22);  // Display Update Control 2
    epdSendData(0xC7);     //   Fast update: skip LUT load (already loaded by InitFast)
    epdSendCommand(0x20);  // Activate Display Update Sequence
    epdWaitBusy();
}

// ── EPD partial refresh ─────────────────────────────────────

void epdPartialDisplay(uint8_t *data, int xStart, int yStart, int xEnd, int yEnd) {
    int xS = xStart / 8;
    int xE = (xEnd - 1) / 8;
    int width = xE - xS + 1;
    int count = width * (yEnd - yStart);

    epdSendCommand(0x3C);  // Border Waveform Control
    epdSendData(0x80);

    epdSendCommand(0x21);  // Display Update Control 1
    epdSendData(0x00);
    epdSendData(0x00);

    epdSendCommand(0x3C);  // Border Waveform Control
    epdSendData(0x80);

    epdSendCommand(0x44);  // Set RAM X address range
    epdSendData(xS & 0xFF);
    epdSendData(xE & 0xFF);

    epdSendCommand(0x45);  // Set RAM Y address range
    epdSendData(yStart & 0xFF);
    epdSendData((yStart >> 8) & 0xFF);
    epdSendData((yEnd - 1) & 0xFF);
    epdSendData(((yEnd - 1) >> 8) & 0xFF);

    epdSendCommand(0x4E);  // Set RAM X address counter
    epdSendData(xS & 0xFF);

    epdSendCommand(0x4F);  // Set RAM Y address counter
    epdSendData(yStart & 0xFF);
    epdSendData((yStart >> 8) & 0xFF);

    epdSendCommand(0x24);  // Write Black/White RAM
    for (int i = 0; i < count; i++)
        epdSendData(data[i]);

    epdSendCommand(0x22);  // Display Update Control 2
    epdSendData(0xFF);     //   Partial update sequence
    epdSendCommand(0x20);  // Activate Display Update Sequence
    epdWaitBusy();
}

// ── EPD sleep ───────────────────────────────────────────────

void epdSleep() {
    epdSendCommand(0x10);  // Deep Sleep Mode
    epdSendData(0x01);     //   Enter deep sleep
    delay(200);
}

#else
// ── Other panel sizes: GxEPD2 (hardware SPI) ─────────────────

#include <SPI.h>
#include <GxEPD2_BW.h>

#if defined(EPD_PANEL_29)
  #include <gdey/GxEPD2_290_GDEY029T94.h>
  GxEPD2_BW<GxEPD2_290_GDEY029T94, GxEPD2_290_GDEY029T94::HEIGHT> display(
      GxEPD2_290_GDEY029T94(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));
  static uint8_t rotated_buffer[IMG_BUF_LEN];

  static bool is_black_pixel(const uint8_t* buffer, int width, int x, int y) {
      int row_bytes = (width + 7) / 8;
      return (buffer[y * row_bytes + x / 8] & (0x80 >> (x % 8))) == 0;
  }

  static void set_black_pixel(uint8_t* buffer, int width, int x, int y) {
      int row_bytes = (width + 7) / 8;
      buffer[y * row_bytes + x / 8] &= ~(0x80 >> (x % 8));
  }

  static void rotate_landscape_to_panel(const uint8_t* source) {
      memset(rotated_buffer, 0xFF, sizeof(rotated_buffer));
      for (int src_y = 0; src_y < H; src_y++) {
          for (int src_x = 0; src_x < W; src_x++) {
              if (!is_black_pixel(source, W, src_x, src_y)) continue;
              int dst_x = src_y;
              int dst_y = W - 1 - src_x;
              set_black_pixel(rotated_buffer, GxEPD2_290_GDEY029T94::WIDTH, dst_x, dst_y);
          }
      }
  }
#elif defined(EPD_PANEL_583)
  #include <gdeq/GxEPD2_583_GDEQ0583T31.h>
  GxEPD2_BW<GxEPD2_583_GDEQ0583T31, GxEPD2_583_GDEQ0583T31::HEIGHT / 4> display(
      GxEPD2_583_GDEQ0583T31(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));
#elif defined(EPD_PANEL_75)
  #include <epd/GxEPD2_750_T7.h>
  GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT / 4> display(
      GxEPD2_750_T7(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));
#else
  #error "No EPD panel type defined. Use -DEPD_PANEL_42, -DEPD_PANEL_29, -DEPD_PANEL_583, or -DEPD_PANEL_75"
#endif

static bool _initialized = false;

void gpioInit() {
    pinMode(PIN_CFG_BTN, INPUT_PULLUP);
    SPI.begin(PIN_EPD_SCK, -1, PIN_EPD_MOSI, PIN_EPD_CS);
}

void epdInit() {
    if (!_initialized) {
        display.init(0);
        display.setRotation(1);
        _initialized = true;
    }
}

void epdInitFast() {
    epdInit();
}

void epdDisplay(const uint8_t *image) {
    epdInit();
#if defined(EPD_PANEL_29)
    rotate_landscape_to_panel(image);
    display.writeImage(
        rotated_buffer,
        0,
        0,
        GxEPD2_290_GDEY029T94::WIDTH,
        GxEPD2_290_GDEY029T94::HEIGHT,
        false,
        false,
        false
    );
#else
    display.writeImage(image, 0, 0, W, H, false, false, true);
#endif
    display.refresh(false);
    display.powerOff();
}

void epdDisplayFast(const uint8_t *image) {
    epdInit();
#if defined(EPD_PANEL_29)
    rotate_landscape_to_panel(image);
    display.writeImage(
        rotated_buffer,
        0,
        0,
        GxEPD2_290_GDEY029T94::WIDTH,
        GxEPD2_290_GDEY029T94::HEIGHT,
        false,
        false,
        false
    );
#else
    display.writeImage(image, 0, 0, W, H, false, false, true);
#endif
    display.refresh(true);
    display.powerOff();
}

void epdPartialDisplay(uint8_t *data, int xStart, int yStart, int xEnd, int yEnd) {
    epdInit();
#if defined(EPD_PANEL_29)
    rotate_landscape_to_panel(imgBuf);
    display.writeImage(
        rotated_buffer,
        0,
        0,
        GxEPD2_290_GDEY029T94::WIDTH,
        GxEPD2_290_GDEY029T94::HEIGHT,
        false,
        false,
        false
    );
    display.refresh(true);
#else
    int w = xEnd - xStart;
    int h = yEnd - yStart;
    display.writeImage(data, xStart, yStart, w, h, false, false, true);
    display.refresh(xStart, yStart, w, h);
#endif
    display.powerOff();
}

void epdSleep() {
    display.hibernate();
    _initialized = false;
}

#endif // EPD_PANEL_42
