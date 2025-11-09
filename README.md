# Cryptocurrency Matching Engine

A high-performance cryptocurrency matching engine implementing REG NMS-inspired principles with price-time priority matching, real-time BBO calculation, and comprehensive WebSocket APIs.

## 🚀 Features

### Core Matching Engine
- **Price-Time Priority**: Strict FIFO matching at each price level
- **Internal Order Protection**: Prevents trade-throughs, always matches at best available price
- **Real-time BBO Calculation**: Instantaneous Best Bid and Offer updates
- **Multiple Order Types**:
  - Market Orders: Execute immediately at best available price
  - Limit Orders: Execute at specified price or better
  - IOC (Immediate-Or-Cancel): Execute immediately, cancel remainder
  - FOK (Fill-Or-Kill): Execute completely or cancel entirely

### APIs
- **REST API**: Order submission, cancellation, and market data queries
- **WebSocket APIs**:
  - Order submission stream
  - Market data stream (BBO + L2 order book)
  - Trade execution feed

### Performance
- Optimized data structures using `sortedcontainers.SortedDict`
- Thread-safe operations with RLock
- Target: >1000 orders/second throughput
- Microsecond-precision timestamps

##  Requirements

- Python 3.9+
- Dependencies (see `requirements.txt`):
  - FastAPI
  - uvicorn
  - websockets
  - sortedcontainers
  - pydantic

##  Installation

### 1. Clone or download the project

```powershell
cd c:\Users\user_name\Downloads\project
```

### 2. Create virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Install in development mode (optional)

```powershell
pip install -e .
```

##  Quick Start

### Start the Server

```powershell
python -m src.api.server
```

The server will start on `http://localhost:8000`

### Interactive API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Run Trading Simulation

```powershell
python examples/simulation.py
```

### Run Performance Benchmarks

```powershell
python benchmarks/performance.py
```

## 📖 Usage Examples

### REST API - Submit Order

```python
import requests

order = {
    "symbol": "BTC-USDT",
    "order_type": "limit",
    "side": "buy",
    "quantity": "1.5",
    "price": "50000"
}

response = requests.post("http://localhost:8000/api/v1/orders", json=order)
print(response.json())
```

### REST API - Get BBO

```python
import requests

response = requests.get("http://localhost:8000/api/v1/bbo/BTC-USDT")
bbo = response.json()
print(f"Best Bid: {bbo['best_bid']}")
print(f"Best Ask: {bbo['best_ask']}")
```

### WebSocket - Market Data Stream

```python
import asyncio
import websockets
import json

async def subscribe_market_data():
    uri = "ws://localhost:8000/ws/market-data/BTC-USDT"
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Update: {data}")

asyncio.run(subscribe_market_data())
```

### WebSocket - Trade Feed

```python
import asyncio
import websockets
import json

async def subscribe_trades():
    uri = "ws://localhost:8000/ws/trades/BTC-USDT"
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            trade = json.loads(message)
            print(f"Trade: {trade['quantity']} @ {trade['price']}")

asyncio.run(subscribe_trades())
```

##  Architecture

### Project Structure

```
project/
├── src/
│   ├── models/           # Data models (Order, Trade, BBO)
│   │   └── orders.py
│   ├── matching_engine/  # Core matching engine
│   │   ├── order_book.py # Order book with price levels
│   │   └── engine.py     # Matching logic
│   └── api/              # FastAPI application
│       └── server.py
├── tests/                # Unit tests
│   ├── test_models.py
│   └── test_engine.py
├── examples/             # Usage examples
│   ├── client_example.py
│   └── simulation.py
├── benchmarks/           # Performance testing
│   └── performance.py
├── requirements.txt
├── setup.py
└── README.md
```

### Key Design Decisions

#### 1. Order Book Data Structure
- **SortedDict** for price levels (O(log n) operations)
- Bids sorted in descending order (best bid first)
- Asks sorted in ascending order (best ask first)
- FIFO queues at each price level using `deque`

#### 2. Matching Algorithm
```
For each incoming order:
  1. Determine opposite side book (buy → asks, sell → bids)
  2. Iterate through price levels from best to worst
  3. Check price limit (if applicable)
  4. Match FIFO within each price level
  5. Update order quantities and BBO
  6. Remove fully filled orders
```

#### 3. Order Protection
- No trade-throughs: Orders always execute at best available price
- Price improvement: Better prices always prioritized
- FIFO at each level: Time priority within price level

#### 4. Event-Driven Architecture
- Callbacks for trade executions
- Callbacks for BBO updates
- Async broadcasting to WebSocket clients

##  Testing

### Run All Tests

```powershell
pytest
```

### Run with Coverage

```powershell
pytest --cov=src --cov-report=html
```

### Run Specific Test File

```powershell
pytest tests/test_engine.py -v
```

##  Performance Benchmarks

Expected performance metrics (on typical hardware):

- **Order Submission**: < 100 μs mean latency
- **Order Matching**: < 200 μs mean latency
- **BBO Calculation**: < 10 μs mean latency
- **Throughput**: > 5,000 orders/second

Run benchmarks:
```powershell
python benchmarks/performance.py
```

## 🔧 Configuration

Create a `.env` file for configuration (optional):

```env
# Server Configuration
HOST=0.0.0.0
PORT=8000

# Logging
LOG_LEVEL=INFO
```

##  API Reference

### REST Endpoints

#### POST /api/v1/orders
Submit a new order

**Request Body:**
```json
{
  "symbol": "BTC-USDT",
  "order_type": "limit",
  "side": "buy",
  "quantity": "1.5",
  "price": "50000"
}
```

**Response:**
```json
{
  "order_id": "uuid",
  "status": "filled",
  "filled_quantity": "1.5",
  "remaining_quantity": "0",
  "trades": [...],
  "timestamp": "2025-10-25T12:00:00.000000Z"
}
```

#### POST /api/v1/orders/cancel
Cancel an existing order

#### GET /api/v1/bbo/{symbol}
Get current Best Bid and Offer

#### GET /api/v1/orderbook/{symbol}
Get L2 order book snapshot

### WebSocket Endpoints

#### WS /ws/orders
Order submission via WebSocket

#### WS /ws/market-data/{symbol}
Real-time market data stream (BBO + order book)

#### WS /ws/trades/{symbol}
Real-time trade execution feed

##  REG NMS Principles Implemented

1. **Order Protection Rule**: No trade-throughs of protected quotations
2. **Access Rule**: Fair and non-discriminatory access to quotations
3. **Sub-Penny Rule**: Minimum price increment (implemented via Decimal precision)
4. **Market Data Rules**: Real-time dissemination of quotes and trades

##  Thread Safety

The matching engine uses `threading.RLock()` for thread-safe operations:
- Order submission
- Order cancellation
- BBO calculation
- Order book queries

## 📝 Logging

Comprehensive logging at multiple levels:
- INFO: Order submissions, matches, cancellations
- DEBUG: Detailed matching logic, price level updates
- ERROR: Exceptions and error conditions

##  Order Type Behavior

| Order Type | Immediate Execution | Rests on Book | Cancel Remainder |
|------------|-------------------|---------------|------------------|
| Market     | ✅ Yes            | ❌ No         | ✅ Yes           |
| Limit      | ✅ If marketable  | ✅ Yes        | ❌ No            |
| IOC        | ✅ Yes            | ❌ No         | ✅ Yes           |
| FOK        | ✅ All or nothing | ❌ No         | ✅ If not filled |

##  Contributing

This is a demonstration project. For production use, consider:
- Persistent storage for order book state
- Enhanced error handling and validation
- Risk management and circuit breakers
- Order modification support
- Advanced order types (stop-loss, stop-limit)
- Multi-symbol support optimization
- Maker-taker fee model

##  License

MIT License - feel free to use this for learning and development

##  Author

Developed as a high-performance matching engine demonstration

---

**Note**: This matching engine is for educational and demonstration purposes. For production use, additional features like persistence, failover, and comprehensive monitoring would be required.
