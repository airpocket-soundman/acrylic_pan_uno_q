#pragma once

#include <Arduino.h>

class Kx134 {
 public:
  explicit Kx134(uint8_t chipSelectPin);

  bool begin();
  int16_t readZ();
  uint8_t whoAmI();

 private:
  uint8_t transfer(uint8_t value);
  uint8_t readRegister(uint8_t address);
  void readRegisters(uint8_t address, uint8_t* destination, size_t length);
  void writeRegister(uint8_t address, uint8_t value);

  uint8_t chipSelectPin_;
};
