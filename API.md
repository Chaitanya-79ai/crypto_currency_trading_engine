# API Documentation

## REST API

Base URL: `http://localhost:8000`

### Authentication

Currently, no authentication is required. For production use, implement API keys or OAuth2.

---

## Endpoints

### Submit Order

Submit a new order to the matching engine.

**Endpoint:** `POST /api/v1/orders`

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

**Parameters:**
- `symbol` (string, required): Trading pair (e.g., "BTC-USDT", "ETH-USDT")
- `order_type` (string, required): One of: "market", "limit", "ioc", "fok"
- `side` (string, required): "buy" or "sell"
- `quantity` (string, required): Order quantity as decimal string
- `price` (string, optional): Limit price (required for non-market orders)

**Response:** `200 OK`
```json
{
  "order_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "filled",
  "filled_quantity": "1.5",
  "remaining_quantity": "0",
  "trades": [
    {
      "timestamp": "2025-10-25T12:00:00.000000Z",
      "symbol": "BTC-USDT",
      "trade_id": "987fcdeb-51a2-43f1-b789-123456789abc",
      "price": "50000",
      "quantity": "1.5",
      "aggressor_side": "buy",
      "maker_order_id": "abc123...",
      "taker_order_id": "123e4567..."
    }
  ],
  "timestamp": "2025-10-25T12:00:00.000000Z"
}
```

**Status Values:**
- `pending`: Order resting on book
- `partial`: Partially filled
- `filled`: Fully filled
- `cancelled`: Cancelled (IOC, FOK, or manual)
- `rejected`: Validation error

**Error Response:** `400 Bad Request`
```json
{
  "detail": "Order quantity must be positive"
}
```

---

### Cancel Order

Cancel an existing order on the book.

**Endpoint:** `POST /api/v1/orders/cancel`

**Request Body:**
```json
{
  "symbol": "BTC-USDT",
  "order_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Response:** `200 OK`
```json
{
  "order_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "cancelled",
  "timestamp": "2025-10-25T12:00:01.000000Z"
}
```

**Error Response:** `404 Not Found`
```json
{
  "detail": "Order not found"
}
```

---

### Get BBO

Get current Best Bid and Offer for a symbol.

**Endpoint:** `GET /api/v1/bbo/{symbol}`

**Parameters:**
- `symbol` (path): Trading pair

**Example:** `GET /api/v1/bbo/BTC-USDT`

**Response:** `200 OK`
```json
{
  "timestamp": "2025-10-25T12:00:00.000000Z",
  "symbol": "BTC-USDT",
  "best_bid": "49900",
  "best_bid_quantity": "10.5",
  "best_ask": "50100",
  "best_ask_quantity": "8.2"
}
```

**Notes:**
- `best_bid` and `best_ask` may be `null` if no orders on that side
- Quantities are aggregated at each price level

---

### Get Order Book

Get L2 order book snapshot with depth.

**Endpoint:** `GET /api/v1/orderbook/{symbol}`

**Parameters:**
- `symbol` (path): Trading pair
- `depth` (query, optional): Number of levels per side (default: 10)

**Example:** `GET /api/v1/orderbook/BTC-USDT?depth=5`

**Response:** `200 OK`
```json
{
  "timestamp": "2025-10-25T12:00:00.000000Z",
  "symbol": "BTC-USDT",
  "bids": [
    ["49900", "10.5"],
    ["49800", "5.2"],
    ["49700", "8.1"],
    ["49600", "12.3"],
    ["49500", "6.7"]
  ],
  "asks": [
    ["50100", "8.2"],
    ["50200", "4.1"],
    ["50300", "9.5"],
    ["50400", "7.8"],
    ["50500", "11.2"]
  ]
}
```

**Format:**
- Each entry is `[price, quantity]`
- Bids ordered from highest to lowest
- Asks ordered from lowest to highest

---

## WebSocket API

### Order Submission

Submit orders via WebSocket for lower latency.

**Endpoint:** `WS /ws/orders`

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/orders');
```

**Send Message:**
```json
{
  "symbol": "BTC-USDT",
  "order_type": "limit",
  "side": "buy",
  "quantity": "1.5",
  "price": "50000"
}
```

**Receive Response:**
```json
{
  "order_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "filled",
  "filled_quantity": "1.5",
  "remaining_quantity": "0",
  "trades": [...],
  "timestamp": "2025-10-25T12:00:00.000000Z"
}
```

**Error Response:**
```json
{
  "status": "error",
  "error": "Order quantity must be positive",
  "timestamp": "2025-10-25T12:00:00.000000Z"
}
```

---

### Market Data Stream

Subscribe to real-time market data updates.

**Endpoint:** `WS /ws/market-data/{symbol}`

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/market-data/BTC-USDT');
```

**Message Types:**

**BBO Update:**
```json
{
  "type": "bbo",
  "data": {
    "timestamp": "2025-10-25T12:00:00.000000Z",
    "symbol": "BTC-USDT",
    "best_bid": "49900",
    "best_bid_quantity": "10.5",
    "best_ask": "50100",
    "best_ask_quantity": "8.2"
  }
}
```

**Order Book Update:**
```json
{
  "type": "orderbook",
  "data": {
    "timestamp": "2025-10-25T12:00:00.000000Z",
    "symbol": "BTC-USDT",
    "bids": [["49900", "10.5"], ...],
    "asks": [["50100", "8.2"], ...]
  }
}
```

**Keep-Alive:**

Send ping:
```json
{"type": "ping"}
```

Receive pong:
```json
{"type": "pong"}
```

---

### Trade Execution Feed

Subscribe to real-time trade executions.

**Endpoint:** `WS /ws/trades/{symbol}`

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/trades/BTC-USDT');
```

**Receive Trade:**
```json
{
  "timestamp": "2025-10-25T12:00:00.000000Z",
  "symbol": "BTC-USDT",
  "trade_id": "987fcdeb-51a2-43f1-b789-123456789abc",
  "price": "50000",
  "quantity": "1.5",
  "aggressor_side": "buy",
  "maker_order_id": "abc123...",
  "taker_order_id": "def456..."
}
```

**Fields:**
- `aggressor_side`: Side of the incoming (taker) order
- `maker_order_id`: Order that was resting on the book
- `taker_order_id`: Incoming order that initiated the trade

---

## Code Examples

### Python - REST API

```python
import requests

# Submit order
response = requests.post('http://localhost:8000/api/v1/orders', json={
    "symbol": "BTC-USDT",
    "order_type": "limit",
    "side": "buy",
    "quantity": "1.5",
    "price": "50000"
})
result = response.json()
print(f"Order ID: {result['order_id']}")

# Get BBO
response = requests.get('http://localhost:8000/api/v1/bbo/BTC-USDT')
bbo = response.json()
print(f"Spread: {float(bbo['best_ask']) - float(bbo['best_bid'])}")
```

### Python - WebSocket

```python
import asyncio
import websockets
import json

async def trade_feed():
    uri = "ws://localhost:8000/ws/trades/BTC-USDT"
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            trade = json.loads(message)
            print(f"{trade['quantity']} @ {trade['price']}")

asyncio.run(trade_feed())
```

### JavaScript - WebSocket

```javascript
// Market data stream
const ws = new WebSocket('ws://localhost:8000/ws/market-data/BTC-USDT');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'bbo') {
        console.log('BBO:', data.data);
    } else if (data.type === 'orderbook') {
        console.log('Order Book:', data.data);
    }
};

ws.onopen = () => {
    console.log('Connected to market data');
    // Send ping every 30 seconds
    setInterval(() => {
        ws.send(JSON.stringify({type: 'ping'}));
    }, 30000);
};
```

---

## Order Type Behaviors

### Market Order
- Executes immediately at best available price
- Crosses the spread
- Unfilled quantity is cancelled
- No price parameter

### Limit Order
- Executes at specified price or better
- Rests on book if not immediately marketable
- Provides liquidity (maker)
- Requires price parameter

### IOC (Immediate-Or-Cancel)
- Executes immediately at specified price or better
- Unfilled quantity is cancelled
- Does not rest on book
- Requires price parameter

### FOK (Fill-Or-Kill)
- Must fill completely or cancels entirely
- No partial fills
- Does not rest on book
- Requires price parameter

---

## Rate Limits

Currently no rate limits. For production:
- Implement per-IP rate limiting
- Implement per-API-key rate limiting
- WebSocket message throttling

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Order or symbol not found |
| 500 | Internal Server Error |

---

## Best Practices

1. **Use WebSockets for high-frequency trading**
   - Lower latency than REST
   - Persistent connection
   - Real-time updates

2. **Handle disconnections gracefully**
   - Implement reconnection logic
   - Maintain local order state
   - Reconcile on reconnect

3. **Use Decimal types for precision**
   - Avoid floating-point errors
   - Use string representation in JSON

4. **Subscribe to market data before trading**
   - Understand current market state
   - Make informed decisions

5. **Implement proper error handling**
   - Retry transient errors
   - Log all errors
   - Alert on critical failures
