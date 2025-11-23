"""
🧹 Shared Memory Cleaner - Pre-flight cleanup for stale segments
Ensures fresh RingBuffer initialization on process restart
"""

import logging
from multiprocessing import shared_memory

logger = logging.getLogger(__name__)


def cleanup_segments():
    """
    Clean up stale shared memory segments before starting processes.
    
    Prevents FileExistsError when RingBuffer tries to create new segments
    after an unclean shutdown.
    """
    segments_to_clean = [
        "ring_buffer",
        "ring_buffer_meta"
    ]
    
    cleaned_count = 0
    
    for segment_name in segments_to_clean:
        try:
            # Try to attach to existing segment
            shm = shared_memory.SharedMemory(name=segment_name)
            # If found, unlink it (delete from OS)
            shm.unlink()
            cleaned_count += 1
            logger.info(f"✅ Cleaned stale segment: {segment_name}")
        except FileNotFoundError:
            # Segment doesn't exist - normal case on fresh start
            pass
        except Exception as e:
            logger.debug(f"Note: Could not clean {segment_name}: {e}")
    
    if cleaned_count > 0:
        logger.critical(f"🧹 Cleaned {cleaned_count} stale shared memory segments")
    else:
        logger.debug("✅ No stale segments found - fresh start")
