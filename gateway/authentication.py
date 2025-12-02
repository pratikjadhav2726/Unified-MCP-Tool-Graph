"""
Authentication module for SaaS MCP Server.

Handles JWT and API key authentication for multi-tenant MCP server.
"""

import os
import jwt
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger("Authentication")


class AuthenticationError(Exception):
    """Authentication-related errors."""
    pass


class TokenValidator:
    """Validates JWT tokens and API keys."""
    
    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret
        self.token_cache = {}  # In production, use Redis
    
    def validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token and extract tenant/user info.
        
        Args:
            token: JWT token string
            
        Returns:
            Dictionary with tenant_id, user_id, and permissions if valid
            None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"]
            )
            
            # Check if token is blacklisted (in production, check database)
            if self.is_token_blacklisted(token):
                logger.warning("Token is blacklisted")
                return None
            
            return {
                "tenant_id": payload.get("tenant_id"),
                "user_id": payload.get("user_id"),
                "permissions": payload.get("permissions", []),
                "auth_method": "jwt",
                "expires_at": datetime.fromtimestamp(payload.get("exp", 0))
            }
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
    
    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate API key and return tenant info.
        
        Args:
            api_key: API key string
            
        Returns:
            Dictionary with tenant_id and permissions if valid
            None if invalid
        """
        # Hash the API key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Look up in database (placeholder - implement actual DB lookup)
        tenant_info = await self.get_tenant_by_api_key(key_hash)
        if not tenant_info:
            return None
        
        # Check if key is active
        if not tenant_info.get("is_active", False):
            logger.warning(f"API key is not active for tenant {tenant_info.get('tenant_id')}")
            return None
        
        # Update last used timestamp
        await self.update_api_key_last_used(key_hash)
        
        return {
            "tenant_id": tenant_info["tenant_id"],
            "api_key_id": tenant_info.get("api_key_id"),
            "permissions": tenant_info.get("permissions", []),
            "auth_method": "api_key"
        }
    
    async def get_tenant_by_api_key(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant info by API key hash.
        
        In production, this would query the database.
        """
        # TODO: Implement database lookup
        # Example:
        # async with db_pool.acquire() as conn:
        #     row = await conn.fetchrow(
        #         "SELECT tenant_id, api_key_id, is_active FROM api_keys WHERE key_hash = $1",
        #         key_hash
        #     )
        #     return dict(row) if row else None
        return None
    
    async def update_api_key_last_used(self, key_hash: str):
        """Update last used timestamp for API key."""
        # TODO: Implement database update
        pass
    
    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        # In production, check database or Redis
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token_hash in self.token_cache.get("blacklist", set())
    
    def blacklist_token(self, token: str):
        """Add token to blacklist."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if "blacklist" not in self.token_cache:
            self.token_cache["blacklist"] = set()
        self.token_cache["blacklist"].add(token_hash)


class AuthenticationMiddleware:
    """Middleware for handling authentication in MCP server."""
    
    def __init__(self, jwt_secret: Optional[str] = None):
        self.jwt_secret = jwt_secret or os.getenv("JWT_SECRET", "change-me-in-production")
        self.validator = TokenValidator(self.jwt_secret)
        self.tenant_contexts: Dict[str, Dict[str, Any]] = {}  # connection_id -> tenant_info
    
    def extract_token_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extract authentication token from headers.
        
        Supports:
        - Authorization: Bearer {token}
        - X-API-Key: {api_key}
        """
        # Try Authorization header
        auth_header = headers.get("Authorization") or headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        
        # Try API key header
        api_key = headers.get("X-API-Key") or headers.get("x-api-key")
        if api_key:
            return api_key
        
        return None
    
    def extract_token_from_query(self, query_params: Dict[str, str]) -> Optional[str]:
        """Extract token from query parameters."""
        return query_params.get("token") or query_params.get("api_key")
    
    async def authenticate(
        self,
        token: str,
        connection_id: str
    ) -> Dict[str, Any]:
        """
        Authenticate a connection using token.
        
        Args:
            token: JWT token or API key
            connection_id: Unique connection identifier
            
        Returns:
            Tenant info dictionary
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Try JWT first
        tenant_info = self.validator.validate_jwt_token(token)
        if tenant_info:
            self.tenant_contexts[connection_id] = tenant_info
            return tenant_info
        
        # Try API key
        tenant_info = await self.validator.validate_api_key(token)
        if tenant_info:
            self.tenant_contexts[connection_id] = tenant_info
            return tenant_info
        
        raise AuthenticationError("Invalid authentication token")
    
    def get_tenant_context(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant context for a connection."""
        return self.tenant_contexts.get(connection_id)
    
    def require_auth(self, func):
        """Decorator to require authentication for tool calls."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get connection ID from context
            # This depends on how FastMCP exposes connection context
            connection_id = self._get_connection_id_from_context()
            
            tenant_info = self.tenant_contexts.get(connection_id)
            if not tenant_info:
                raise AuthenticationError("Authentication required")
            
            # Add tenant context to kwargs
            kwargs["tenant_id"] = tenant_info["tenant_id"]
            kwargs["user_id"] = tenant_info.get("user_id")
            kwargs["permissions"] = tenant_info.get("permissions", [])
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    def _get_connection_id_from_context(self) -> str:
        """Get connection ID from current context."""
        # This is a placeholder - actual implementation depends on FastMCP
        # In production, this would extract from request context
        return "default"  # TODO: Implement proper connection ID extraction


def generate_jwt_token(
    tenant_id: str,
    user_id: Optional[str] = None,
    permissions: Optional[list] = None,
    expires_hours: int = 24,
    jwt_secret: Optional[str] = None
) -> str:
    """
    Generate JWT token for tenant/user.
    
    Args:
        tenant_id: Tenant identifier
        user_id: Optional user identifier
        permissions: Optional list of permissions
        expires_hours: Token expiration in hours
        jwt_secret: JWT secret (defaults to env var)
        
    Returns:
        JWT token string
    """
    secret = jwt_secret or os.getenv("JWT_SECRET", "change-me-in-production")
    
    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "permissions": permissions or [],
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expires_hours)
    }
    
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


def generate_api_key() -> tuple[str, str]:
    """
    Generate API key and its hash.
    
    Returns:
        Tuple of (api_key, key_hash)
        Store key_hash in database, return api_key to user
    """
    import secrets
    
    # Generate random key
    api_key = f"mcp_{secrets.token_urlsafe(32)}"
    
    # Hash for storage
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    return api_key, key_hash

