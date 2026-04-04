#ifndef INKSIGHT_EPD_DRIVER_H
#define INKSIGHT_EPD_DRIVER_H

#include <Arduino.h>

// Initialize GPIO pins and SPI for EPD
void gpioInit();

// Initialize EPD controller (full refresh mode)
void epdInit();

// Initialize EPD controller in fast refresh mode
void epdInitFast();

// Full-screen display with full refresh (clears ghosting, has black-white flash)
void epdDisplay(const uint8_t *image);

// Full-screen display with pre-packed 2bpp data (4-color panels)
void epdDisplay2bpp(const uint8_t *image2bpp);

// Full-screen display with fast refresh (reduced flashing)
void epdDisplayFast(const uint8_t *image);

// Partial display refresh for a rectangular region
void epdPartialDisplay(uint8_t *data, int xStart, int yStart, int xEnd, int yEnd);

// Put EPD into deep sleep mode
void epdSleep();

#endif // INKSIGHT_EPD_DRIVER_H
// ==================== 威锋4in2b函数声明 ====================

/**
 * @brief 威锋4in2b初始化
 * WFT0420CZ15LW 专用初始化函数
 */
void epd_wft_4in2b_init();

/**
 * @brief 威锋4in2b清屏
 * @param color 颜色: 0=黑, 1=白, 2=红
 */
void epd_wft_4in2b_clear(uint8_t color);

/**
 * @brief 威锋4in2b显示图像
 * @param image 图像数据指针
 * @param len 图像数据长度
 */
void epd_wft_4in2b_display(const uint8_t* image, size_t len);

/**
 * @brief 威锋4in2b进入睡眠模式
 */
void epd_wft_4in2b_sleep();
