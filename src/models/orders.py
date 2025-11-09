"""Order and trade data models."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


class OrderType(str, Enum):
    """Supported order types."""
    MARKET = "market"
    LIMIT = "limit"
    IOC = "ioc"  # Immediate-Or-Cancel
    FOK = "fok"  # Fill-Or-Kill


class OrderSide(str, Enum):
    """Order side: buy or sell."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status throughout its lifecycle."""
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """
    Represents a trading order in the matching engine.
    
    Attributes:
        order_id: Unique identifier for the order
        symbol: Trading pair (e.g., "BTC-USDT")
        order_type: Type of order (market, limit, ioc, fok)
        side: Buy or sell
        quantity: Order quantity
        price: Limit price (None for market orders)
        timestamp: Order creation timestamp with microsecond precision
        status: Current order status
        filled_quantity: Amount filled so far
        remaining_quantity: Amount remaining to be filled
    """
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    order_type: OrderType = OrderType.LIMIT
    side: OrderSide = OrderSide.BUY
    quantity: Decimal = Decimal("0")
    price: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = Decimal("0")
    remaining_quantity: Decimal = field(init=False)
    
    def __post_init__(self):
        """Initialize computed fields."""
        self.remaining_quantity = self.quantity - self.filled_quantity
        
        # Validate order parameters
        if self.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        
        if self.order_type != OrderType.MARKET and self.price is None:
            raise ValueError(f"{self.order_type} orders require a price")
        
        if self.order_type == OrderType.MARKET and self.price is not None:
            raise ValueError("Market orders should not have a price")
        
        if self.price is not None and self.price <= 0:
            raise ValueError("Order price must be positive")
    
    def is_marketable(self, best_bid: Optional[Decimal], best_ask: Optional[Decimal]) -> bool:
        """
        Check if this order can be immediately matched.
        
        Args:
            best_bid: Current best bid price
            best_ask: Current best ask price
            
        Returns:
            True if the order can be immediately matched
        """
        if self.order_type == OrderType.MARKET:
            return True
        
        if self.side == OrderSide.BUY and best_ask is not None:
            return self.price >= best_ask
        
        if self.side == OrderSide.SELL and best_bid is not None:
            return self.price <= best_bid
        
        return False
    
    def fill(self, quantity: Decimal) -> None:
        """
        Partially or fully fill the order.
        
        Args:
            quantity: Amount to fill
        """
        if quantity <= 0:
            raise ValueError("Fill quantity must be positive")
        
        if quantity > self.remaining_quantity:
            raise ValueError("Fill quantity exceeds remaining quantity")
        
        self.filled_quantity += quantity
        self.remaining_quantity -= quantity
        
        if self.remaining_quantity == 0:
            self.status = OrderStatus.FILLED
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIAL


@dataclass
class Trade:
    """
    Represents an executed trade.
    
    Attributes:
        trade_id: Unique identifier for the trade
        symbol: Trading pair
        price: Execution price
        quantity: Executed quantity
        timestamp: Trade execution timestamp with microsecond precision
        aggressor_side: Side of the incoming order that initiated the trade
        maker_order_id: ID of the resting order on the book
        taker_order_id: ID of the incoming order
        maker_fee: Fee charged to the maker (optional)
        taker_fee: Fee charged to the taker (optional)
    """
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggressor_side: OrderSide = OrderSide.BUY
    maker_order_id: str = ""
    taker_order_id: str = ""
    maker_fee: Optional[Decimal] = None
    taker_fee: Optional[Decimal] = None
    
    def to_dict(self) -> dict:
        """Convert trade to dictionary for API responses."""
        return {
            "timestamp": self.timestamp.isoformat() + "Z",
            "symbol": self.symbol,
            "trade_id": self.trade_id,
            "price": str(self.price),
            "quantity": str(self.quantity),
            "aggressor_side": self.aggressor_side.value,
            "maker_order_id": self.maker_order_id,
            "taker_order_id": self.taker_order_id,
            **({"maker_fee": str(self.maker_fee)} if self.maker_fee is not None else {}),
            **({"taker_fee": str(self.taker_fee)} if self.taker_fee is not None else {}),
        }


@dataclass
class BBO:
    """
    Best Bid and Offer (BBO) data.
    
    Attributes:
        symbol: Trading pair
        best_bid: Best bid price
        best_bid_quantity: Total quantity at best bid
        best_ask: Best ask price
        best_ask_quantity: Total quantity at best ask
        timestamp: BBO update timestamp
    """
    symbol: str
    best_bid: Optional[Decimal] = None
    best_bid_quantity: Decimal = Decimal("0")
    best_ask: Optional[Decimal] = None
    best_ask_quantity: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert BBO to dictionary for API responses."""
        return {
            "timestamp": self.timestamp.isoformat() + "Z",
            "symbol": self.symbol,
            "best_bid": str(self.best_bid) if self.best_bid else None,
            "best_bid_quantity": str(self.best_bid_quantity),
            "best_ask": str(self.best_ask) if self.best_ask else None,
            "best_ask_quantity": str(self.best_ask_quantity),
        }


@dataclass
class OrderBookSnapshot:
    """
    L2 Order book snapshot with depth.
    
    Attributes:
        symbol: Trading pair
        bids: List of [price, quantity] for bid side
        asks: List of [price, quantity] for ask side
        timestamp: Snapshot timestamp
    """
    symbol: str
    bids: list[tuple[str, str]] = field(default_factory=list)
    asks: list[tuple[str, str]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert order book snapshot to dictionary for API responses."""
        return {
            "timestamp": self.timestamp.isoformat() + "Z",
            "symbol": self.symbol,
            "bids": self.bids,
            "asks": self.asks,
        }
