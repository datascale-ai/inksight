#ifndef INKSIGHT_OFFLINE_CACHE_H
#define INKSIGHT_OFFLINE_CACHE_H

#include <Arduino.h>

// Initialize LittleFS filesystem
bool cacheInit();

// Save current imgBuf to flash cache
bool cacheSave(const uint8_t *buf, int len);

// Load cached image into imgBuf, returns true if cache exists
bool cacheLoad(uint8_t *buf, int len);

// Check if cache file exists
bool cacheExists();

#endif
