#include <Arduino_RouterBridge.h>
#include <SPI.h>
#include <stm32u585xx.h>

constexpr uint8_t CS_PIN = 10;
constexpr uint8_t MOSI_PIN = 11;
constexpr uint8_t MISO_PIN = 12;
constexpr uint8_t SCK_PIN = 13;
constexpr uint8_t REG_XOUT_L = 0x08;
constexpr uint8_t REG_WHO_AM_I = 0x13;
constexpr uint8_t REG_CNTL1 = 0x1B;
constexpr uint8_t REG_CNTL2 = 0x1C;
constexpr uint8_t REG_ODCNTL = 0x21;
constexpr uint8_t REG_INC1 = 0x22;
constexpr uint8_t REG_INC4 = 0x25;
constexpr uint8_t REG_INC5 = 0x26;
constexpr uint8_t EXPECTED_WHO_AM_I = 0x46;
constexpr uint8_t INT1_PIN = 2;

uint8_t spiMode = SPI_MODE0;
bool sensorReady = false;
uint32_t sampleNumber = 0;
uint32_t nextProbeAt = 0;
volatile uint32_t dataReadyIrqCount = 0;
bool fastGpioTested = false;

void onDataReady() { ++dataReadyIrqCount; }

uint8_t bitBangTransfer(uint8_t value, uint8_t mode) {
  const bool cpol = (mode & 0x02U) != 0;
  const bool cpha = (mode & 0x01U) != 0;
  uint8_t received = 0;

  for (int bit = 7; bit >= 0; --bit) {
    if (!cpha) digitalWrite(MOSI_PIN, (value >> bit) & 1U);
    digitalWrite(SCK_PIN, !cpol);
    if (cpha) digitalWrite(MOSI_PIN, (value >> bit) & 1U);
    delayMicroseconds(5);
    if (!cpha) received |= static_cast<uint8_t>(digitalRead(MISO_PIN)) << bit;
    digitalWrite(SCK_PIN, cpol);
    delayMicroseconds(5);
    if (cpha) received |= static_cast<uint8_t>(digitalRead(MISO_PIN)) << bit;
  }
  return received;
}

uint8_t readRegisterBitBang(uint8_t address, uint8_t mode) {
  const bool cpol = (mode & 0x02U) != 0;
  digitalWrite(SCK_PIN, cpol);
  digitalWrite(CS_PIN, LOW);
  delayMicroseconds(5);
  bitBangTransfer(address | 0x80U, mode);
  const uint8_t value = bitBangTransfer(0x00, mode);
  delayMicroseconds(5);
  digitalWrite(CS_PIN, HIGH);
  delayMicroseconds(5);
  return value;
}

void readRegistersBitBang(uint8_t address, uint8_t* values, size_t count,
                          uint8_t mode = 0) {
  const bool cpol = (mode & 0x02U) != 0;
  digitalWrite(SCK_PIN, cpol);
  digitalWrite(CS_PIN, LOW);
  delayMicroseconds(5);
  bitBangTransfer(address | 0x80U, mode);
  for (size_t i = 0; i < count; ++i) values[i] = bitBangTransfer(0x00, mode);
  delayMicroseconds(5);
  digitalWrite(CS_PIN, HIGH);
  delayMicroseconds(5);
}

void writeRegisterBitBang(uint8_t address, uint8_t value, uint8_t mode = 0) {
  const bool cpol = (mode & 0x02U) != 0;
  digitalWrite(SCK_PIN, cpol);
  digitalWrite(CS_PIN, LOW);
  delayMicroseconds(5);
  bitBangTransfer(address & 0x7FU, mode);
  bitBangTransfer(value, mode);
  delayMicroseconds(5);
  digitalWrite(CS_PIN, HIGH);
  delayMicroseconds(5);
}

void configureSensorBitBang() {
  writeRegisterBitBang(REG_CNTL1, 0x00);  // Standby before configuration.
  writeRegisterBitBang(REG_CNTL2, 0x80);  // Software reset.
  delay(10);
  writeRegisterBitBang(REG_CNTL1, 0x00);
  writeRegisterBitBang(REG_ODCNTL, 0x0F); // 25.6 kHz ODR.
  writeRegisterBitBang(REG_INC1, 0x78);   // INT1 enabled, active-high pulse, 1 ODR period.
  writeRegisterBitBang(REG_INC4, 0x10);   // Route DRDY to INT1.
  writeRegisterBitBang(REG_INC5, 0x01);   // Auto-clear INT1 pulse.
  writeRegisterBitBang(REG_CNTL1, 0xF8);  // HP, DRDY enabled, +/-64 g, operating.
  delay(20);
}

bool probeBitBang() {
  pinMode(CS_PIN, OUTPUT);
  pinMode(MOSI_PIN, OUTPUT);
  pinMode(MISO_PIN, INPUT);
  pinMode(SCK_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);

  bool ready = false;
  for (uint8_t mode = 0; mode < 4; ++mode) {
    const uint8_t who = readRegisterBitBang(REG_WHO_AM_I, mode);
    Bridge.notify("on_bitbang_probe", static_cast<int>(mode), static_cast<int>(who));
    ready |= who == EXPECTED_WHO_AM_I;
  }
  return ready;
}

uint8_t probeBufferedHardware() {
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);
  SPI.begin();
  uint8_t frame[2] = {static_cast<uint8_t>(REG_WHO_AM_I | 0x80U), 0x00};
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(frame, sizeof(frame));
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
  return frame[1];
}

uint16_t probeTransfer16Hardware() {
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);
  SPI.begin();
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CS_PIN, LOW);
  const uint16_t result = SPI.transfer16(0x9300U);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
  return result;
}

inline void fastSpiDelay() {
  __NOP(); __NOP(); __NOP(); __NOP();
  __NOP(); __NOP(); __NOP(); __NOP();
}

uint8_t fastGpioTransfer(uint8_t value) {
  constexpr uint32_t MOSI_MASK = 1UL << 15;
  constexpr uint32_t MISO_MASK = 1UL << 14;
  constexpr uint32_t SCK_MASK = 1UL << 13;
  uint8_t received = 0;
  for (int bit = 7; bit >= 0; --bit) {
    GPIOB->BSRR = ((value >> bit) & 1U) ? MOSI_MASK : (MOSI_MASK << 16);
    fastSpiDelay();
    GPIOB->BSRR = SCK_MASK;
    fastSpiDelay();
    received |= static_cast<uint8_t>((GPIOB->IDR & MISO_MASK) != 0) << bit;
    GPIOB->BSRR = SCK_MASK << 16;
  }
  return received;
}

uint8_t fastGpioReadRegister(uint8_t address) {
  constexpr uint32_t CS_MASK = 1UL << 9;
  GPIOB->BSRR = CS_MASK << 16;
  fastSpiDelay();
  fastGpioTransfer(address | 0x80U);
  const uint8_t result = fastGpioTransfer(0x00);
  fastSpiDelay();
  GPIOB->BSRR = CS_MASK;
  return result;
}

void readRegistersBufferedHardware(uint8_t address, uint8_t* values,
                                   size_t count) {
  uint8_t frame[8] = {};
  frame[0] = address | 0x80U;
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(frame, count + 1);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
  for (size_t i = 0; i < count; ++i) values[i] = frame[i + 1];
}

uint8_t readRegister(uint8_t address) {
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, spiMode));
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(address | 0x80U);
  const uint8_t value = SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
  return value;
}

void readRegisters(uint8_t address, uint8_t* values, size_t count) {
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, spiMode));
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(address | 0x80U);
  for (size_t i = 0; i < count; ++i) values[i] = SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
}

void writeRegister(uint8_t address, uint8_t value) {
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, spiMode));
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(address & 0x7FU);
  SPI.transfer(value);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
}

int16_t joinSignedLittleEndian(uint8_t low, uint8_t high) {
  return static_cast<int16_t>((static_cast<uint16_t>(high) << 8) | low);
}

bool probeSensor() {
  const uint8_t modes[] = {SPI_MODE0, SPI_MODE3};
  uint8_t who = 0;
  for (uint8_t candidate : modes) {
    spiMode = candidate;
    who = readRegister(REG_WHO_AM_I);
    Bridge.notify("on_probe_attempt", static_cast<int>(candidate), static_cast<int>(who));
    if (who == EXPECTED_WHO_AM_I) break;
  }
  const bool ready = who == EXPECTED_WHO_AM_I;
  sensorReady = ready;
  Bridge.notify("on_probe_result", sensorReady, static_cast<int>(who), static_cast<int>(spiMode));
  return ready;
}

void configureSensor() {
  writeRegister(REG_CNTL1, 0x00);  // Standby before configuration.
  writeRegister(REG_CNTL2, 0x80);  // Software reset.
  delay(10);
  writeRegister(REG_CNTL1, 0x00);
  writeRegister(REG_ODCNTL, 0x0F); // 25.6 kHz ODR.
  writeRegister(REG_CNTL1, 0xD8);  // High performance, +/-16 g, operating.
  delay(20);
}

void setup() {
  Bridge.begin();
  delay(1000);  // Allow the Linux logger to subscribe before the first probe.
  sensorReady = probeBitBang();
  if (sensorReady) {
    pinMode(INT1_PIN, INPUT);
    attachInterrupt(digitalPinToInterrupt(INT1_PIN), onDataReady, RISING);
    configureSensorBitBang();
  }
  Bridge.notify("on_bitbang_result", sensorReady,
                static_cast<int>(digitalRead(MISO_PIN)));
  nextProbeAt = millis() + 1000;
}

void loop() {
  if (!sensorReady) {
    if (static_cast<int32_t>(millis() - nextProbeAt) >= 0) {
      sensorReady = probeBitBang();
      if (sensorReady) configureSensorBitBang();
      Bridge.notify("on_bitbang_result", sensorReady,
                    static_cast<int>(digitalRead(MISO_PIN)));
      nextProbeAt = millis() + 1000;
    }
    delay(20);
    return;
  }
  uint8_t raw[6];
  if (!fastGpioTested && sampleNumber >= 20) {
    fastGpioTested = true;
    const uint8_t who = fastGpioReadRegister(REG_WHO_AM_I);
    const uint32_t started = micros();
    for (size_t i = 0; i < 1000; ++i) fastGpioReadRegister(REG_WHO_AM_I);
    const uint32_t elapsed = micros() - started;
    Bridge.notify("on_fast_gpio_probe", static_cast<int>(who),
                  static_cast<int>(elapsed));
  }
  if (static_cast<int32_t>(millis() - nextProbeAt) >= 0) {
    noInterrupts();
    const uint32_t irqSnapshot = dataReadyIrqCount;
    dataReadyIrqCount = 0;
    interrupts();
    Bridge.notify("on_irq_rate", static_cast<int>(irqSnapshot));
    nextProbeAt = millis() + 1000;
  }
  readRegistersBitBang(REG_XOUT_L, raw, sizeof(raw));
  Bridge.notify("on_sample",
                static_cast<int>(joinSignedLittleEndian(raw[0], raw[1])),
                static_cast<int>(joinSignedLittleEndian(raw[2], raw[3])),
                static_cast<int>(joinSignedLittleEndian(raw[4], raw[5])),
                static_cast<int>(++sampleNumber));
  delay(200);
}
