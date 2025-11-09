"""Unit tests for order models."""

import pytest
from decimal import Decimal
from datetime import datetime

from src.models.orders import Order, OrderType, OrderSide, OrderStatus, Trade, BBO


class TestOrder:
    """Test Order class."""
    
    def test_create_limit_order(self):
        """Test creating a valid limit order."""
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.5"),
            price=Decimal("50000")
        )
        
        assert order.symbol == "BTC-USDT"
        assert order.order_type == OrderType.LIMIT
        assert order.side == OrderSide.BUY
        assert order.quantity == Decimal("1.5")
        assert order.price == Decimal("50000")
        assert order.status == OrderStatus.PENDING
        assert order.filled_quantity == Decimal("0")
        assert order.remaining_quantity == Decimal("1.5")
    
    def test_create_market_order(self):
        """Test creating a valid market order."""
        order = Order(
            symbol="ETH-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.SELL,
            quantity=Decimal("10")
        )
        
        assert order.order_type == OrderType.MARKET
        assert order.price is None
    
    def test_invalid_quantity(self):
        """Test that negative quantity raises error."""
        with pytest.raises(ValueError, match="quantity must be positive"):
            Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("-1"),
                price=Decimal("50000")
            )
    
    def test_limit_order_requires_price(self):
        """Test that limit order without price raises error."""
        with pytest.raises(ValueError, match="require a price"):
            Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("1"),
            )
    
    def test_market_order_no_price(self):
        """Test that market order with price raises error."""
        with pytest.raises(ValueError, match="should not have a price"):
            Order(
                symbol="BTC-USDT",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("50000")
            )
    
    def test_order_fill(self):
        """Test order fill functionality."""
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("2"),
            price=Decimal("50000")
        )
        
        order.fill(Decimal("1"))
        assert order.filled_quantity == Decimal("1")
        assert order.remaining_quantity == Decimal("1")
        assert order.status == OrderStatus.PARTIAL
        
        order.fill(Decimal("1"))
        assert order.filled_quantity == Decimal("2")
        assert order.remaining_quantity == Decimal("0")
        assert order.status == OrderStatus.FILLED
    
    def test_is_marketable(self):
        """Test order marketability check."""
        buy_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("51000")
        )
        
        # Marketable if price >= best ask
        assert buy_order.is_marketable(Decimal("49000"), Decimal("50000")) is True
        assert buy_order.is_marketable(Decimal("49000"), Decimal("52000")) is False
        
        sell_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("49000")
        )
        
        # Marketable if price <= best bid
        assert sell_order.is_marketable(Decimal("50000"), Decimal("51000")) is True
        assert sell_order.is_marketable(Decimal("48000"), Decimal("51000")) is False


class TestTrade:
    """Test Trade class."""
    
    def test_create_trade(self):
        """Test creating a trade."""
        trade = Trade(
            symbol="BTC-USDT",
            price=Decimal("50000"),
            quantity=Decimal("1"),
            aggressor_side=OrderSide.BUY,
            maker_order_id="maker-123",
            taker_order_id="taker-456"
        )
        
        assert trade.symbol == "BTC-USDT"
        assert trade.price == Decimal("50000")
        assert trade.quantity == Decimal("1")
        assert trade.aggressor_side == OrderSide.BUY
    
    def test_trade_to_dict(self):
        """Test trade serialization."""
        trade = Trade(
            symbol="BTC-USDT",
            price=Decimal("50000"),
            quantity=Decimal("1"),
            aggressor_side=OrderSide.BUY,
            maker_order_id="maker-123",
            taker_order_id="taker-456"
        )
        
        trade_dict = trade.to_dict()
        assert trade_dict["symbol"] == "BTC-USDT"
        assert trade_dict["price"] == "50000"
        assert trade_dict["quantity"] == "1"
        assert trade_dict["aggressor_side"] == "buy"


class TestBBO:
    """Test BBO class."""
    
    def test_create_bbo(self):
        """Test creating BBO."""
        bbo = BBO(
            symbol="BTC-USDT",
            best_bid=Decimal("49900"),
            best_bid_quantity=Decimal("10"),
            best_ask=Decimal("50100"),
            best_ask_quantity=Decimal("15")
        )
        
        assert bbo.symbol == "BTC-USDT"
        assert bbo.best_bid == Decimal("49900")
        assert bbo.best_ask == Decimal("50100")
    
    def test_bbo_to_dict(self):
        """Test BBO serialization."""
        bbo = BBO(
            symbol="BTC-USDT",
            best_bid=Decimal("49900"),
            best_ask=Decimal("50100")
        )
        
        bbo_dict = bbo.to_dict()
        assert bbo_dict["symbol"] == "BTC-USDT"
        assert bbo_dict["best_bid"] == "49900"
        assert bbo_dict["best_ask"] == "50100"
