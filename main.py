"""
Main entry point for running the matching engine server.
Configures logging and starts the FastAPI application.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('matching_engine.log')
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Start the matching engine server."""
    import uvicorn
    
    logger.info("Starting Cryptocurrency Matching Engine...")
    logger.info("Documentation available at: http://localhost:8000/docs")
    logger.info("WebSocket endpoints:")
    logger.info("  - Order submission: ws://localhost:8000/ws/orders")
    logger.info("  - Market data: ws://localhost:8000/ws/market-data/{symbol}")
    logger.info("  - Trade feed: ws://localhost:8000/ws/trades/{symbol}")
    
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )


if __name__ == "__main__":
    main()
