import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

logger = logging.getLogger(__name__)

class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        process_time = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
        
        # Latency monitoring for p95 < 500ms targets
        if process_time > 500:
            logger.warning(
                f"Latency Target Exceeded: {request.method} {request.url.path} "
                f"({process_time:.2f}ms)"
            )
        else:
            logger.debug(
                f"Request: {request.method} {request.url.path} "
                f"took {process_time:.2f}ms"
            )
            
        return response
