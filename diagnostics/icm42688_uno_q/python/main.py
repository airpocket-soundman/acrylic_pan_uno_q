from arduino.app_utils import App, Bridge, Logger


logger = Logger("icm42688-diag")


def on_probe_attempt(mode: int, who_am_i: int) -> None:
    logger.info(f"PROBE mode={mode} WHO_AM_I=0x{who_am_i:02X}")


def on_probe_result(ready: bool, who_am_i: int, mode: int) -> None:
    level = "PASS" if ready else "FAIL"
    logger.info(f"{level} ready={ready} WHO_AM_I=0x{who_am_i:02X} spi_mode={mode}")


def on_sample(ax: int, ay: int, az: int, int1: int, sample_number: int) -> None:
    logger.info(
        f"SAMPLE n={sample_number} raw=({ax},{ay},{az}) "
        f"g=({ax/2048:.3f},{ay/2048:.3f},{az/2048:.3f}) INT1/D8={int1}"
    )


Bridge.provide("on_probe_attempt", on_probe_attempt)
Bridge.provide("on_probe_result", on_probe_result)
Bridge.provide("on_sample", on_sample)
logger.info("Waiting for ICM-42688-P diagnostic sketch")
App.run()
