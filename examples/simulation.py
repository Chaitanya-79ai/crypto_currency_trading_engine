"""Trading simulation script."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import random
from decimal import Decimal
from src.models.orders import Order, OrderType, OrderSide
from src.matching_engine.engine import MatchingEngine


def create_random_order(symbol: str, base_price: Decimal) -> Order:
    """Generate a random order for testing."""
    side = random.choice([OrderSide.BUY, OrderSide.SELL])
    order_type = random.choice([OrderType.LIMIT, OrderType.MARKET, OrderType.IOC])
    quantity = Decimal(str(round(random.uniform(0.1, 5.0), 2)))
    
    if order_type == OrderType.MARKET:
        price = None
    else:
        # Price within +/- 5% of base price
        variation = random.uniform(-0.05, 0.05)
        price = base_price * Decimal(str(1 + variation))
        price = price.quantize(Decimal("0.01"))
    
    return Order(
        symbol=symbol,
        order_type=order_type,
        side=side,
        quantity=quantity,
        price=price
    )


def print_bbo(engine: MatchingEngine, symbol: str):
    """Print current BBO."""
    bbo = engine.get_bbo(symbol)
    if bbo:
        print(f"\n{'='*60}")
        print(f"BBO for {symbol}:")
        print(f"  Best Bid: {bbo['best_bid']} x {bbo['best_bid_quantity']}")
        print(f"  Best Ask: {bbo['best_ask']} x {bbo['best_ask_quantity']}")
        if bbo['best_bid'] and bbo['best_ask']:
            spread = Decimal(bbo['best_ask']) - Decimal(bbo['best_bid'])
            print(f"  Spread: {spread}")
        print(f"{'='*60}\n")


def print_order_book(engine: MatchingEngine, symbol: str, depth: int = 5):
    """Print order book snapshot."""
    snapshot = engine.get_order_book_snapshot(symbol, depth)
    if snapshot:
        print(f"\nOrder Book for {symbol} (depth={depth}):")
        print(f"\n{'ASKS':^30}")
        print(f"{'Price':<15} {'Quantity':<15}")
        print("-" * 30)
        for price, qty in reversed(snapshot['asks']):
            print(f"{price:<15} {qty:<15}")
        
        print(f"\n{'BIDS':^30}")
        print(f"{'Price':<15} {'Quantity':<15}")
        print("-" * 30)
        for price, qty in snapshot['bids']:
            print(f"{price:<15} {qty:<15}")
        print()


def run_simulation(num_orders: int = 20, symbol: str = "BTC-USDT", base_price: Decimal = Decimal("50000")):
    """Run a trading simulation."""
    print(f"\n{'='*60}")
    print(f"TRADING SIMULATION")
    print(f"{'='*60}")
    print(f"Symbol: {symbol}")
    print(f"Base Price: ${base_price:,.2f}")
    print(f"Number of Orders: {num_orders}")
    print(f"{'='*60}\n")
    
    engine = MatchingEngine()
    trade_count = [0]  # Use list to modify in callback
    
    def on_trade(trade):
        trade_count[0] += 1
        print(f"\n TRADE #{trade_count[0]} EXECUTED:")
        print(f"   {trade.quantity} {trade.symbol} @ ${trade.price}")
        print(f"   Aggressor: {trade.aggressor_side.value}")
        print(f"   Trade ID: {trade.trade_id}")
    
    engine.register_trade_callback(on_trade)
    
    # Submit initial orders to build the book
    print("Building initial order book...")
    for i in range(5):
        # Add buy orders below market
        buy_order = Order(
            symbol=symbol,
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=base_price - Decimal(i * 100)
        )
        engine.submit_order(buy_order)
        
        # Add sell orders above market
        sell_order = Order(
            symbol=symbol,
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=base_price + Decimal(i * 100)
        )
        engine.submit_order(sell_order)
    
    print_order_book(engine, symbol)
    print_bbo(engine, symbol)
    # Submit random orders
    print(f"\nSubmitting {num_orders} random orders...\n")
    for i in range(num_orders):
        order = create_random_order(symbol, base_price)
        print(f"Order {i+1}: {order.side.value.upper()} {order.quantity} @ {order.price or 'MARKET'} ({order.order_type.value})")
        
        result = engine.submit_order(order)
        print(f"  → Status: {result['status']}, Filled: {result['filled_quantity']}, Trades: {len(result['trades'])}")
        
        if (i + 1) % 5 == 0:
            print_bbo(engine, symbol)
    
    print_order_book(engine, symbol, depth=10)
    print_bbo(engine, symbol)
    
    print(f"\n{'='*60}")
    print(f"SIMULATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total Trades Executed: {trade_count[0]}")
    print(f"Total Orders Submitted: {num_orders + 10}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_simulation(num_orders=30)
