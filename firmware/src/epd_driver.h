#ifndef INKSIGHT_EPD_DRIVER_H
#define INKSIGHT_EPD_DRIVER_H

#include <Arduino.h>

// Initialize GPIO pins for EPD and config button
void gpioInit();

// Initialize EPD controller (Waveshare 4.2" V2, SSD1683) - full refresh mode
void epdInit();

// Initialize EPD controller in fast refresh mode (1.5s, reduced flashing)
void epdInitFast();

// Full-screen display with full refresh (clears ghosting, has black-white flash)
void epdDisplay(const uint8_t *image);

// Full-screen display with fast refresh (reduced flashing, ~1.5s)
void epdDisplayFast(const uint8_t *image);

// Partial display refresh for a rectangular region
void epdPartialDisplay(uint8_t *data, int xStart, int yStart, int xEnd, int yEnd);

// Put EPD into deep sleep mode
void epdSleep();

#endif // INKSIGHT_EPD_DRIVER_H
