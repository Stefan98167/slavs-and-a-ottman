"""Supplier-only negotiation strategy based on live offers and supplier evidence."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class SupplierOnlyPolicy:
    """Set quote targets and evidence use without reading buyer or case data.

    The first counter asks for a percentage reduction from the supplier's opening
    quote. If same-part supplier quote history supports a lower price, the target
    uses that supplier-stated price instead. Later counters respond to movement in
    the supplier's current offer, rather than repeating the first counter forever.
    """

    def __init__(self, counter_discount_pct=5, max_messages_per_supplier=6,
                 concession_share_pct=50):
        try:
            discount = Decimal(str(counter_discount_pct))
        except InvalidOperation as exc:
            raise ValueError("counter_discount_pct must be a number from 0 to less than 100") from exc
        if not discount.is_finite() or not 0 <= discount < 100:
            raise ValueError("counter_discount_pct must be a number from 0 to less than 100")
        if type(max_messages_per_supplier) is not int or max_messages_per_supplier < 1:
            raise ValueError("max_messages_per_supplier must be a positive integer")
        self.counter_discount_pct = discount
        self.max_messages_per_supplier = max_messages_per_supplier
        try:
            concession_share = Decimal(str(concession_share_pct))
        except InvalidOperation as exc:
            raise ValueError("concession_share_pct must be a number from 0 to 100") from exc
        if not concession_share.is_finite() or not 0 <= concession_share <= 100:
            raise ValueError("concession_share_pct must be a number from 0 to 100")
        self.concession_share_pct = concession_share

    def target_price(self, opening_price, *, current_price=None, previous_supplier_price=None,
                     previous_buyer_price=None, historical_low=None, rounds=0):
        """Return a staged counter target, capped by a supplier-stated historical low.

        ``rounds`` counts prior buyer replies. On subsequent counters, the buyer
        shares the configured fraction of the supplier's latest price concession.
        A same-scope historical low can lower the resulting target.
        """
        try:
            opening = Decimal(str(opening_price))
        except InvalidOperation as exc:
            raise ValueError("supplier opening price must be numeric") from exc
        if not opening.is_finite() or opening <= 0:
            raise ValueError("supplier opening price must be finite and positive")
        initial = (opening * (Decimal(1) - self.counter_discount_pct / Decimal(100))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        target = initial
        if (current_price is not None and previous_supplier_price is not None
                and previous_buyer_price is not None and rounds > 0):
            current = self._decimal_price(current_price)
            previous = self._decimal_price(previous_supplier_price)
            prior_target = self._decimal_price(previous_buyer_price)
            concession = max(Decimal(0), previous - current)
            buyer_share = concession * self.concession_share_pct / Decimal(100)
            target = (prior_target + buyer_share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if historical_low is not None:
            low = self._decimal_price(historical_low)
            target = min(target, low)
        if target <= 0:
            raise ValueError("policy target rounds to zero; supplier must clarify price precision")
        return target

    @staticmethod
    def _decimal_price(value):
        try:
            price = Decimal(str(value).strip().replace(",", "."))
        except (InvalidOperation, ValueError, AttributeError) as exc:
            raise ValueError("supplier price evidence must be numeric") from exc
        if not price.is_finite() or price <= 0:
            raise ValueError("supplier price evidence must be finite and positive")
        return price
