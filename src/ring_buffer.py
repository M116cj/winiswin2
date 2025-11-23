"""
🔄 Shared Memory Ring Buffer (LMAX Disruptor Pattern)
Minimal version for IPC between processes
"""

import multiprocessing
from multiprocessing import shared_memory
import numpy as np

TOTAL_BUFFER_SIZE = 480000  # bytes
SLOT_SIZE = 48  # bytes per candle
NUM_SLOTS = TOTAL_BUFFER_SIZE // SLOT_SIZE


def get_ring_buffer(create: bool = False):
    """Get or create shared memory ring buffer"""
    try:
        if create:
            buffer = shared_memory.SharedMemory(
                name="ring_buffer", 
                create=True,
                size=TOTAL_BUFFER_SIZE
            )
            import logging
            logging.getLogger(__name__).info(
                f"🔄 RingBuffer created: {TOTAL_BUFFER_SIZE} bytes, {NUM_SLOTS} slots"
            )
            return buffer
        else:
            buffer = shared_memory.SharedMemory(name="ring_buffer")
            return buffer
    except:
        # Fallback if shared memory not available
        return None
