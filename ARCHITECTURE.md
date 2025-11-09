# System Architecture

## Overview

The Cryptocurrency Matching Engine is designed with a modular architecture that separates concerns and enables high performance.

## Components

### 1. Data Models (`src/models/`)

**orders.py**
- `Order`: Represents trading orders with validation
- `Trade`: Represents executed trades
- `BBO`: Best Bid and Offer data structure
- `OrderBookSnapshot`: L2 order book representation
- Enums: `OrderType`, `OrderSide`, `OrderStatus`

**Key Design Decisions:**
- Use of `dataclasses` for clean, performant data structures
- `Decimal` type for precise financial calculations
- Microsecond-precision timestamps for accurate ordering
- Built-in validation in `__post_init__`

### 2. Matching Engine (`src/matching_engine/`)

**order_book.py**

The `OrderBook` class maintains the state for a single trading pair:

```
OrderBook
├── bids: SortedDict[Decimal, PriceLevel]  # Descending order
├── asks: SortedDict[Decimal, PriceLevel]  # Ascending order
└── orders: dict[str, Order]               # Fast lookup
```

`PriceLevel` maintains FIFO queue:
```
PriceLevel
├── price: Decimal
├── orders: deque[Order]  # FIFO queue
└── total_quantity: Decimal
```

**Data Structure Rationale:**
- `SortedDict`: O(log n) insertion, deletion, and best price lookup
- `deque`: O(1) append and popleft for FIFO queue
- Bids sorted negatively for efficient best-bid-first iteration
- Separate order index for O(1) cancellation lookups

**engine.py**

The `MatchingEngine` orchestrates order processing:

```
MatchingEngine
├── order_books: dict[symbol, OrderBook]
├── trades: List[Trade]
├── lock: RLock (for thread safety)
└── callbacks: List[Callable]
```

**Matching Algorithm Flow:**

```
1. Receive Order
   ├─> Validate parameters
   └─> Determine order type
       
2. Match Against Book
   ├─> Select opposite side (buy → asks, sell → bids)
   ├─> Iterate price levels (best to worst)
   │   ├─> Check price limit
   │   ├─> Match FIFO within level
   │   ├─> Create Trade objects
   │   └─> Update quantities
   └─> Remove fully filled orders
   
3. Handle Remainder
   ├─> Limit: Add to book if remaining
   ├─> Market: Cancel remainder
   ├─> IOC: Cancel remainder
   └─> FOK: Cancel all if not fully filled
   
4. Update BBO
   └─> Broadcast to subscribers
```

### 3. API Layer (`src/api/`)

**server.py**

FastAPI application providing:

**REST Endpoints:**
- `POST /api/v1/orders` - Submit order
- `POST /api/v1/orders/cancel` - Cancel order
- `GET /api/v1/bbo/{symbol}` - Get BBO
- `GET /api/v1/orderbook/{symbol}` - Get L2 snapshot

**WebSocket Endpoints:**
- `WS /ws/orders` - Order submission stream
- `WS /ws/market-data/{symbol}` - Market data stream
- `WS /ws/trades/{symbol}` - Trade execution feed

**Connection Management:**
```
ConnectionManager
├── market_data_connections: dict[symbol, List[WebSocket]]
├── trade_connections: dict[symbol, List[WebSocket]]
└── Methods:
    ├─> connect()
    ├─> disconnect()
    ├─> broadcast_market_data()
    └─> broadcast_trade()
```

## REG NMS Implementation

### Order Protection Rule

**Requirement:** Prevent trade-throughs of protected quotations

**Implementation:**
```python
# In _match_order()
while order.remaining_quantity > 0 and book:
    best_price = list(book.keys())[0]  # Always best price
    
    # Check price limit
    if order.price is not None:
        if order.side == OrderSide.BUY and best_price > order.price:
            break  # Stop, would trade through
        if order.side == OrderSide.SELL and best_price < order.price:
            break  # Stop, would trade through
```

### Price-Time Priority

**Requirement:** Best price first, FIFO within price

**Implementation:**
- SortedDict maintains price ordering
- deque at each price level maintains time ordering
- Orders matched in strict sequence

### BBO Dissemination

**Requirement:** Real-time quote updates

**Implementation:**
```python
def _notify_bbo_update(self, symbol: str):
    """Callback triggered after every order book change"""
    bbo = self.get_bbo(symbol)
    for callback in self.bbo_callbacks:
        callback(symbol)  # Async broadcast to WebSockets
```

## Thread Safety

**Concurrency Model:**
- `threading.RLock()` protects critical sections
- All public methods acquire lock
- Callbacks executed outside lock to prevent deadlock

**Critical Sections:**
```python
with self.lock:
    # Order submission
    # Order matching
    # Order cancellation
    # BBO calculation
```

## Performance Optimizations

### 1. Data Structures
- SortedDict: O(log n) vs O(n) for sorted list
- deque: O(1) FIFO operations
- dict lookup: O(1) order cancellation

### 2. Minimal Copying
- Orders modified in place
- No unnecessary object creation during matching

### 3. Early Termination
- Break out of loops when price limits exceeded
- FOK checks liquidity before executing

### 4. Efficient BBO
- Best bid/ask: O(1) lookup (first key in SortedDict)
- No iteration required

## Event Flow

```
Order Submission
      │
      ▼
┌─────────────┐
│  Validate   │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│   Match     │────────┐
│  Against    │        │
│    Book     │        │ Creates
└─────┬───────┘        │
      │                │
      ▼                ▼
┌─────────────┐  ┌──────────┐
│   Update    │  │  Trade   │
│    Book     │  │  Events  │
└─────┬───────┘  └────┬─────┘
      │               │
      ▼               │
┌─────────────┐       │
│ Update BBO  │       │
└─────┬───────┘       │
      │               │
      └───────┬───────┘
              │
              ▼
      ┌───────────────┐
      │   Broadcast   │
      │  WebSocket    │
      │    Updates    │
      └───────────────┘
```

## Scalability Considerations

### Current Implementation
- Single-threaded matching per symbol
- In-memory order book
- Synchronous matching

### Future Enhancements
- Symbol-level partitioning for parallel processing
- Persistent order book (Redis, PostgreSQL)
- Async matching with event queues
- Distributed matching across multiple nodes

## Error Handling

**Validation Errors:**
- Invalid order parameters → HTTP 400
- Missing required fields → ValueError

**Runtime Errors:**
- Order not found → HTTP 404
- Symbol not found → HTTP 404

**System Errors:**
- Exceptions logged with full traceback
- Order marked as REJECTED
- Client receives error response

## Monitoring and Logging

**Log Levels:**
- **DEBUG**: Price level updates, detailed matching
- **INFO**: Order submissions, trades, cancellations
- **WARNING**: Partial fills, unusual conditions
- **ERROR**: Exceptions, system errors

**Key Metrics to Monitor:**
- Order submission latency
- Matching latency
- BBO update latency
- Throughput (orders/second)
- Active WebSocket connections
- Order book depth

## Testing Strategy

**Unit Tests:**
- Model validation
- Order book operations
- Matching algorithm correctness
- Edge cases (FOK, IOC behavior)

**Integration Tests:**
- API endpoints
- WebSocket connections
- End-to-end order flow

**Performance Tests:**
- Benchmark throughput
- Measure latencies (p50, p95, p99)
- Stress testing with high load
