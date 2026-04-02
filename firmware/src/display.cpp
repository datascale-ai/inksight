#include "display.h"
#include "config.h"
#include "epd_driver.h"

// ── Unified 5x7 pixel font ─────────────────────────────────
// Each glyph is 5 columns x 7 rows, stored column-major.
// Bit 0 = top row, bit 6 = bottom row.

const uint8_t* getGlyph(char c) {
    // Uppercase letters
    static const uint8_t g_A[] = {0x7E,0x11,0x11,0x11,0x7E};
    static const uint8_t g_B[] = {0x7F,0x49,0x49,0x49,0x36};
    static const uint8_t g_C[] = {0x3E,0x41,0x41,0x41,0x22};
    static const uint8_t g_D[] = {0x7F,0x41,0x41,0x22,0x1C};
    static const uint8_t g_E[] = {0x7F,0x49,0x49,0x49,0x41};
    static const uint8_t g_F[] = {0x7F,0x09,0x09,0x09,0x01};
    static const uint8_t g_G[] = {0x3E,0x41,0x49,0x49,0x3A};
    static const uint8_t g_H[] = {0x7F,0x08,0x08,0x08,0x7F};
    static const uint8_t g_I[] = {0x00,0x41,0x7F,0x41,0x00};
    static const uint8_t g_K[] = {0x7F,0x08,0x14,0x22,0x41};
    static const uint8_t g_L[] = {0x7F,0x40,0x40,0x40,0x40};
    static const uint8_t g_M[] = {0x7F,0x02,0x0C,0x02,0x7F};
    static const uint8_t g_N[] = {0x7F,0x04,0x08,0x10,0x7F};
    static const uint8_t g_O[] = {0x3E,0x41,0x41,0x41,0x3E};
    static const uint8_t g_P[] = {0x7F,0x09,0x09,0x09,0x06};
    static const uint8_t g_R[] = {0x7F,0x09,0x19,0x29,0x46};
    static const uint8_t g_S[] = {0x26,0x49,0x49,0x49,0x32};
    static const uint8_t g_T[] = {0x01,0x01,0x7F,0x01,0x01};
    static const uint8_t g_U[] = {0x3F,0x40,0x40,0x40,0x3F};
    static const uint8_t g_V[] = {0x1F,0x20,0x40,0x20,0x1F};
    static const uint8_t g_W[] = {0x3F,0x40,0x38,0x40,0x3F};
    static const uint8_t g_X[] = {0x63,0x14,0x08,0x14,0x63};
    static const uint8_t g_Y[] = {0x07,0x08,0x70,0x08,0x07};
    static const uint8_t g_Z[] = {0x61,0x51,0x49,0x45,0x43};

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
    static const uint8_t g_dot[]   = {0x00,0x60,0x60,0x00,0x00};
    static const uint8_t g_slash[] = {0x20,0x10,0x08,0x04,0x02};
    static const uint8_t g_exclam[]= {0x00,0x00,0x5F,0x00,0x00};
    static const uint8_t g_space[] = {0x00,0x00,0x00,0x00,0x00};

    switch (c) {
        // Uppercase
        case 'A': return g_A; case 'B': return g_B; case 'C': return g_C;
        case 'D': return g_D; case 'E': return g_E; case 'F': return g_F;
        case 'G': return g_G; case 'H': return g_H; case 'I': return g_I;
        case 'K': return g_K; case 'L': return g_L; case 'M': return g_M;
        case 'N': return g_N; case 'O': return g_O; case 'P': return g_P;
        case 'R': return g_R; case 'S': return g_S; case 'T': return g_T;
        case 'U': return g_U; case 'V': return g_V; case 'W': return g_W;
        case 'X': return g_X; case 'Y': return g_Y; case 'Z': return g_Z;
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
        case '.': return g_dot;   case '/': return g_slash;
        case '!': return g_exclam;
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

static void fillRect(int x, int y, int w, int h) {
    int rowBytes = W / 8;
    for (int py = y; py < y + h; py++) {
        if (py < 0 || py >= H) continue;
        for (int px = x; px < x + w; px++) {
            if (px < 0 || px >= W) continue;
            imgBuf[py * rowBytes + px / 8] &= ~(0x80 >> (px % 8));
        }
    }
}

// ── Show WiFi setup screen ──────────────────────────────────

void showSetupScreen(const char *apName) {
    memset(imgBuf, 0xFF, IMG_BUF_LEN);

    fillRect(0, 0, W, H * 12 / 100);
    fillRect(W * 8 / 100, H * 28 / 100, W * 84 / 100, H * 2 / 100);
    fillRect(W * 8 / 100, H * 72 / 100, W * 84 / 100, H * 2 / 100);

    const char *title = "SETUP WIFI";
    int titleScale = (H < 200) ? 2 : 4;
    int titleX = (W - textWidth(strlen(title), titleScale)) / 2;
    int titleY = H * 15 / 100;
    drawText(title, titleX, titleY, titleScale);

    const char *line1 = "CONNECT TO";
    int bodyScale = (H < 200) ? 1 : 2;
    int line1X = (W - textWidth(strlen(line1), bodyScale)) / 2;
    int line1Y = H * 36 / 100;
    drawText(line1, line1X, line1Y, bodyScale);

    int apScale = (H < 200) ? 2 : 3;
    int apX = (W - textWidth(strlen(apName), apScale)) / 2;
    int apY = H * 46 / 100;
    drawText(apName, apX, apY, apScale);

    const char *line3 = "OPEN BROWSER";
    int line3X = (W - textWidth(strlen(line3), bodyScale)) / 2;
    int line3Y = H * 62 / 100;
    drawText(line3, line3X, line3Y, bodyScale);

    epdDisplay(imgBuf);
    Serial.printf("Setup screen shown: %s\n", apName);
}

// ── Show diagnostic screen ──────────────────────────────────

void showDiagnostic(const char *line1, const char *line2, const char *line3, const char *line4) {
    memset(imgBuf, 0xFF, IMG_BUF_LEN);

    int titleScale = (H < 200) ? 2 : 3;
    int bodyScale  = (H < 200) ? 1 : 2;

    int y = H * 10 / 100;
    int lh = 7 * titleScale + titleScale * 2;
    int blh = 7 * bodyScale + bodyScale * 2;

    if (line1 && line1[0]) {
        int x = (W - textWidth(strlen(line1), titleScale)) / 2;
        if (x < 4) x = 4;
        drawText(line1, x, y, titleScale);
        y += lh + 4;
    }

    int infoX = W * 5 / 100;
    if (line2 && line2[0]) {
        drawText(line2, infoX, y, bodyScale);
        y += blh;
    }
    if (line3 && line3[0]) {
        drawText(line3, infoX, y, bodyScale);
        y += blh;
    }
    if (line4 && line4[0]) {
        drawText(line4, infoX, y, bodyScale);
    }

    epdDisplay(imgBuf);
}

// ── Show centered error message ─────────────────────────────

void showError(const char *msg) {
    memset(imgBuf, 0xFF, IMG_BUF_LEN);

    int scale = (H < 200) ? 1 : 2;
    int len = strlen(msg);
    int startX = (W - textWidth(len, scale)) / 2;
    int startY = H / 2 - (7 * scale) / 2;

    drawText(msg, startX, startY, scale);

    epdDisplay(imgBuf);
    Serial.printf("Error shown: %s\n", msg);
}

// ── Update time display (partial refresh) ───────────────────

// Time state (shared with network module)
extern int curHour, curMin, curSec;

static const uint16_t GLYPH_SHEN[16] = {
    0x33FE, 0x1A02, 0x04D4, 0x4988, 0x2964, 0x3244, 0x1446, 0x17F8,
    0x20D0, 0x20D0, 0x6148, 0x2246, 0x2443, 0x2840, 0x0000, 0x0000,
};

static const uint16_t GLYPH_YE[16] = {
    0x0200, 0x0180, 0x0086, 0x7F78, 0x0CC0, 0x08FC, 0x1104, 0x1948,
    0x3328, 0x5290, 0x1490, 0x1060, 0x1070, 0x119C, 0x1607, 0x0000,
};

static const uint16_t GLYPH_LING[16] = {
    0x4060, 0x2044, 0x1BFA, 0x0842, 0x0FFE, 0x1188, 0x1306, 0x24CA,
    0x21FC, 0x6318, 0x2490, 0x2060, 0x21B8, 0x2E0F, 0x0000, 0x0000,
};

static const uint16_t GLYPH_CHEN[16] = {
    0x1FFC, 0x1008, 0x1FF8, 0x1008, 0x1FF8, 0x3FFE, 0x2000, 0x2FF8,
    0x2004, 0x3FFA, 0x248C, 0x2450, 0x27B8, 0x4C0E, 0x0000, 0x0000,
};

static const uint16_t GLYPH_ZAO[16] = {
    0x1008, 0x1FFC, 0x1008, 0x1FF8, 0x1008, 0x1008, 0x1FF8, 0x1188,
    0x0184, 0x7FFE, 0x0180, 0x0180, 0x0180, 0x0180, 0x0000, 0x0000,
};

static const uint16_t GLYPH_SHANG[16] = {
    0x0180, 0x0100, 0x0100, 0x0100, 0x0100, 0x01FC, 0x0100, 0x0100,
    0x0100, 0x0100, 0x0100, 0x0100, 0x7FFE, 0x0000, 0x0000, 0x0000,
};

static const uint16_t GLYPH_WU[16] = {
    0x0800, 0x0C00, 0x0808, 0x1FFC, 0x1180, 0x2180, 0x4180, 0x0184,
    0x7FFE, 0x0180, 0x0180, 0x0180, 0x0180, 0x0180, 0x0180, 0x0000,
};

static const uint16_t GLYPH_ZHONG[16] = {
    0x0180, 0x0100, 0x2104, 0x3FFE, 0x2104, 0x2104, 0x2104, 0x3FFC,
    0x2104, 0x2100, 0x0100, 0x0100, 0x0100, 0x0100, 0x0000, 0x0000,
};

static const uint16_t GLYPH_XIA[16] = {
    0x0006, 0x7FFE, 0x0100, 0x0100, 0x0180, 0x0160, 0x0130, 0x0108,
    0x0104, 0x0100, 0x0100, 0x0100, 0x0100, 0x0100, 0x0000, 0x0000,
};

static const uint16_t GLYPH_BANG[16] = {
    0x0C40, 0x1EF6, 0x1108, 0x1090, 0x37BE, 0x3443, 0x5824, 0x97FE,
    0x1080, 0x10FC, 0x1088, 0x1108, 0x1208, 0x1478, 0x0000, 0x0000,
};

static const uint16_t GLYPH_WAN[16] = {
    0x00C0, 0x7CF8, 0x4910, 0x4A24, 0x4BFE, 0x7D24, 0x4924, 0x49EC,
    0x4934, 0x4850, 0x7850, 0x4892, 0x0312, 0x0C1F, 0x0000, 0x0000,
};

int currentPeriodIndex() {
    if (curHour >= 23 || curHour < 2) return 0;
    if (curHour < 5) return 1;
    if (curHour < 8) return 2;
    if (curHour < 12) return 3;
    if (curHour < 14) return 4;
    if (curHour < 18) return 5;
    if (curHour < 20) return 6;
    return 7;
}

static void periodGlyphs(int period, const uint16_t **left, const uint16_t **right) {
    switch (period) {
        case 0: *left = GLYPH_SHEN;  *right = GLYPH_YE;    return;
        case 1: *left = GLYPH_LING;  *right = GLYPH_CHEN;  return;
        case 2: *left = GLYPH_ZAO;   *right = GLYPH_CHEN;  return;
        case 3: *left = GLYPH_SHANG; *right = GLYPH_WU;    return;
        case 4: *left = GLYPH_ZHONG; *right = GLYPH_WU;    return;
        case 5: *left = GLYPH_XIA;   *right = GLYPH_WU;    return;
        case 6: *left = GLYPH_BANG;  *right = GLYPH_WAN;   return;
        default: *left = GLYPH_YE;   *right = GLYPH_WAN;   return;
    }
}

static void drawGlyph16(uint8_t *buffer, int width, int height, int x, int y, const uint16_t *glyph) {
    int rowBytes = (width + 7) / 8;
    for (int row = 0; row < 16; row++) {
        int py = y + row;
        if (py < 0 || py >= height) continue;
        uint16_t bits = glyph[row];
        for (int col = 0; col < 16; col++) {
            if ((bits & (1 << (15 - col))) == 0) continue;
            int px = x + col;
            if (px < 0 || px >= width) continue;
            buffer[py * rowBytes + px / 8] &= ~(0x80 >> (px % 8));
        }
    }
}

static void drawPeriodLabel(
    uint8_t *buffer,
    int bufferWidth,
    int bufferHeight,
    int regionX,
    int regionY,
    int regionWidth,
    int regionHeight
) {
    const uint16_t *left = nullptr;
    const uint16_t *right = nullptr;
    periodGlyphs(currentPeriodIndex(), &left, &right);

    const int glyphW = 16;
    const int glyphH = 16;
    const int gap = 2;
    int startX = regionX + (regionWidth - (glyphW * 2 + gap)) / 2;
    int startY = regionY + (regionHeight - glyphH) / 2;
    if (startX < 0) startX = 0;
    if (startY < 0) startY = 0;

    drawGlyph16(buffer, bufferWidth, bufferHeight, startX, startY, left);
    drawGlyph16(buffer, bufferWidth, bufferHeight, startX + glyphW + gap, startY, right);
}

void updateTimeDisplay() {
    int rgnPixelW = TIME_RGN_X1 - TIME_RGN_X0;
    int rgnW = rgnPixelW / 8;
    int rgnH = TIME_RGN_Y1 - TIME_RGN_Y0;
    drawPeriodLabel(imgBuf, W, H, TIME_RGN_X0, TIME_RGN_Y0, rgnPixelW, rgnH);
    uint8_t partBuf[rgnW * rgnH];
    memset(partBuf, 0xFF, sizeof(partBuf));
    drawPeriodLabel(partBuf, rgnPixelW, rgnH, 0, 0, rgnPixelW, rgnH);
    epdPartialDisplay(partBuf, TIME_RGN_X0, TIME_RGN_Y0, TIME_RGN_X1, TIME_RGN_Y1);
}

// ── Mode preview screen (double-click transition) ───────────

void showModePreview(const char *modeName) {
    memset(imgBuf, 0xFF, IMG_BUF_LEN);

    int nameScale = (H < 200) ? 2 : 3;
    int loadScale = (H < 200) ? 1 : 2;

    int len = strlen(modeName);
    int nameX = (W - textWidth(len, nameScale)) / 2;
    int nameY = H / 2 - (H < 200 ? 15 : 30);
    drawText(modeName, nameX, nameY, nameScale);

    const char *loading = "loading...";
    int loadLen = strlen(loading);
    int loadX = (W - textWidth(loadLen, loadScale)) / 2;
    int loadY = H / 2 + (H < 200 ? 10 : 20);
    drawText(loading, loadX, loadY, loadScale);

    epdDisplayFast(imgBuf);
    Serial.printf("Mode preview shown: %s\n", modeName);
}

static int refreshCount = 0;

void smartDisplay(const uint8_t *image) {
#if EPD_BPP >= 2
    if (useColorBuf) {
        Serial.printf("smartDisplay: 2bpp color (cycle %d)\n", refreshCount);
        epdDisplay2bpp(colorBuf);
        useColorBuf = false;
        refreshCount++;
        return;
    }
#endif
    if (refreshCount % FULL_REFRESH_INTERVAL == 0) {
        Serial.printf("smartDisplay: full refresh (cycle %d)\n", refreshCount);
        epdDisplay(image);
    } else {
#if defined(EPD_PANEL_42_GXEPD2_GYE042A87)
        Serial.printf("smartDisplay: full refresh fallback (cycle %d)\n", refreshCount);
#else
        Serial.printf("smartDisplay: fast refresh (cycle %d)\n", refreshCount);
#endif
        epdDisplayFast(image);
    }
    refreshCount++;
}
