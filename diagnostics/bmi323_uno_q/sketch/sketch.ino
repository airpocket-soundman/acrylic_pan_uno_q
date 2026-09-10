#include <Arduino_RouterBridge.h>
#include <SPI.h>

constexpr uint8_t CS_PIN = 10;
constexpr uint8_t REG_CHIP_ID = 0x00;
constexpr uint8_t EXPECTED_CHIP_ID = 0x43;
uint32_t probeCycle = 0;

uint8_t readChipId(uint8_t mode, uint8_t attempt) {
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, mode));
  digitalWrite(CS_PIN, LOW);
  const uint8_t b0 = SPI.transfer(REG_CHIP_ID | 0x80U);
  const uint8_t b1 = SPI.transfer(0x00);  // BMI323 SPI dummy byte.
  const uint8_t low = SPI.transfer(0x00);
  const uint8_t high = SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
  Bridge.notify("on_probe", static_cast<int>(mode), static_cast<int>(attempt),
                static_cast<int>(b0), static_cast<int>(b1),
                static_cast<int>(low), static_cast<int>(high));
  return low;
}

void setup() {
  Bridge.begin();
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);
  SPI.begin();
  delay(100);
}

void loop() {
  const uint8_t modes[] = {SPI_MODE0, SPI_MODE3};
  uint8_t chipId = 0;
  uint8_t selectedMode = SPI_MODE0;
  for (uint8_t mode : modes) {
    // Bosch recommends one dummy register read after selecting SPI.
    readChipId(mode, 1);
    delay(2);
    chipId = readChipId(mode, 2);
    if (chipId == EXPECTED_CHIP_ID) {
      selectedMode = mode;
      break;
    }
  }
  Bridge.notify("on_result", chipId == EXPECTED_CHIP_ID,
                static_cast<int>(chipId), static_cast<int>(selectedMode));
  ++probeCycle;
  delay(probeCycle < 5 ? 1000 : 5000);
}
