"""Example client for the matching engine."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import websockets
import json
from decimal import Decimal


async def order_submission_example():
    """Example: Submit orders via WebSocket."""
    uri = "ws://localhost:8000/ws/orders"
    
    async with websockets.connect(uri) as websocket:
        # Submit a limit buy order
        order1 = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "1.5",
            "price": "50000"
        }
        
        await websocket.send(json.dumps(order1))
        response = await websocket.recv()
        print(f"Order 1 response: {response}")
        
        # Submit a limit sell order
        order2 = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "sell",
            "quantity": "1.0",
            "price": "50000"
        }
        
        await websocket.send(json.dumps(order2))
        response = await websocket.recv()
        print(f"Order 2 response: {response}")


async def market_data_stream_example():
    """Example: Subscribe to market data stream."""
    uri = "ws://localhost:8000/ws/market-data/BTC-USDT"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to market data stream for BTC-USDT")
        
        # Receive updates
        for i in range(10):
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Market data update: {data['type']}")
            print(f"  Data: {data['data']}")
            
            if i % 3 == 0:
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))


async def trade_feed_example():
    """Example: Subscribe to trade execution feed."""
    uri = "ws://localhost:8000/ws/trades/BTC-USDT"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to trade feed for BTC-USDT")
        
        # Receive trade executions
        while True:
            message = await websocket.recv()
            trade = json.loads(message)
            print(f"Trade executed:")
            print(f"  Price: {trade['price']}")
            print(f"  Quantity: {trade['quantity']}")
            print(f"  Aggressor: {trade['aggressor_side']}")
            print(f"  Time: {trade['timestamp']}")


async def rest_api_example():
    """Example: Use REST API for order submission."""
    import aiohttp
    
    url = "http://localhost:8000/api/v1/orders"
    
    order = {
        "symbol": "BTC-USDT",
        "order_type": "limit",
        "side": "buy",
        "quantity": "2.0",
        "price": "49500"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=order) as response:
            result = await response.json()
            print(f"Order submitted via REST API:")
            print(f"  Order ID: {result['order_id']}")
            print(f"  Status: {result['status']}")
            print(f"  Filled: {result['filled_quantity']}")
        
        # Get BBO
        async with session.get("http://localhost:8000/api/v1/bbo/BTC-USDT") as response:
            bbo = await response.json()
            print(f"\nCurrent BBO:")
            print(f"  Best Bid: {bbo['best_bid']} x {bbo['best_bid_quantity']}")
            print(f"  Best Ask: {bbo['best_ask']} x {bbo['best_ask_quantity']}")
        
        # Get order book snapshot
        async with session.get("http://localhost:8000/api/v1/orderbook/BTC-USDT?depth=5") as response:
            orderbook = await response.json()
            print(f"\nOrder Book:")
            print(f"  Bids: {orderbook['bids'][:5]}")
            print(f"  Asks: {orderbook['asks'][:5]}")


if __name__ == "__main__":
    print("=" * 60)
    print("Matching Engine Examples")
    print("=" * 60)
    print("\nMake sure the server is running: python -m src.api.server")
    print("\nChoose an example to run:")
    print("1. Order submission via WebSocket")
    print("2. Market data stream")
    print("3. Trade feed")
    print("4. REST API example")
    
    choice = input("\nEnter choice (1-4): ")
    
    if choice == "1":
        asyncio.run(order_submission_example())
    elif choice == "2":
        asyncio.run(market_data_stream_example())
    elif choice == "3":
        asyncio.run(trade_feed_example())
    elif choice == "4":
        asyncio.run(rest_api_example())
    else:
        print("Invalid choice")

