#include <Arduino_RouterBridge.h>
#include <SPI.h>

constexpr uint8_t CS_PIN = 10;
constexpr uint8_t INT1_PIN = 8;
constexpr uint8_t REG_DEVICE_CONFIG = 0x11;
constexpr uint8_t REG_ACCEL_DATA_X1 = 0x1F;
constexpr uint8_t REG_PWR_MGMT0 = 0x4E;
constexpr uint8_t REG_ACCEL_CONFIG0 = 0x50;
constexpr uint8_t REG_WHO_AM_I = 0x75;
constexpr uint8_t EXPECTED_WHO_AM_I = 0x47;

uint8_t spiMode = SPI_MODE0;
bool sensorReady = false;
uint32_t sampleNumber = 0;

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

int16_t joinSigned(uint8_t high, uint8_t low) {
  return static_cast<int16_t>((static_cast<uint16_t>(high) << 8) | low);
}

void setup() {
  Bridge.begin();
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);
  pinMode(INT1_PIN, INPUT);
  SPI.begin();
  delay(100);

  const uint8_t modes[] = {SPI_MODE0, SPI_MODE3};
  uint8_t who = 0;
  for (uint8_t candidate : modes) {
    spiMode = candidate;
    who = readRegister(REG_WHO_AM_I);
    Bridge.notify("on_probe_attempt", static_cast<int>(candidate), static_cast<int>(who));
    if (who == EXPECTED_WHO_AM_I) break;
  }
  sensorReady = who == EXPECTED_WHO_AM_I;
  Bridge.notify("on_probe_result", sensorReady, static_cast<int>(who), static_cast<int>(spiMode));
  if (!sensorReady) return;

  writeRegister(REG_DEVICE_CONFIG, 0x01);  // Soft reset.
  delay(10);
  writeRegister(REG_ACCEL_CONFIG0, 0x01);  // +/-16 g, 32 kHz ODR.
  writeRegister(REG_PWR_MGMT0, 0x0F);      // Accel and gyro low-noise mode.
  delay(50);
}

void loop() {
  if (!sensorReady) {
    delay(1000);
    return;
  }
  uint8_t raw[6];
  readRegisters(REG_ACCEL_DATA_X1, raw, sizeof(raw));
  Bridge.notify("on_sample", static_cast<int>(joinSigned(raw[0], raw[1])),
                static_cast<int>(joinSigned(raw[2], raw[3])),
                static_cast<int>(joinSigned(raw[4], raw[5])),
                static_cast<int>(digitalRead(INT1_PIN)), static_cast<int>(++sampleNumber));
  delay(200);
}
