#ifndef INKSIGHT_DISPLAY_H
#define INKSIGHT_DISPLAY_H

#include <Arduino.h>

// Look up glyph data for a character (5x7 pixel font)
const uint8_t* getGlyph(char c);

// Draw scaled text into imgBuf at (x, y)
void drawText(const char *msg, int x, int y, int scale);

// Show WiFi setup screen with AP name
void showSetupScreen(const char *apName);

// Show centered error message on screen
void showError(const char *msg);

// Show diagnostic screen with up to 4 lines
void showDiagnostic(const char *line1, const char *line2, const char *line3, const char *line4);

int currentPeriodIndex();

void updateTimeDisplay();

// Smart display: uses no-flash partial refresh normally, full refresh every N cycles
void smartDisplay(const uint8_t *image);

// Show mode name preview screen (displayed briefly on double-click before loading)
void showModePreview(const char *modeName);

// ── LED feedback patterns ──────────────────────────────────────

// Drive the LED with named feedback patterns.
// Patterns: "ack", "connecting", "downloading", "success", "fail", "favorite", "portal", "off"
void ledFeedback(const char *pattern);

#endif // INKSIGHT_DISPLAY_H
