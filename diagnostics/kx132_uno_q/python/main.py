from arduino.app_utils import App, Bridge, Logger


logger = Logger("kx134-diag")


def on_probe_attempt(mode: int, who_am_i: int) -> None:
    logger.info(f"PROBE mode={mode} WHO_AM_I=0x{who_am_i:02X}")


def on_probe_result(ready: bool, who_am_i: int, mode: int) -> None:
    level = "PASS" if ready else "FAIL"
    logger.info(f"{level} ready={ready} WHO_AM_I=0x{who_am_i:02X} spi_mode={mode}")


def on_bitbang_probe(mode: int, who_am_i: int) -> None:
    logger.info(f"BITBANG mode={mode} WHO_AM_I=0x{who_am_i:02X}")


def on_bitbang_result(ready: bool, miso_idle: int) -> None:
    level = "PASS" if ready else "FAIL"
    logger.info(f"BITBANG {level} ready={ready} MISO_IDLE={miso_idle}")


def on_buffered_probe(who_am_i: int) -> None:
    level = "PASS" if who_am_i == 0x46 else "FAIL"
    logger.info(f"BUFFERED_SPI {level} WHO_AM_I=0x{who_am_i:02X}")


def on_irq_rate(count: int) -> None:
    logger.info(f"INT1 data-ready edges={count}/s")


def on_transfer16_probe(value: int) -> None:
    logger.info(f"TRANSFER16 response=0x{value:04X}")


def on_fast_gpio_probe(who_am_i: int, elapsed_us: int) -> None:
    rate = 1_000_000_000 / elapsed_us if elapsed_us else 0
    logger.info(
        f"FAST_GPIO WHO_AM_I=0x{who_am_i:02X} "
        f"1000_reads={elapsed_us}us effective_register_reads={rate:.0f}/s"
    )


def on_sample(ax: int, ay: int, az: int, sample_number: int) -> None:
    logger.info(
        f"SAMPLE n={sample_number} raw=({ax},{ay},{az}) "
        f"g=({ax/512:.3f},{ay/512:.3f},{az/512:.3f})"
    )


Bridge.provide("on_probe_attempt", on_probe_attempt)
Bridge.provide("on_probe_result", on_probe_result)
Bridge.provide("on_bitbang_probe", on_bitbang_probe)
Bridge.provide("on_bitbang_result", on_bitbang_result)
Bridge.provide("on_buffered_probe", on_buffered_probe)
Bridge.provide("on_irq_rate", on_irq_rate)
Bridge.provide("on_transfer16_probe", on_transfer16_probe)
Bridge.provide("on_fast_gpio_probe", on_fast_gpio_probe)
Bridge.provide("on_sample", on_sample)
logger.info("Waiting for KX134-1211 diagnostic sketch")
App.run()
