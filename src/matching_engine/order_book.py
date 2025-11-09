"""Order book implementation with price-time priority."""

from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Tuple
from sortedcontainers import SortedDict
import logging

from ..models.orders import Order, OrderSide, BBO, OrderBookSnapshot

logger = logging.getLogger(__name__)


class PriceLevel:
    """
    Represents a single price level in the order book.
    Maintains FIFO queue for price-time priority.
    """
    
    def __init__(self, price: Decimal):
        """
        Initialize a price level.
        
        Args:
            price: Price for this level
        """
        self.price = price
        self.orders: deque[Order] = deque()
        self.total_quantity = Decimal("0")
    
    def add_order(self, order: Order) -> None:
        """
        Add an order to this price level (FIFO queue).
        
        Args:
            order: Order to add
        """
        self.orders.append(order)
        self.total_quantity += order.remaining_quantity
        logger.debug(f"Added order {order.order_id} to price level {self.price}, "
                    f"total quantity: {self.total_quantity}")
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """
        Remove an order from this price level.
        
        Args:
            order_id: ID of the order to remove
            
        Returns:
            Removed order or None if not found
        """
        for i, order in enumerate(self.orders):
            if order.order_id == order_id:
                removed_order = self.orders[i]
                del self.orders[i]
                self.total_quantity -= removed_order.remaining_quantity
                logger.debug(f"Removed order {order_id} from price level {self.price}, "
                           f"remaining quantity: {self.total_quantity}")
                return removed_order
        return None
    
    def update_quantity(self, quantity_change: Decimal) -> None:
        """
        Update the total quantity at this price level.
        
        Args:
            quantity_change: Change in quantity (can be negative)
        """
        self.total_quantity += quantity_change
    
    def is_empty(self) -> bool:
        """Check if this price level has no orders."""
        return len(self.orders) == 0 or self.total_quantity == 0


class OrderBook:
    """
    Order book for a single trading pair with price-time priority matching.
    Uses SortedDict for efficient price level management.
    """
    
    def __init__(self, symbol: str):
        """
        Initialize an order book for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
        """
        self.symbol = symbol
        # Bids: highest price first (reverse=True)
        self.bids: SortedDict = SortedDict(lambda x: -x)
        # Asks: lowest price first (normal sorting)
        self.asks: SortedDict = SortedDict()
        # Order lookup for cancellations
        self.orders: dict[str, Order] = {}
        
        logger.info(f"Initialized order book for {symbol}")
    
    def add_order(self, order: Order) -> None:
        """
        Add an order to the appropriate side of the book.
        
        Args:
            order: Order to add
        """
        if order.remaining_quantity <= 0:
            logger.warning(f"Attempted to add order {order.order_id} with no remaining quantity")
            return
        
        book = self.bids if order.side == OrderSide.BUY else self.asks
        price = order.price
        
        if price not in book:
            book[price] = PriceLevel(price)
        
        book[price].add_order(order)
        self.orders[order.order_id] = order
        
        logger.info(f"Added {order.side.value} order {order.order_id} "
                   f"for {order.remaining_quantity} @ {price}")
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """
        Remove an order from the book.
        
        Args:
            order_id: ID of the order to remove
            
        Returns:
            Removed order or None if not found
        """
        if order_id not in self.orders:
            logger.warning(f"Order {order_id} not found in book")
            return None
        
        order = self.orders[order_id]
        book = self.bids if order.side == OrderSide.BUY else self.asks
        price = order.price
        
        if price in book:
            removed = book[price].remove_order(order_id)
            if book[price].is_empty():
                del book[price]
            
            if removed:
                del self.orders[order_id]
                logger.info(f"Removed order {order_id} from book")
                return removed
        
        return None
    
    def update_order_quantity(self, order: Order, filled_quantity: Decimal) -> None:
        """
        Update order quantity after a fill.
        
        Args:
            order: Order that was filled
            filled_quantity: Amount that was filled
        """
        book = self.bids if order.side == OrderSide.BUY else self.asks
        price = order.price
        
        if price in book:
            book[price].update_quantity(-filled_quantity)
            
            if book[price].is_empty():
                del book[price]
                logger.debug(f"Price level {price} is empty, removed from book")
    
    def get_best_bid(self) -> Optional[Decimal]:
        """Get the best (highest) bid price."""
        return self.bids.keys()[0] if self.bids else None
    
    def get_best_ask(self) -> Optional[Decimal]:
        """Get the best (lowest) ask price."""
        return self.asks.keys()[0] if self.asks else None
    
    def get_bbo(self) -> BBO:
        """
        Calculate and return the current Best Bid and Offer.
        
        Returns:
            BBO object with current best bid and ask
        """
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        return BBO(
            symbol=self.symbol,
            best_bid=best_bid,
            best_bid_quantity=self.bids[best_bid].total_quantity if best_bid else Decimal("0"),
            best_ask=best_ask,
            best_ask_quantity=self.asks[best_ask].total_quantity if best_ask else Decimal("0"),
            timestamp=datetime.utcnow()
        )
    
    def get_snapshot(self, depth: int = 10) -> OrderBookSnapshot:
        """
        Get L2 order book snapshot with specified depth.
        
        Args:
            depth: Number of price levels to include on each side
            
        Returns:
            OrderBookSnapshot with bids and asks
        """
        bids = []
        for i, (price, level) in enumerate(self.bids.items()):
            if i >= depth:
                break
            bids.append((str(price), str(level.total_quantity)))
        
        asks = []
        for i, (price, level) in enumerate(self.asks.items()):
            if i >= depth:
                break
            asks.append((str(price), str(level.total_quantity)))
        
        return OrderBookSnapshot(
            symbol=self.symbol,
            bids=bids,
            asks=asks,
            timestamp=datetime.utcnow()
        )
    
    def get_market_price(self, side: OrderSide) -> Optional[Decimal]:
        """
        Get the price a market order would execute at.
        
        Args:
            side: Side of the market order
            
        Returns:
            Best available price or None if no liquidity
        """
        if side == OrderSide.BUY:
            return self.get_best_ask()
        else:
            return self.get_best_bid()
