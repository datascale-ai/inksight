// Exercise the production driver through GPIO, decoding its SPI wire output.
#include "config.h"
#include "epd_driver.h"

#include <array>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

uint8_t imgBuf[IMG_BUF_LEN];
FakeSerial Serial;

struct Command {
    uint8_t code;
    unsigned mask;
    unsigned long time;
    std::vector<uint8_t> data[2];
};
enum class Busy { Normal, NeverAsserted, PowerOnTimeout, RefreshTimeout, PowerOffTimeout };
static Busy busyMode = Busy::Normal;
static std::vector<Command> commands;
static std::vector<std::string> logs;
static std::array<int, 32> levels{};
static std::array<int, 32> modes{};
static int lastCommand[2] = {-1, -1};
static unsigned long nowMs = 0, busyStart = 0, busyEnd = 0;
static uint8_t busyCommand = 0, spiByte = 0;
static int spiBits = 0, resetCount = 0;

void pinMode(int pin, int mode) { modes.at(pin) = mode; }
unsigned long millis() { return nowMs; }
void delay(unsigned long ms) { nowMs += ms; }
void FakeSerial::printf(const char *format, ...) {
    char message[256];
    va_list args;
    va_start(args, format);
    vsnprintf(message, sizeof(message), format, args);
    va_end(args);
    logs.emplace_back(message);
}

void digitalWrite(int pin, int value) {
    if (pin == PIN_EPD_RST && value == HIGH && levels.at(pin) == LOW) ++resetCount;
    levels.at(pin) = value;
    if (pin != PIN_EPD_SCK || value != HIGH) return;
    spiByte = static_cast<uint8_t>((spiByte << 1) | levels.at(PIN_EPD_MOSI));
    if (++spiBits != 8) return;
    spiBits = 0;
    unsigned mask = (levels.at(PIN_EPD_CS) == LOW ? 1 : 0)
                  | (levels.at(PIN_EPD_CS2) == LOW ? 2 : 0);
    assert(mask != 0);
    if (levels.at(PIN_EPD_DC) == LOW) {
        commands.push_back({spiByte, mask, nowMs, {}});
        for (int ic = 0; ic < 2; ++ic) {
            if (mask & (1 << ic)) lastCommand[ic] = static_cast<int>(commands.size()) - 1;
        }
        if (spiByte == 0x04 || spiByte == 0x12 || spiByte == 0x02) {
            busyCommand = spiByte;
            busyStart = nowMs + (spiByte == 0x12 ? 20 : 5);
            busyEnd = nowMs + (spiByte == 0x12 ? 600 : 35);
        }
    } else {
        for (int ic = 0; ic < 2; ++ic) {
            if (!(mask & (1 << ic))) continue;
            assert(lastCommand[ic] >= 0);
            commands.at(lastCommand[ic]).data[ic].push_back(spiByte);
        }
    }
}

int digitalRead(int pin) {
    assert(pin == PIN_EPD_BUSY);
    if (busyMode == Busy::NeverAsserted) return HIGH;
    bool stuck = (busyMode == Busy::PowerOnTimeout && busyCommand == 0x04)
              || (busyMode == Busy::RefreshTimeout && busyCommand == 0x12)
              || (busyMode == Busy::PowerOffTimeout && busyCommand == 0x02);
    return nowMs >= busyStart && (stuck || nowMs < busyEnd) ? LOW : HIGH;
}

static void begin(Busy mode = Busy::Normal) {
    epdSleep();
    commands.clear();
    logs.clear();
    busyMode = mode;
    nowMs = busyStart = busyEnd = 0;
    busyCommand = 0;
    resetCount = 0;
    lastCommand[0] = lastCommand[1] = -1;
    spiBits = 0;
}

static const Command &get(uint8_t code) {
    for (const auto &cmd : commands) if (cmd.code == code) return cmd;
    assert(false && "Missing command");
    return commands.front();
}

static void expect(uint8_t code, std::initializer_list<uint8_t> data) {
    for (const auto &payload : get(code).data) assert(payload == std::vector<uint8_t>(data));
}

static void checkFrame(const uint8_t *image) {
    const auto &frame = get(0x10);
    for (int ic = 0; ic < 2; ++ic) {
        assert(frame.data[ic].size() == 15000);
        for (int y = 0; y < 300; ++y) {
            for (int x = 0; x < 200; ++x) {
                int sourceX = x + ic * 200;
                bool white = image[y * 50 + sourceX / 8] & (0x80 >> (sourceX % 8));
                int actual = (frame.data[ic][y * 50 + x / 4] >> (6 - (x % 4) * 2)) & 3;
                assert(actual == (white ? 0 : 3));
            }
        }
    }
}

static void checkLifecycle() {
    const std::vector<uint8_t> expected = {
        0x01, 0x04, 0x00, 0x50, 0x30, 0x61, 0x82,
        0x20, 0x21, 0x22, 0x23, 0x24, 0x10, 0xe0, 0x12, 0x02, 0x07,
    };
    assert(commands.size() == expected.size());
    for (size_t i = 0; i < expected.size(); ++i) {
        assert(commands[i].code == expected[i]);
        assert(commands[i].mask == 3);
    }
    expect(0x01, {0x07, 0x00, 0x0d, 0x00});
    expect(0x00, {0xdf});
    expect(0x50, {0x67});
    expect(0x30, {0x2a});
    expect(0x61, {0xc8, 0x01, 0x2c});
    expect(0x82, {0x0a});
    expect(0x20, {0x19, 0x1e, 0x04, 0x28, 0x28, 0x05, 0x1e, 0x19, 0x04, 0, 0, 0, 0, 0, 0});
    expect(0x21, {0x19, 0x5e, 0x04, 0xa8, 0x68, 0x05, 0x9e, 0x19, 0x04, 0, 0, 0, 0, 0, 0});
    for (uint8_t cmd = 0x22; cmd <= 0x24; ++cmd) {
        expect(cmd, {0x99, 0x9e, 0x04, 0xa8, 0x68, 0x05, 0x5e, 0x59, 0x04, 0, 0, 0, 0, 0, 0});
    }
    expect(0xe0, {1});
    expect(0x07, {0xa5});
    assert(get(0x02).time - get(0x12).time >= 600);
    assert(get(0x07).time - get(0x02).time >= 35);
    assert(resetCount == 1);
    assert(levels.at(PIN_EPD_CS) == HIGH && levels.at(PIN_EPD_CS2) == HIGH);
    size_t count = commands.size();
    epdSleep();
    assert(commands.size() == count);
}

int main() {
    gpioInit();
    assert(PIN_EPD_CS == 7 && PIN_EPD_CS2 == 8);
    assert(modes.at(PIN_EPD_CS2) == OUTPUT && modes.at(PIN_EPD_BUSY) == INPUT_PULLUP);
    assert(!epdSupportsPartialRefresh());
    for (int value : {0xff, 0x00}) {
        memset(imgBuf, value, sizeof(imgBuf));
        begin();
        epdDisplay(imgBuf);
        checkFrame(imgBuf);
        checkLifecycle();
    }
    // Asymmetric pattern covers all input bytes, both halves, row order and bit order.
    for (int i = 0; i < IMG_BUF_LEN; ++i) imgBuf[i] = static_cast<uint8_t>(i * 73 + i / 50);
    begin();
    epdDisplayFast(imgBuf);
    checkFrame(imgBuf);
    checkLifecycle();
    begin();
    uint8_t region[1] = {0};
    epdPartialDisplayWithOld(region, region, 8, 10, 16, 11);
    checkFrame(imgBuf);  // The fallback must not read the tiny region buffer.
    checkLifecycle();
    begin();
    epdInit();
    epdDisplay(imgBuf);
    assert(resetCount == 2);
    checkFrame(imgBuf);

    for (Busy mode : {Busy::PowerOnTimeout, Busy::RefreshTimeout, Busy::PowerOffTimeout}) {
        begin(mode);
        epdDisplay(imgBuf);
        assert(nowMs < 40000);
        assert(commands[commands.size() - 2].code == 0x02);
        assert(commands.back().code == 0x07);
        bool timeoutLogged = false;
        for (const auto &line : logs) if (line.find("timeout") != std::string::npos) timeoutLogged = true;
        assert(timeoutLogged);
        if (mode == Busy::PowerOnTimeout) {
            for (const auto &cmd : commands) assert(cmd.code != 0x10 && cmd.code != 0x12);
        }
    }
    begin(Busy::NeverAsserted);
    epdDisplay(imgBuf);
    checkFrame(imgBuf);
    assert(get(0x02).time - get(0x12).time >= 20000);
    puts("UC8154: pixel mapping, registers, lifecycle, fallbacks and BUSY failures passed");
}
