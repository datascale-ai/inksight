#include "display.h"
#include "config.h"
#include "epd_driver.h"

// ── Unified 5x7 pixel font ─────────────────────────────────
// Each glyph is 5 columns x 7 rows, stored column-major.
// Bit 0 = top row, bit 6 = bottom row.

const uint8_t* getGlyph(char c) {
    // Uppercase letters
    static const uint8_t g_C[] = {0x3E,0x41,0x41,0x41,0x22};
    static const uint8_t g_F[] = {0x7F,0x09,0x09,0x09,0x01};
    static const uint8_t g_I[] = {0x00,0x41,0x7F,0x41,0x00};
    static const uint8_t g_O[] = {0x3E,0x41,0x41,0x41,0x3E};
    static const uint8_t g_R[] = {0x7F,0x09,0x19,0x29,0x46};
    static const uint8_t g_S[] = {0x26,0x49,0x49,0x49,0x32};
    static const uint8_t g_W[] = {0x3F,0x40,0x38,0x40,0x3F};

    // Lowercase letters
    static const uint8_t g_a[] = {0x20,0x54,0x54,0x54,0x78};
    static const uint8_t g_b[] = {0x7F,0x48,0x44,0x44,0x38};
    static const uint8_t g_c[] = {0x38,0x44,0x44,0x44,0x28};
    static const uint8_t g_d[] = {0x38,0x44,0x44,0x28,0x7F};
    static const uint8_t g_e[] = {0x38,0x54,0x54,0x54,0x18};
    static const uint8_t g_f[] = {0x00,0x08,0x7E,0x09,0x02};
    static const uint8_t g_g[] = {0x18,0xA4,0xA4,0xA4,0x7C};
    static const uint8_t g_h[] = {0x7F,0x08,0x04,0x04,0x78};
    static const uint8_t g_i[] = {0x00,0x44,0x7D,0x40,0x00};
    static const uint8_t g_k[] = {0x7F,0x10,0x28,0x44,0x00};
    static const uint8_t g_l[] = {0x00,0x41,0x7F,0x40,0x00};
    static const uint8_t g_m[] = {0x7C,0x04,0x18,0x04,0x78};
    static const uint8_t g_n[] = {0x7C,0x08,0x04,0x04,0x78};
    static const uint8_t g_o[] = {0x38,0x44,0x44,0x44,0x38};
    static const uint8_t g_p[] = {0x7C,0x14,0x14,0x14,0x08};
    static const uint8_t g_r[] = {0x7C,0x08,0x04,0x04,0x08};
    static const uint8_t g_s[] = {0x48,0x54,0x54,0x54,0x24};
    static const uint8_t g_t[] = {0x04,0x3F,0x44,0x40,0x20};
    static const uint8_t g_u[] = {0x3C,0x40,0x40,0x20,0x7C};
    static const uint8_t g_v[] = {0x1C,0x20,0x40,0x20,0x1C};
    static const uint8_t g_w[] = {0x3C,0x40,0x30,0x40,0x3C};

    // Digits 0-9
    static const uint8_t g_0[] = {0x3E,0x51,0x49,0x45,0x3E};
    static const uint8_t g_1[] = {0x00,0x42,0x7F,0x40,0x00};
    static const uint8_t g_2[] = {0x42,0x61,0x51,0x49,0x46};
    static const uint8_t g_3[] = {0x21,0x41,0x45,0x4B,0x31};
    static const uint8_t g_4[] = {0x18,0x14,0x12,0x7F,0x10};
    static const uint8_t g_5[] = {0x27,0x45,0x45,0x45,0x39};
    static const uint8_t g_6[] = {0x3C,0x4A,0x49,0x49,0x30};
    static const uint8_t g_7[] = {0x01,0x71,0x09,0x05,0x03};
    static const uint8_t g_8[] = {0x36,0x49,0x49,0x49,0x36};
    static const uint8_t g_9[] = {0x06,0x49,0x49,0x29,0x1E};

    // Special characters
    static const uint8_t g_colon[] = {0x00,0x00,0x36,0x36,0x00};
    static const uint8_t g_dash[]  = {0x08,0x08,0x08,0x08,0x08};
    static const uint8_t g_space[] = {0x00,0x00,0x00,0x00,0x00};

    switch (c) {
        // Uppercase
        case 'C': return g_C; case 'F': return g_F; case 'I': return g_I;
        case 'O': return g_O; case 'R': return g_R; case 'S': return g_S;
        case 'W': return g_W;
        // Lowercase
        case 'a': return g_a; case 'b': return g_b; case 'c': return g_c;
        case 'd': return g_d; case 'e': return g_e; case 'f': return g_f;
        case 'g': return g_g; case 'h': return g_h; case 'i': return g_i;
        case 'k': return g_k; case 'l': return g_l; case 'm': return g_m;
        case 'n': return g_n; case 'o': return g_o; case 'p': return g_p;
        case 'r': return g_r; case 's': return g_s; case 't': return g_t;
        case 'u': return g_u; case 'v': return g_v; case 'w': return g_w;
        // Digits
        case '0': return g_0; case '1': return g_1; case '2': return g_2;
        case '3': return g_3; case '4': return g_4; case '5': return g_5;
        case '6': return g_6; case '7': return g_7; case '8': return g_8;
        case '9': return g_9;
        // Special
        case ':': return g_colon; case '-': return g_dash;
        default:  return g_space;
    }
}

// ── Draw scaled text into imgBuf ────────────────────────────

void drawText(const char *msg, int x, int y, int scale) {
    int rowBytes = W / 8;
    int len = strlen(msg);

    for (int ci = 0; ci < len; ci++) {
        const uint8_t *glyph = getGlyph(msg[ci]);
        int cx = x + ci * (5 * scale + scale);
        for (int col = 0; col < 5; col++) {
            for (int row = 0; row < 7; row++) {
                if (glyph[col] & (1 << row)) {
                    for (int dy = 0; dy < scale; dy++) {
                        for (int dx = 0; dx < scale; dx++) {
                            int px = cx + col * scale + dx;
                            int py = y + row * scale + dy;
                            if (px >= 0 && px < W && py >= 0 && py < H)
                                imgBuf[py * rowBytes + px / 8] &= ~(0x80 >> (px % 8));
                        }
                    }
                }
            }
        }
    }
}

// ── Helper: calculate text width in pixels ──────────────────

static int textWidth(int charCount, int scale) {
    return charCount * (5 * scale + scale) - scale;
}

// ── Show WiFi setup screen ──────────────────────────────────

void showSetupScreen(const char *apName) {
    memset(imgBuf, 0xFF, IMG_BUF_LEN);

    // Title: "Setup WiFi" (scale 3, centered)
    const char *title = "Setup WiFi";
    int titleX = (W - textWidth(strlen(title), 3)) / 2;
    drawText(title, titleX, 40, 3);

    // "Connect phone to" (scale 2, centered)
    const char *line1 = "Connect phone to";
    int line1X = (W - textWidth(strlen(line1), 2)) / 2;
    drawText(line1, line1X, 110, 2);

    // AP name (scale 3, centered)
    int apX = (W - textWidth(strlen(apName), 3)) / 2;
    drawText(apName, apX, 145, 3);

    // "Open browser" (scale 2, centered)
    const char *line3 = "Open browser";
    int line3X = (W - textWidth(strlen(line3), 2)) / 2;
    drawText(line3, line3X, 200, 2);

    epdDisplay(imgBuf);
    Serial.printf("Setup screen shown: %s\n", apName);
}

// ── Show centered error message ─────────────────────────────

void showError(const char *msg) {
    memset(imgBuf, 0xFF, IMG_BUF_LEN);

    int scale = 2;
    int len = strlen(msg);
    int startX = (W - textWidth(len, scale)) / 2;
    int startY = H / 2 - 7;

    drawText(msg, startX, startY, scale);

    epdDisplay(imgBuf);
    Serial.printf("Error shown: %s\n", msg);
}

// ── Update time display (partial refresh) ───────────────────

// Time state (shared with network module)
extern int curHour, curMin, curSec;

void updateTimeDisplay() {
    int rgnW = (TIME_RGN_X1 - TIME_RGN_X0) / 8;
    int rgnH = TIME_RGN_Y1 - TIME_RGN_Y0;
    uint8_t partBuf[rgnW * rgnH];
    memset(partBuf, 0xFF, sizeof(partBuf));

    char ts[9];
    snprintf(ts, sizeof(ts), "%02d:%02d:%02d", curHour, curMin, curSec);

    int charW = 5;
    int gap = 1;
    int sx = 4;
    int sy = (rgnH - 7) / 2;

    for (int ci = 0; ci < 8; ci++) {
        const uint8_t *g = getGlyph(ts[ci]);
        int cx = sx + ci * (charW + gap);
        for (int col = 0; col < 5; col++) {
            for (int row = 0; row < 7; row++) {
                if (g[col] & (1 << row)) {
                    int px = cx + col;
                    int py = sy + row;
                    if (px >= 0 && px < rgnW * 8 && py >= 0 && py < rgnH)
                        partBuf[py * rgnW + px / 8] &= ~(0x80 >> (px % 8));
                }
            }
        }
    }

    epdPartialDisplay(partBuf, TIME_RGN_X0, TIME_RGN_Y0, TIME_RGN_X1, TIME_RGN_Y1);
}

// ── Smart display with hybrid refresh strategy ──────────────
// Uses fast refresh (0xC7 + temperature LUT, ~1.5s, minimal flash) most of the time.
// Performs a full refresh (0xF7, clears ghosting) every FULL_REFRESH_INTERVAL cycles.

static int refreshCount = 0;

void smartDisplay(const uint8_t *image) {
    if (refreshCount % FULL_REFRESH_INTERVAL == 0) {
        Serial.printf("smartDisplay: full refresh (cycle %d)\n", refreshCount);
        epdDisplay(image);
    } else {
        Serial.printf("smartDisplay: fast refresh (cycle %d)\n", refreshCount);
        epdDisplayFast(image);
    }
    refreshCount++;
}
