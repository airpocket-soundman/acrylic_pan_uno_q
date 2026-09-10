from arduino.app_utils import App, Bridge, Logger


logger = Logger("bmi323-diag")


def on_probe(mode: int, attempt: int, b0: int, b1: int, low: int, high: int) -> None:
    word = low | (high << 8)
    logger.info(
        f"PROBE mode={mode} attempt={attempt} bytes="
        f"[{b0:02X} {b1:02X} {low:02X} {high:02X}] "
        f"CHIP_ID_WORD=0x{word:04X}"
    )


def on_result(ready: bool, chip_id: int, mode: int) -> None:
    level = "PASS" if ready else "FAIL"
    logger.info(f"{level} ready={ready} BMI323_CHIP_ID=0x{chip_id:02X} spi_mode={mode}")


Bridge.provide("on_probe", on_probe)
Bridge.provide("on_result", on_result)
logger.info("Waiting for BMI323 diagnostic sketch; expected CHIP_ID=0x43")
App.run()
