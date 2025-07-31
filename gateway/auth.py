"""
Authentication and Security Module for Unified MCP Gateway

Provides:
- API key authentication
- Rate limiting
- CORS handling
- Security middleware
- User management
"""

import time
import hashlib
import secrets
from typing import Dict, Optional, Tuple, List
from collections import defaultdict, deque
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Token bucket rate limiter implementation."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, client_id: str) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed for client.
        
        Args:
            client_id: Unique identifier for the client
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        client_requests = self.requests[client_id]
        while client_requests and client_requests[0] < window_start:
            client_requests.popleft()
        
        # Check if under limit
        current_requests = len(client_requests)
        is_allowed = current_requests < self.max_requests
        
        if is_allowed:
            client_requests.append(now)
        
        rate_limit_info = {
            "limit": self.max_requests,
            "remaining": max(0, self.max_requests - current_requests - (1 if is_allowed else 0)),
            "reset": int(window_start + self.window_seconds),
            "window": self.window_seconds
        }
        
        return is_allowed, rate_limit_info

class APIKeyManager:
    """Manages API keys and user authentication."""
    
    def __init__(self):
        self.api_keys: Dict[str, Dict[str, any]] = {}
        self.key_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    def generate_api_key(self, user_id: str, permissions: List[str] = None) -> str:
        """
        Generate a new API key for a user.
        
        Args:
            user_id: Unique user identifier
            permissions: List of permissions for this key
            
        Returns:
            Generated API key
        """
        api_key = f"mcp_{secrets.token_urlsafe(32)}"
        
        self.api_keys[api_key] = {
            "user_id": user_id,
            "permissions": permissions or ["read", "write"],
            "created_at": time.time(),
            "last_used": None,
            "usage_count": 0,
            "enabled": True
        }
        
        logger.info(f"Generated API key for user: {user_id}")
        return api_key
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, any]]:
        """
        Validate an API key and return user info.
        
        Args:
            api_key: API key to validate
            
        Returns:
            User info dict if valid, None otherwise
        """
        if not api_key or api_key not in self.api_keys:
            return None
        
        key_info = self.api_keys[api_key]
        if not key_info.get("enabled", False):
            return None
        
        # Update usage statistics
        key_info["last_used"] = time.time()
        key_info["usage_count"] += 1
        
        return key_info
    
    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke
            
        Returns:
            True if revoked, False if key not found
        """
        if api_key in self.api_keys:
            self.api_keys[api_key]["enabled"] = False
            logger.info(f"Revoked API key: {api_key[:10]}...")
            return True
        return False
    
    def list_keys_for_user(self, user_id: str) -> List[Dict[str, any]]:
        """
        List all API keys for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of API key info (without the actual key)
        """
        user_keys = []
        for api_key, key_info in self.api_keys.items():
            if key_info["user_id"] == user_id:
                safe_info = key_info.copy()
                safe_info["api_key_preview"] = api_key[:10] + "..."
                user_keys.append(safe_info)
        
        return user_keys

class SecurityMiddleware:
    """Security middleware for the MCP Gateway."""
    
    def __init__(self, api_key: Optional[str] = None, rate_limit: int = 100):
        self.required_api_key = api_key
        self.rate_limiter = RateLimiter(max_requests=rate_limit)
        self.api_key_manager = APIKeyManager()
        self.security = HTTPBearer(auto_error=False) if api_key else None
        
        # Generate a default admin key if API key authentication is enabled
        if self.required_api_key:
            admin_key = self.api_key_manager.generate_api_key(
                "admin", 
                ["read", "write", "admin"]
            )
            logger.info(f"Admin API key generated: {admin_key}")
    
    def get_client_id(self, request: Request) -> str:
        """
        Get unique client identifier from request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Unique client identifier
        """
        # Use API key if available, otherwise fall back to IP
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
            return f"key_{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
        
        # Use IP address with X-Forwarded-For support
        client_ip = request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip_{client_ip}"
    
    async def authenticate(
        self, 
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> Optional[Dict[str, any]]:
        """
        Authenticate request and return user info.
        
        Args:
            request: FastAPI request object
            credentials: HTTP authorization credentials
            
        Returns:
            User info if authenticated, None if no auth required
            
        Raises:
            HTTPException: If authentication fails
        """
        # If no API key is required, allow all requests
        if not self.required_api_key:
            return {"user_id": "anonymous", "permissions": ["read", "write"]}
        
        # Check for API key
        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=401,
                detail="API key required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Validate API key
        user_info = self.api_key_manager.validate_api_key(credentials.credentials)
        if not user_info:
            raise HTTPException(
                status_code=401,
                detail="Invalid or revoked API key",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return user_info
    
    async def check_rate_limit(self, request: Request) -> Dict[str, int]:
        """
        Check rate limit for request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Rate limit info
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        client_id = self.get_client_id(request)
        is_allowed, rate_info = self.rate_limiter.is_allowed(client_id)
        
        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_info["reset"]),
                    "Retry-After": str(rate_info["window"])
                }
            )
        
        return rate_info
    
    def create_auth_dependency(self):
        """Create FastAPI dependency for authentication."""
        
        async def auth_dependency(
            request: Request,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security) if self.security else None
        ):
            # Check rate limit first
            rate_info = await self.check_rate_limit(request)
            
            # Then authenticate
            user_info = await self.authenticate(request, credentials)
            
            return {
                "user": user_info,
                "rate_limit": rate_info
            }
        
        return auth_dependency

def setup_cors_middleware(app, cors_origins: List[str]):
    """
    Setup CORS middleware for the application.
    
    Args:
        app: FastAPI application instance
        cors_origins: List of allowed CORS origins
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    logger.info(f"CORS middleware configured with origins: {cors_origins}")

def create_security_headers_middleware():
    """Create middleware for adding security headers."""
    
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response
    
    return security_headers_middleware