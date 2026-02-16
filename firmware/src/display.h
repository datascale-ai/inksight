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

// Update time display via partial refresh (HH:MM:SS)
void updateTimeDisplay();

// Smart display: uses no-flash partial refresh normally, full refresh every N cycles
void smartDisplay(const uint8_t *image);

#endif // INKSIGHT_DISPLAY_H
