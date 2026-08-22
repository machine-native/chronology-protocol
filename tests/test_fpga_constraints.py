"""Guard the one FPGA fact that was established by measurement, not reading.

The UART link was silent in both directions for three build cycles, because the
two port DIRECTIONS were inverted. The pin numbers matched Digilent's master XDC
exactly; their net names are relative to the HOST side, so `uart_txd_in` is data
the host transmits INTO the board -- an FPGA input -- and it had been declared an
output. The FPGA therefore drove J17 against the FT2232's own driver.

Measured on 2026-08-22 with `fpga/rtl/pinprobe.v` and the host transmitting
continuously: J17 carried edges, J18 was static. The FPGA receives on J17.

Note this was the FIRST hypothesis raised during bring-up, and it was abandoned
on the strength of a single web search that stated the opposite. The search was
wrong. Three further theories were pursued before an instrument settled it.

These tests exist because that fact cannot be re-derived by reading. Anyone who
"tidies" the constraints back toward the vendor's net names, or swaps the pins to
match a datasheet reading, gets a failure here that points at the evidence rather
than a silent board that does nothing.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XDC = ROOT / "fpga" / "constraints" / "cmod_a7.xdc"
TOP = ROOT / "fpga" / "rtl" / "miner_top.v"


def _assignments():
    """Map port name -> package pin, from the miner's constraints file."""
    text = XDC.read_text()
    found = {}
    for m in re.finditer(
        r"PACKAGE_PIN\s+(\w+).*?get_ports\s*\{\s*([\w\[\]]+)\s*\}", text, re.S
    ):
        found[m.group(2).strip()] = m.group(1)
    return found


def test_fpga_receives_on_j17_and_transmits_on_j18():
    a = _assignments()
    assert a.get("uart_rx_from_host") == "J17", (
        "The FPGA's receive pin must be J17. Measured 2026-08-22: with the host "
        "transmitting continuously, J17 showed edges and J18 was static. "
        "Swapping these two makes the board silent in both directions with no "
        "error anywhere -- it builds, meets timing, and does nothing."
    )
    assert a.get("uart_tx_to_host") == "J18", (
        "The FPGA's transmit pin must be J18 -- see fpga/rtl/pinprobe.v."
    )


def test_port_names_state_their_direction():
    """Ambiguous names caused this bug; keep the unambiguous ones."""
    src = TOP.read_text()
    assert "input  wire uart_rx_from_host" in src
    assert "output wire uart_tx_to_host" in src
    # The vendor names may appear in comments explaining the history, but must
    # not come back as actual ports -- that is what reintroduced the ambiguity.
    ports = re.search(r"\)\s*\(\s*(.*?)\n\);", src, re.S)
    assert ports, "could not locate miner_top's port list"
    body = "\n".join(
        line for line in ports.group(1).splitlines()
        if not line.strip().startswith("//")
    )
    for vendor in ("uart_rxd_out", "uart_txd_in"):
        assert vendor not in body, (
            f"{vendor} is back in the port list. Its direction is ambiguous "
            "(bridge-relative or host-relative, both grammatical), which is how "
            "the pins got crossed in the first place."
        )


def test_clock_pin_and_period_agree_with_a_12mhz_board():
    """The INPUT clock is 12 MHz; the MMCM derives the logic clock from it."""
    text = XDC.read_text()
    assert re.search(r"PACKAGE_PIN\s+L17.*?get_ports\s*\{\s*clk_12mhz\s*\}", text, re.S)
    period = re.search(r"create_clock.*?-period\s+([\d.]+)", text, re.S)
    assert period, "no create_clock constraint for the board oscillator"
    # 12 MHz -> 83.33 ns. This constrains the MMCM's INPUT; get it wrong and the
    # MMCM synthesises a different frequency than CLK_HZ claims, which corrupts
    # every UART bit period derived from it.
    assert abs(float(period.group(1)) - 83.33) < 0.5, period.group(1)
    src = TOP.read_text()
    assert "CLKIN1_PERIOD   (83.333)" in src, "MMCM input period must match the board"


def test_mmcm_frequency_is_reachable_from_the_fixed_vco():
    """CLK_HZ must divide the VCO exactly, or the MMCM produces something else.

    The logic clock, the baud divisor and the heartbeat are all derived from
    CLK_HZ. If the MMCM cannot actually synthesise it, every one of those is
    wrong together -- and the symptom is a UART emitting garbage, which is a
    long way from the cause.
    """
    src = TOP.read_text()
    vco = re.search(r"MMCM_VCO_MHZ = ([\d.]+)", src)
    clk = re.search(r"parameter integer CLK_HZ\s*=\s*([\d_]+)", src)
    assert vco and clk, "MMCM VCO or CLK_HZ default not found"
    vco_mhz = float(vco.group(1))
    clk_mhz = int(clk.group(1).replace("_", "")) / 1e6
    # CLKOUT0_DIVIDE_F moves in steps of 0.125, so the reachable set is wider
    # than the integer divisors -- what matters is that 600/f lands on one of
    # those steps, not that it is a whole number.
    # Tolerance is 0.01, not machine epsilon: legal divide steps are 1.0 apart
    # in these units, while a frequency like 69.565217 MHz cannot be written
    # exactly in integer Hz. Demanding exactness rejects legal frequencies for
    # a rounding artefact -- 0.01 discriminates the real cases with room to
    # spare, since an unreachable frequency lands hundreds of times further out.
    div = vco_mhz / clk_mhz
    assert abs(div * 8 - round(div * 8)) < 0.01, (
        f"{clk_mhz} MHz needs CLKOUT0_DIVIDE_F = {div}, which is not a multiple "
        "of 0.125; the MMCM would synthesise something else and every value "
        "derived from CLK_HZ -- baud divisor included -- would be wrong"
    )
    assert 1.0 <= div <= 128.0, div
    # 600-1200 MHz is the Artix-7 -1 VCO range; 12 MHz x 50 = 600 sits at the
    # bottom of it, which is legal. Outside it the MMCM will not lock at all.
    assert 600.0 <= vco_mhz <= 1200.0, vco_mhz


def test_cores_interleave_rather_than_slice():
    """Each core must stride by NUM_CORES, or coverage is wrong or duplicated."""
    src = TOP.read_text()
    assert ".NONCE_STRIDE(NUM_CORES)" in src, (
        "cores must stride by NUM_CORES so that together they cover every nonce "
        "exactly once; a stride of 1 makes every core scan the same nonces"
    )
    assert ".nonce_start(nonce_start + g[31:0])" in src, (
        "core i must start at nonce_start + i, or the lanes overlap and some "
        "nonces are never visited at all"
    )
