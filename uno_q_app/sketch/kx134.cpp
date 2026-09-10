#include "kx134.h"

#include <stm32u585xx.h>

namespace {
constexpr uint8_t REG_WHO_AM_I = 0x13;
constexpr uint8_t REG_CNTL1 = 0x1B;
constexpr uint8_t REG_CNTL2 = 0x1C;
constexpr uint8_t REG_ODCNTL = 0x21;
constexpr uint8_t REG_INC1 = 0x22;
constexpr uint8_t REG_INC4 = 0x25;
constexpr uint8_t REG_INC5 = 0x26;
constexpr uint8_t REG_XOUT_L = 0x08;
constexpr uint8_t WHO_AM_I_VALUE = 0x46;
constexpr uint8_t SOFT_RESET = 0x80;
constexpr uint8_t ODR_25600_HZ = 0x0F;
// The original Acrylic Pan data/model contract is KX134 +/-32 g (1024 LSB/g).
constexpr uint8_t CNTL1_OPERATING_32G = 0xF0;  // PC1 | RES | DRDYE | GSEL=32 g

// UNO Q Arduino header mapping: D10=PB9, D11=PB15, D12=PB14, D13=PB13.
constexpr uint32_t CS_MASK = 1UL << 9;
constexpr uint32_t MOSI_MASK = 1UL << 15;
constexpr uint32_t MISO_MASK = 1UL << 14;
constexpr uint32_t SCK_MASK = 1UL << 13;

inline void edgeDelay() {
  __NOP(); __NOP(); __NOP(); __NOP();
  __NOP(); __NOP(); __NOP(); __NOP();
}
}

Kx134::Kx134(uint8_t chipSelectPin) : chipSelectPin_(chipSelectPin) {}

bool Kx134::begin() {
  pinMode(chipSelectPin_, OUTPUT);
  pinMode(11, OUTPUT);
  pinMode(12, INPUT);
  pinMode(13, OUTPUT);
  digitalWrite(chipSelectPin_, HIGH);
  digitalWrite(13, LOW);
  delay(50);

  if (whoAmI() != WHO_AM_I_VALUE) return false;

  writeRegister(REG_CNTL1, 0x00);
  writeRegister(REG_CNTL2, SOFT_RESET);
  delay(10);
  if (whoAmI() != WHO_AM_I_VALUE) return false;

  writeRegister(REG_CNTL1, 0x00);
  writeRegister(REG_ODCNTL, ODR_25600_HZ);
  writeRegister(REG_INC1, 0x78);  // INT1 enabled, active-high pulse.
  writeRegister(REG_INC4, 0x10);  // Route data-ready to INT1.
  writeRegister(REG_INC5, 0x01);  // Auto-clear pulse configuration.
  writeRegister(REG_CNTL1, CNTL1_OPERATING_32G);
  delay(2);
  return true;
}

uint8_t Kx134::transfer(uint8_t value) {
  uint8_t received = 0;
  for (int bit = 7; bit >= 0; --bit) {
    GPIOB->BSRR = ((value >> bit) & 1U) ? MOSI_MASK : (MOSI_MASK << 16);
    edgeDelay();
    GPIOB->BSRR = SCK_MASK;
    edgeDelay();
    received |= static_cast<uint8_t>((GPIOB->IDR & MISO_MASK) != 0) << bit;
    GPIOB->BSRR = SCK_MASK << 16;
  }
  return received;
}

uint8_t Kx134::readRegister(uint8_t address) {
  uint8_t value = 0;
  readRegisters(address, &value, 1);
  return value;
}

void Kx134::readRegisters(uint8_t address, uint8_t* destination, size_t length) {
  GPIOB->BSRR = CS_MASK << 16;
  edgeDelay();
  transfer(address | 0x80U);
  for (size_t i = 0; i < length; ++i) destination[i] = transfer(0x00);
  edgeDelay();
  GPIOB->BSRR = CS_MASK;
}

void Kx134::writeRegister(uint8_t address, uint8_t value) {
  GPIOB->BSRR = CS_MASK << 16;
  edgeDelay();
  transfer(address & 0x7FU);
  transfer(value);
  edgeDelay();
  GPIOB->BSRR = CS_MASK;
}

int16_t Kx134::readZ() {
  // Read the complete XYZ output group. KX134 keeps DRDY asserted until the
  // acceleration output has been consumed; reading Z alone does not reliably
  // release INT1 on this board.
  uint8_t bytes[6];
  readRegisters(REG_XOUT_L, bytes, sizeof(bytes));
  return static_cast<int16_t>((static_cast<uint16_t>(bytes[5]) << 8U) | bytes[4]);
}

uint8_t Kx134::whoAmI() { return readRegister(REG_WHO_AM_I); }
