import logging
import sys
import time
import uuid
from datetime import datetime
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter to ensure ISO-8601 timestamps."""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        # Ensure timestamp is in ISO-8601 format with Z suffix
        if not log_record.get('ts'):
            log_record['ts'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        log_record['level'] = record.levelname


def setup_logging(log_level: str = "INFO"):
    """
    Setup structured JSON logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger = logging.getLogger()
    logger.setLevel(log_level.upper())
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create JSON handler for stdout
    json_handler = logging.StreamHandler(sys.stdout)
    
    # Use custom JSON formatter
    formatter = CustomJsonFormatter(
        '%(ts)s %(level)s %(name)s %(message)s'
    )
    json_handler.setFormatter(formatter)
    
    logger.addHandler(json_handler)
    
    return logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all HTTP requests in structured JSON format.
    
    Required log keys:
    - ts: server time (ISO-8601)
    - level: log level
    - request_id: unique per request
    - method: HTTP method
    - path: request path
    - status: response status code
    - latency_ms: request processing time in milliseconds
    
    For /webhook requests, also includes:
    - message_id: from request body (when present)
    - dup: boolean indicating duplicate message
    - result: processing result (created, duplicate, invalid_signature, validation_error)
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Record start time
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate latency
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        # Build log data
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": latency_ms,
        }
        
        # Add webhook-specific fields if present in request state
        if hasattr(request.state, "webhook_log_data"):
            log_data.update(request.state.webhook_log_data)
        
        # Log the request
        logger = logging.getLogger("app.requests")
        
        if response.status_code >= 500:
            logger.error("Request completed", extra=log_data)
        elif response.status_code >= 400:
            logger.warning("Request completed", extra=log_data)
        else:
            logger.info("Request completed", extra=log_data)
        
        return response


def log_webhook_data(request: Request, message_id: str = None, dup: bool = False, result: str = None):
    """
    Attach webhook-specific logging data to the request state.
    This data will be included in the request log by the middleware.
    
    Args:
        request: FastAPI request object
        message_id: Message ID from the webhook payload
        dup: Whether this is a duplicate message
        result: Processing result (created, duplicate, invalid_signature, validation_error)
    """
    webhook_data = {}
    
    if message_id is not None:
        webhook_data["message_id"] = message_id
    
    if result is not None:
        webhook_data["result"] = result
    
    webhook_data["dup"] = dup
    
    request.state.webhook_log_data = webhook_data
