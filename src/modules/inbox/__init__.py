"""depotru-inbox — Magento orders waiting for a truck.

Shipping slice B. The inbox is the only place a Magento order turns into
something the dispatcher can load: weight, destination, site, and the Magento
id it came from. Everything here is fail-closed — an order without a positive
weight is refused and reported, never given a guessed weight.
"""

from __future__ import annotations
