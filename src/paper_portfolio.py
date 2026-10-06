"""Future allocation contract. No defaults, simulation or portfolio performance."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioProtocol:
    """An explicit advance registration is required before capital allocation."""

    registration_commit: str
    effective_session: str
    equal_weight: float
    maximum_positions: int
    overlap_policy: str
    entry_timing: str
    exit_policy: str
    cash_benchmark: str
    commission_bps: float
    slippage_bps: float

    def validate(self) -> None:
        if not self.registration_commit or not 0 < self.equal_weight <= 1:
            raise ValueError("Portfolio allocation requires an explicit registration")
        if self.maximum_positions < 1 or self.equal_weight * self.maximum_positions > 1:
            raise ValueError("Registered capacity exceeds available capital")
        if min(self.commission_bps, self.slippage_bps) < 0:
            raise ValueError("Costs cannot be negative")
