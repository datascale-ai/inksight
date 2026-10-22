#pragma once

#include <cstddef>
#include <cstdint>

constexpr int LOW = 0;
constexpr int HIGH = 1;
constexpr int INPUT = 0;
constexpr int OUTPUT = 1;
constexpr int INPUT_PULLUP = 2;

void pinMode(int pin, int mode);
void digitalWrite(int pin, int value);
int digitalRead(int pin);
void delay(unsigned long ms);
unsigned long millis();

struct FakeSerial {
    void printf(const char *format, ...);
};
extern FakeSerial Serial;
