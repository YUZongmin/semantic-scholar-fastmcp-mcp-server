"""
Main server module for the Semantic Scholar API Server.
"""

import logging
import asyncio
import signal

# Import mcp from centralized location
from .mcp import mcp
from .utils.http import initialize_client, cleanup_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import API modules to register tools
# Note: This must come AFTER mcp is initialized
from .api import papers, authors, recommendations

async def handle_exception(loop, context):
    """Global exception handler for the event loop."""
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception: {msg}")
    asyncio.create_task(shutdown())

async def shutdown():
    """Gracefully shut down the server."""
    logger.info("Initiating graceful shutdown...")
    
    # Cancel all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    # Cleanup resources
    await cleanup_client()
    await mcp.cleanup()
    
    logger.info(f"Cancelled {len(tasks)} tasks")
    logger.info("Shutdown complete")

def init_signal_handlers(loop):
    """Initialize signal handlers for graceful shutdown."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    logger.info("Signal handlers initialized")

async def run_server():
    """Run the server with proper async context management."""
    async with mcp:
        try:
            # Initialize HTTP client
            await initialize_client()
            
            # Start the server
            logger.info("Starting Semantic Scholar Server")
            await mcp.run_async()
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
        finally:
            await shutdown()

def main():
    """Main entry point for the server."""
    try:
        # Set up event loop with exception handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(handle_exception)
        
        # Initialize signal handlers
        init_signal_handlers(loop)
        
        # Run the server
        loop.run_until_complete(run_server())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        try:
            loop.run_until_complete(asyncio.sleep(0))  # Let pending tasks complete
            loop.close()
        except Exception as e:
            logger.error(f"Error during final cleanup: {str(e)}")
        logger.info("Server stopped")

if __name__ == "__main__":
    main() 