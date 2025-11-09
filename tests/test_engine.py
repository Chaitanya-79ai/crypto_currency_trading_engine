"""Unit tests for the matching engine core logic."""

import pytest
from decimal import Decimal

from src.models.orders import Order, OrderType, OrderSide, OrderStatus
from src.matching_engine.engine import MatchingEngine


class TestMatchingEngine:
    """Test MatchingEngine class."""
    
    @pytest.fixture
    def engine(self):
        """Create a fresh matching engine for each test."""
        return MatchingEngine()
    
    def test_submit_limit_order_no_match(self, engine):
        """Test submitting a limit order that doesn't match."""
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        
        result = engine.submit_order(order)
        
        assert result["status"] == OrderStatus.PENDING.value
        assert result["filled_quantity"] == "0"
        assert result["remaining_quantity"] == "1"
        assert len(result["trades"]) == 0
    
    def test_match_two_limit_orders(self, engine):
        """Test matching two limit orders."""
        # Submit sell order
        sell_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        engine.submit_order(sell_order)
        
        # Submit matching buy order
        buy_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        result = engine.submit_order(buy_order)
        
        assert result["status"] == OrderStatus.FILLED.value
        assert result["filled_quantity"] == "1"
        assert len(result["trades"]) == 1
        assert result["trades"][0]["price"] == "50000"
        assert result["trades"][0]["quantity"] == "1"
    
    def test_price_time_priority(self, engine):
        """Test that orders are matched in price-time priority."""
        # Submit three sell orders at same price
        for i in range(3):
            order = Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("50000")
            )
            engine.submit_order(order)
        
        # Get order IDs from book (should be in FIFO order)
        book = engine.order_books["BTC-USDT"]
        price_level = book.asks[Decimal("50000")]
        first_order_id = price_level.orders[0].order_id
        
        # Submit buy order that matches partially
        buy_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        result = engine.submit_order(buy_order)
        
        # First order should be matched
        assert result["trades"][0]["maker_order_id"] == first_order_id
    
    def test_no_trade_through(self, engine):
        """Test that orders don't trade through better prices."""
        # Submit sell order at 50000
        sell_order1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        engine.submit_order(sell_order1)
        
        # Submit sell order at 50100
        sell_order2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("50100")
        )
        engine.submit_order(sell_order2)
        
        # Submit buy order at 50100 - should match 50000 first
        buy_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("2"),
            price=Decimal("50100")
        )
        result = engine.submit_order(buy_order)
        
        assert len(result["trades"]) == 2
        assert result["trades"][0]["price"] == "50000"  # Better price first
        assert result["trades"][1]["price"] == "50100"
    
    def test_market_order(self, engine):
        """Test market order execution."""
        # Submit sell order
        sell_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        engine.submit_order(sell_order)
        
        # Submit market buy order
        market_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("1")
        )
        result = engine.submit_order(market_order)
        
        assert result["status"] == OrderStatus.FILLED.value
        assert len(result["trades"]) == 1
    
    def test_ioc_order_partial_fill(self, engine):
        """Test IOC order with partial fill."""
        # Submit sell order for 1 BTC
        sell_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        engine.submit_order(sell_order)
        
        # Submit IOC buy order for 2 BTC
        ioc_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.IOC,
            side=OrderSide.BUY,
            quantity=Decimal("2"),
            price=Decimal("50000")
        )
        result = engine.submit_order(ioc_order)
        
        assert result["status"] == OrderStatus.CANCELLED.value
        assert result["filled_quantity"] == "1"
        assert result["remaining_quantity"] == "1"
    
    def test_fok_order_success(self, engine):
        """Test FOK order with full fill."""
        # Submit sell order
        sell_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("2"),
            price=Decimal("50000")
        )
        engine.submit_order(sell_order)
        
        # Submit FOK buy order
        fok_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("2"),
            price=Decimal("50000")
        )
        result = engine.submit_order(fok_order)
        
        assert result["status"] == OrderStatus.FILLED.value
        assert result["filled_quantity"] == "2"
    
    def test_fok_order_kill(self, engine):
        """Test FOK order gets killed when insufficient liquidity."""
        # Submit sell order for 1 BTC
        sell_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        engine.submit_order(sell_order)
        
        # Submit FOK buy order for 2 BTC
        fok_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("2"),
            price=Decimal("50000")
        )
        result = engine.submit_order(fok_order)
        
        assert result["status"] == OrderStatus.CANCELLED.value
        assert result["filled_quantity"] == "0"
        assert len(result["trades"]) == 0
    
    def test_cancel_order(self, engine):
        """Test order cancellation."""
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        result = engine.submit_order(order)
        order_id = result["order_id"]
        
        # Cancel the order
        cancel_result = engine.cancel_order("BTC-USDT", order_id)
        
        assert cancel_result["status"] == OrderStatus.CANCELLED.value
    
    def test_get_bbo(self, engine):
        """Test BBO calculation."""
        # Submit orders
        buy_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("49900")
        )
        engine.submit_order(buy_order)
        
        sell_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("50100")
        )
        engine.submit_order(sell_order)
        
        # Get BBO
        bbo = engine.get_bbo("BTC-USDT")
        
        assert bbo["best_bid"] == "49900"
        assert bbo["best_ask"] == "50100"
    
    def test_partial_fill_updates_bbo(self, engine):
        """Test that partial fills update BBO correctly."""
        # Submit sell orders at same price
        for _ in range(2):
            order = Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("50000")
            )
            engine.submit_order(order)
        
        # Submit buy order that partially fills
        buy_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("50000")
        )
        engine.submit_order(buy_order)
        
        # BBO should still show 50000 ask with reduced quantity
        bbo = engine.get_bbo("BTC-USDT")
        assert bbo["best_ask"] == "50000"
        assert bbo["best_ask_quantity"] == "1"


class TestOrderBookSnapshot:
    """Test order book snapshot functionality."""
    
    @pytest.fixture
    def engine(self):
        """Create a fresh matching engine."""
        return MatchingEngine()
    
    def test_order_book_snapshot(self, engine):
        """Test L2 order book snapshot."""
        # Submit multiple orders
        for i in range(5):
            buy_order = Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal(50000 - i * 100)
            )
            engine.submit_order(buy_order)
            
            sell_order = Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal(50100 + i * 100)
            )
            engine.submit_order(sell_order)
        
        # Get snapshot
        snapshot = engine.get_order_book_snapshot("BTC-USDT", depth=3)
        
        assert len(snapshot["bids"]) == 3
        assert len(snapshot["asks"]) == 3
        assert snapshot["bids"][0][0] == "50000"  # Best bid
        assert snapshot["asks"][0][0] == "50100"  # Best ask
