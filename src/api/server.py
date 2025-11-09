"""
FastAPI application for the matching engine.
Provides REST and WebSocket APIs for order submission and market data.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
import asyncio
import json
import logging

from ..models.orders import Order, OrderType, OrderSide, Trade
from ..matching_engine.engine import MatchingEngine

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Cryptocurrency Matching Engine",
    description="High-performance matching engine with REG NMS-inspired principles",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize matching engine
engine = MatchingEngine()


class OrderRequest(BaseModel):
    """Request model for order submission."""
    symbol: str = Field(..., description="Trading pair (e.g., BTC-USDT)")
    order_type: OrderType = Field(..., description="Order type")
    side: OrderSide = Field(..., description="Buy or sell")
    quantity: str = Field(..., description="Order quantity as decimal string")
    price: Optional[str] = Field(None, description="Limit price (required for limit orders)")


class OrderResponse(BaseModel):
    """Response model for order submission."""
    order_id: str
    status: str
    filled_quantity: str
    remaining_quantity: str
    trades: List[dict]
    timestamp: str


class CancelRequest(BaseModel):
    """Request model for order cancellation."""
    symbol: str
    order_id: str


# WebSocket connection managers
class ConnectionManager:
    """Manages WebSocket connections for different data streams."""
    
    def __init__(self):
        self.market_data_connections: dict[str, List[WebSocket]] = {}
        self.trade_connections: dict[str, List[WebSocket]] = {}
        self.lock = asyncio.Lock()
    
    async def connect_market_data(self, websocket: WebSocket, symbol: str):
        """Connect a client to market data stream."""
        await websocket.accept()
        async with self.lock:
            if symbol not in self.market_data_connections:
                self.market_data_connections[symbol] = []
            self.market_data_connections[symbol].append(websocket)
        logger.info(f"Client connected to market data for {symbol}")
    
    async def connect_trade_feed(self, websocket: WebSocket, symbol: str):
        """Connect a client to trade feed."""
        await websocket.accept()
        async with self.lock:
            if symbol not in self.trade_connections:
                self.trade_connections[symbol] = []
            self.trade_connections[symbol].append(websocket)
        logger.info(f"Client connected to trade feed for {symbol}")
    
    async def disconnect(self, websocket: WebSocket, symbol: str, stream_type: str):
        """Disconnect a client."""
        async with self.lock:
            if stream_type == "market_data" and symbol in self.market_data_connections:
                if websocket in self.market_data_connections[symbol]:
                    self.market_data_connections[symbol].remove(websocket)
            elif stream_type == "trade" and symbol in self.trade_connections:
                if websocket in self.trade_connections[symbol]:
                    self.trade_connections[symbol].remove(websocket)
        logger.info(f"Client disconnected from {stream_type} for {symbol}")
    
    async def broadcast_market_data(self, symbol: str, data: dict):
        """Broadcast market data update to all connected clients."""
        if symbol in self.market_data_connections:
            dead_connections = []
            for connection in self.market_data_connections[symbol]:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error sending market data: {e}")
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for conn in dead_connections:
                if conn in self.market_data_connections[symbol]:
                    self.market_data_connections[symbol].remove(conn)
    
    async def broadcast_trade(self, symbol: str, trade: dict):
        """Broadcast trade execution to all connected clients."""
        if symbol in self.trade_connections:
            dead_connections = []
            for connection in self.trade_connections[symbol]:
                try:
                    await connection.send_json(trade)
                except Exception as e:
                    logger.error(f"Error sending trade: {e}")
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for conn in dead_connections:
                if conn in self.trade_connections[symbol]:
                    self.trade_connections[symbol].remove(conn)


manager = ConnectionManager()


# Event handlers for matching engine
def on_trade_executed(trade: Trade):
    """Handle trade execution event."""
    asyncio.create_task(manager.broadcast_trade(trade.symbol, trade.to_dict()))


def on_bbo_updated(symbol: str):
    """Handle BBO update event."""
    bbo = engine.get_bbo(symbol)
    if bbo:
        asyncio.create_task(manager.broadcast_market_data(symbol, {
            "type": "bbo",
            "data": bbo
        }))
    
    # Also send order book snapshot
    snapshot = engine.get_order_book_snapshot(symbol, depth=10)
    if snapshot:
        asyncio.create_task(manager.broadcast_market_data(symbol, {
            "type": "orderbook",
            "data": snapshot
        }))


# Register callbacks
engine.register_trade_callback(on_trade_executed)
engine.register_bbo_callback(on_bbo_updated)


# REST API Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Cryptocurrency Matching Engine",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/api/v1/orders", response_model=OrderResponse)
async def submit_order(order_request: OrderRequest):
    """
    Submit a new order to the matching engine.
    
    - **symbol**: Trading pair (e.g., BTC-USDT)
    - **order_type**: market, limit, ioc, or fok
    - **side**: buy or sell
    - **quantity**: Order quantity
    - **price**: Limit price (required for non-market orders)
    """
    try:
        # Create order object
        order = Order(
            symbol=order_request.symbol,
            order_type=order_request.order_type,
            side=order_request.side,
            quantity=Decimal(order_request.quantity),
            price=Decimal(order_request.price) if order_request.price else None,
        )
        
        # Submit to engine
        result = engine.submit_order(order)
        
        return OrderResponse(**result)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/v1/orders/cancel")
async def cancel_order(cancel_request: CancelRequest):
    """
    Cancel an existing order.
    
    - **symbol**: Trading pair
    - **order_id**: ID of the order to cancel
    """
    result = engine.cancel_order(cancel_request.symbol, cancel_request.order_id)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))
    
    return result


@app.get("/api/v1/bbo/{symbol}")
async def get_bbo(symbol: str):
    """
    Get current Best Bid and Offer for a symbol.
    
    - **symbol**: Trading pair
    """
    bbo = engine.get_bbo(symbol)
    
    if bbo is None:
        raise HTTPException(status_code=404, detail=f"No order book for {symbol}")
    
    return bbo


@app.get("/api/v1/orderbook/{symbol}")
async def get_order_book(symbol: str, depth: int = 10):
    """
    Get L2 order book snapshot.
    
    - **symbol**: Trading pair
    - **depth**: Number of price levels per side (default: 10)
    """
    snapshot = engine.get_order_book_snapshot(symbol, depth)
    
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No order book for {symbol}")
    
    return snapshot


# WebSocket Endpoints
@app.websocket("/ws/market-data/{symbol}")
async def market_data_websocket(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time market data (BBO and order book updates).
    
    Streams:
    - BBO updates
    - L2 order book snapshots
    """
    await manager.connect_market_data(websocket, symbol)
    
    try:
        # Send initial snapshot
        bbo = engine.get_bbo(symbol)
        if bbo:
            await websocket.send_json({"type": "bbo", "data": bbo})
        
        snapshot = engine.get_order_book_snapshot(symbol, depth=10)
        if snapshot:
            await websocket.send_json({"type": "orderbook", "data": snapshot})
        
        # Keep connection alive and handle incoming messages
        while True:
            # Wait for messages (can be used for subscription management)
            data = await websocket.receive_text()
            
            # Echo received message (can be extended for commands)
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket, symbol, "market_data")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await manager.disconnect(websocket, symbol, "market_data")


@app.websocket("/ws/trades/{symbol}")
async def trade_feed_websocket(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time trade execution feed.
    
    Streams trade execution reports as they occur.
    """
    await manager.connect_trade_feed(websocket, symbol)
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            
            # Handle ping/pong
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket, symbol, "trade")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await manager.disconnect(websocket, symbol, "trade")


@app.websocket("/ws/orders")
async def order_submission_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for order submission.
    
    Accepts order submission messages and returns execution results.
    """
    await websocket.accept()
    logger.info("Client connected to order submission WebSocket")
    
    try:
        while True:
            # Receive order
            data = await websocket.receive_text()
            message = json.loads(data)
            
            try:
                # Parse order request
                order_request = OrderRequest(**message)
                
                # Create order
                order = Order(
                    symbol=order_request.symbol,
                    order_type=order_request.order_type,
                    side=order_request.side,
                    quantity=Decimal(order_request.quantity),
                    price=Decimal(order_request.price) if order_request.price else None,
                )
                
                # Submit to engine
                result = engine.submit_order(order)
                
                # Send response
                await websocket.send_json(result)
            
            except Exception as e:
                await websocket.send_json({
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
    
    except WebSocketDisconnect:
        logger.info("Client disconnected from order submission WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
