"""
Matching engine core logic with REG NMS-inspired principles.
Implements price-time priority matching and prevents trade-throughs.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Callable
import logging
import threading

from ..models.orders import Order, OrderType, OrderSide, OrderStatus, Trade
from .order_book import OrderBook

logger = logging.getLogger(__name__)


class MatchingEngine:
    """
    Core matching engine implementing price-time priority with order protection.
    
    Key principles:
    - Price-time priority: Best price first, then FIFO within price level
    - No trade-throughs: Orders always execute at best available price
    - Immediate execution: Marketable orders execute immediately
    - BBO maintenance: Real-time best bid/offer calculation
    """
    
    def __init__(self):
        """Initialize the matching engine."""
        self.order_books: dict[str, OrderBook] = {}
        self.trades: List[Trade] = []
        self.lock = threading.RLock()
        
        # Callbacks for event notifications
        self.trade_callbacks: List[Callable[[Trade], None]] = []
        self.bbo_callbacks: List[Callable[[str], None]] = []
        
        logger.info("Matching engine initialized")
    
    def register_trade_callback(self, callback: Callable[[Trade], None]) -> None:
        """
        Register a callback to be notified of trade executions.
        
        Args:
            callback: Function to call with Trade object
        """
        self.trade_callbacks.append(callback)
    
    def register_bbo_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback to be notified of BBO updates.
        
        Args:
            callback: Function to call with symbol
        """
        self.bbo_callbacks.append(callback)
    
    def get_or_create_order_book(self, symbol: str) -> OrderBook:
        """
        Get existing order book or create a new one.
        
        Args:
            symbol: Trading pair
            
        Returns:
            OrderBook instance
        """
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
            logger.info(f"Created new order book for {symbol}")
        return self.order_books[symbol]
    
    def submit_order(self, order: Order) -> dict:
        """
        Submit an order to the matching engine.
        
        Args:
            order: Order to process
            
        Returns:
            Dictionary with execution results
        """
        with self.lock:
            logger.info(f"Received order: {order.order_id} {order.side.value} "
                       f"{order.quantity} {order.symbol} @ {order.price or 'MARKET'}")
            
            order_book = self.get_or_create_order_book(order.symbol)
            trades: List[Trade] = []
            
            try:
                # Process order based on type
                if order.order_type == OrderType.MARKET:
                    trades = self._process_market_order(order, order_book)
                elif order.order_type == OrderType.LIMIT:
                    trades = self._process_limit_order(order, order_book)
                elif order.order_type == OrderType.IOC:
                    trades = self._process_ioc_order(order, order_book)
                elif order.order_type == OrderType.FOK:
                    trades = self._process_fok_order(order, order_book)
                else:
                    raise ValueError(f"Unsupported order type: {order.order_type}")
                
                # Notify BBO update
                self._notify_bbo_update(order.symbol)
                
                # Return execution summary
                return {
                    "order_id": order.order_id,
                    "status": order.status.value,
                    "filled_quantity": str(order.filled_quantity),
                    "remaining_quantity": str(order.remaining_quantity),
                    "trades": [trade.to_dict() for trade in trades],
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
            except Exception as e:
                logger.error(f"Error processing order {order.order_id}: {e}", exc_info=True)
                order.status = OrderStatus.REJECTED
                return {
                    "order_id": order.order_id,
                    "status": OrderStatus.REJECTED.value,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
    
    def _process_market_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Process a market order - execute immediately at best available price(s).
        
        Args:
            order: Market order to process
            order_book: Order book for the symbol
            
        Returns:
            List of executed trades
        """
        trades = self._match_order(order, order_book)
        
        if order.remaining_quantity > 0:
            # Market order could not be fully filled
            order.status = OrderStatus.CANCELLED
            logger.warning(f"Market order {order.order_id} partially filled: "
                         f"{order.filled_quantity}/{order.quantity}, cancelling remainder")
        
        return trades
    
    def _process_limit_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Process a limit order - execute at specified price or better, rest on book.
        
        Args:
            order: Limit order to process
            order_book: Order book for the symbol
            
        Returns:
            List of executed trades
        """
        # Try to match immediately if marketable
        trades = self._match_order(order, order_book)
        
        # If not fully filled, add remaining to book
        if order.remaining_quantity > 0:
            order_book.add_order(order)
            logger.info(f"Limit order {order.order_id} resting on book: "
                       f"{order.remaining_quantity} @ {order.price}")
        
        return trades
    
    def _process_ioc_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Process an Immediate-Or-Cancel order - execute immediately, cancel remainder.
        
        Args:
            order: IOC order to process
            order_book: Order book for the symbol
            
        Returns:
            List of executed trades
        """
        trades = self._match_order(order, order_book)
        
        if order.remaining_quantity > 0:
            order.status = OrderStatus.CANCELLED
            logger.info(f"IOC order {order.order_id} cancelled: "
                       f"filled {order.filled_quantity}, cancelled {order.remaining_quantity}")
        
        return trades
    
    def _process_fok_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Process a Fill-Or-Kill order - execute completely or cancel entirely.
        
        Args:
            order: FOK order to process
            order_book: Order book for the symbol
            
        Returns:
            List of executed trades (empty if order was killed)
        """
        # Check if order can be fully filled
        if not self._can_fill_completely(order, order_book):
            order.status = OrderStatus.CANCELLED
            logger.info(f"FOK order {order.order_id} killed: insufficient liquidity")
            return []
        
        # Execute the order
        trades = self._match_order(order, order_book)
        
        # Should be fully filled, but verify
        if order.remaining_quantity > 0:
            # This shouldn't happen if _can_fill_completely worked correctly
            logger.error(f"FOK order {order.order_id} not fully filled, rolling back")
            # In production, we'd need to reverse the trades
            order.status = OrderStatus.CANCELLED
            return []
        
        return trades
    
    def _can_fill_completely(self, order: Order, order_book: OrderBook) -> bool:
        """
        Check if an order can be completely filled at current prices.
        
        Args:
            order: Order to check
            order_book: Order book for the symbol
            
        Returns:
            True if order can be fully filled
        """
        remaining = order.quantity
        book = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        
        for price, level in book.items():
            # Check price limit
            if order.price is not None:
                if order.side == OrderSide.BUY and price > order.price:
                    break
                if order.side == OrderSide.SELL and price < order.price:
                    break
            
            # Check available quantity
            if level.total_quantity >= remaining:
                return True
            
            remaining -= level.total_quantity
        
        return remaining <= 0
    
    def _match_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Match an order against the book with price-time priority.
        Prevents trade-throughs by always matching at best available price.
        
        Args:
            order: Order to match
            order_book: Order book for the symbol
            
        Returns:
            List of executed trades
        """
        trades: List[Trade] = []
        book = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        
        # Iterate through price levels from best to worst
        while order.remaining_quantity > 0 and book:
            best_price = list(book.keys())[0]
            
            # Check if we can still execute at this price
            if order.price is not None:
                if order.side == OrderSide.BUY and best_price > order.price:
                    break  # No more executable prices
                if order.side == OrderSide.SELL and best_price < order.price:
                    break  # No more executable prices
            
            price_level = book[best_price]
            
            # Match against orders at this price level (FIFO)
            while order.remaining_quantity > 0 and price_level.orders:
                resting_order = price_level.orders[0]
                
                # Determine fill quantity
                fill_quantity = min(order.remaining_quantity, resting_order.remaining_quantity)
                
                # Create trade
                trade = Trade(
                    symbol=order.symbol,
                    price=best_price,
                    quantity=fill_quantity,
                    aggressor_side=order.side,
                    maker_order_id=resting_order.order_id,
                    taker_order_id=order.order_id,
                    timestamp=datetime.utcnow()
                )
                
                # Update orders
                order.fill(fill_quantity)
                resting_order.fill(fill_quantity)
                
                # Update book
                order_book.update_order_quantity(resting_order, fill_quantity)
                
                # Remove fully filled resting order
                if resting_order.remaining_quantity == 0:
                    price_level.orders.popleft()
                    if resting_order.order_id in order_book.orders:
                        del order_book.orders[resting_order.order_id]
                
                trades.append(trade)
                self.trades.append(trade)
                
                logger.info(f"Trade executed: {fill_quantity} {order.symbol} @ {best_price}")
                
                # Notify trade callbacks
                self._notify_trade(trade)
            
            # Remove empty price level (check if it still exists first)
            if best_price in book and price_level.is_empty():
                del book[best_price]
        
        return trades
    
    def cancel_order(self, symbol: str, order_id: str) -> dict:
        """
        Cancel an order.
        
        Args:
            symbol: Trading pair
            order_id: ID of order to cancel
            
        Returns:
            Cancellation result
        """
        with self.lock:
            if symbol not in self.order_books:
                return {
                    "order_id": order_id,
                    "status": "error",
                    "message": f"No order book for {symbol}"
                }
            
            order_book = self.order_books[symbol]
            order = order_book.remove_order(order_id)
            
            if order:
                order.status = OrderStatus.CANCELLED
                self._notify_bbo_update(symbol)
                logger.info(f"Order {order_id} cancelled")
                return {
                    "order_id": order_id,
                    "status": OrderStatus.CANCELLED.value,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            else:
                return {
                    "order_id": order_id,
                    "status": "error",
                    "message": "Order not found"
                }
    
    def get_bbo(self, symbol: str) -> Optional[dict]:
        """
        Get current BBO for a symbol.
        
        Args:
            symbol: Trading pair
            
        Returns:
            BBO data or None
        """
        with self.lock:
            if symbol in self.order_books:
                return self.order_books[symbol].get_bbo().to_dict()
            return None
    
    def get_order_book_snapshot(self, symbol: str, depth: int = 10) -> Optional[dict]:
        """
        Get L2 order book snapshot.
        
        Args:
            symbol: Trading pair
            depth: Number of levels per side
            
        Returns:
            Order book snapshot or None
        """
        with self.lock:
            if symbol in self.order_books:
                return self.order_books[symbol].get_snapshot(depth).to_dict()
            return None
    
    def _notify_trade(self, trade: Trade) -> None:
        """Notify all registered trade callbacks."""
        for callback in self.trade_callbacks:
            try:
                callback(trade)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}", exc_info=True)
    
    def _notify_bbo_update(self, symbol: str) -> None:
        """Notify all registered BBO callbacks."""
        for callback in self.bbo_callbacks:
            try:
                callback(symbol)
            except Exception as e:
                logger.error(f"Error in BBO callback: {e}", exc_info=True)
