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

// Dedicated status screen for local AI chat flow
void showAiChatStatus(const char *state, const char *detail);

// Single-turn: small partial-refresh overlay in footer.
// footerCenter=true puts icon centered; false puts it bottom-right.
void showVoiceIndicator(bool footerCenter = false);
void hideVoiceIndicator();

// Multi-turn: full-screen with large centered robot icon (uses fast full refresh).
void showVoiceChatScreen();

int currentPeriodIndex();

void updateTimeDisplay();

// Smart display: uses no-flash partial refresh normally, full refresh every N cycles
void smartDisplay(const uint8_t *image);

// Show mode name preview screen (displayed briefly on double-click before loading)
void showModePreview(const char *modeName);

#endif // INKSIGHT_DISPLAY_H
