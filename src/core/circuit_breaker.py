"""🔌 Circuit Breaker Pattern - Prevent cascading failures"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Simple circuit breaker for API resilience"""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def record_success(self):
        """Record successful call"""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def record_failure(self):
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
    
    def is_open(self) -> bool:
        """Check if circuit is open"""
        if self.state == 'OPEN':
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = 'HALF_OPEN'
                return False
            return True
        return False

class GradedCircuitBreaker(CircuitBreaker):
    """Advanced circuit breaker with priority levels"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.priority_overrides = {}

class Priority:
    """Priority levels"""
    CRITICAL = 10
    HIGH = 8
    MEDIUM = 5
    LOW = 2
