#include "kx134.h"

namespace {
constexpr uint8_t REG_WHO_AM_I = 0x13;
constexpr uint8_t REG_CNTL1 = 0x1B;
constexpr uint8_t REG_CNTL2 = 0x1C;
constexpr uint8_t REG_ODCNTL = 0x21;
constexpr uint8_t REG_ZOUT_L = 0x0C;
constexpr uint8_t WHO_AM_I_VALUE = 0x46;
constexpr uint8_t SOFT_RESET = 0x80;
constexpr uint8_t ODR_25600_HZ = 0x0F;
constexpr uint8_t CNTL1_OPERATING_64G = 0xD8;  // PC1 | RES | GSEL=64 g
}

Kx134::Kx134(uint8_t chipSelectPin) : chipSelectPin_(chipSelectPin) {}

bool Kx134::begin() {
  pinMode(chipSelectPin_, OUTPUT);
  digitalWrite(chipSelectPin_, HIGH);
  SPI.begin();
  delay(50);

  if (whoAmI() != WHO_AM_I_VALUE) return false;

  writeRegister(REG_CNTL1, 0x00);
  writeRegister(REG_CNTL2, SOFT_RESET);
  delay(10);
  if (whoAmI() != WHO_AM_I_VALUE) return false;

  writeRegister(REG_CNTL1, 0x00);
  writeRegister(REG_ODCNTL, ODR_25600_HZ);
  writeRegister(REG_CNTL1, CNTL1_OPERATING_64G);
  delay(2);
  return true;
}

uint8_t Kx134::readRegister(uint8_t address) {
  uint8_t value = 0;
  readRegisters(address, &value, 1);
  return value;
}

void Kx134::readRegisters(uint8_t address, uint8_t* destination, size_t length) {
  SPI.beginTransaction(settings_);
  digitalWrite(chipSelectPin_, LOW);
  SPI.transfer(address | 0x80U);
  for (size_t i = 0; i < length; ++i) destination[i] = SPI.transfer(0x00);
  digitalWrite(chipSelectPin_, HIGH);
  SPI.endTransaction();
}

void Kx134::writeRegister(uint8_t address, uint8_t value) {
  SPI.beginTransaction(settings_);
  digitalWrite(chipSelectPin_, LOW);
  SPI.transfer(address & 0x7FU);
  SPI.transfer(value);
  digitalWrite(chipSelectPin_, HIGH);
  SPI.endTransaction();
}

int16_t Kx134::readZ() {
  uint8_t bytes[2];
  readRegisters(REG_ZOUT_L, bytes, sizeof(bytes));
  return static_cast<int16_t>((static_cast<uint16_t>(bytes[1]) << 8U) | bytes[0]);
}

uint8_t Kx134::whoAmI() { return readRegister(REG_WHO_AM_I); }
