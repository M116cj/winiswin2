"""
🔄 Shared Memory Ring Buffer (LMAX Disruptor Pattern)
Wrapper class for inter-process communication
"""

import multiprocessing
from multiprocessing import shared_memory
import struct
import logging

logger = logging.getLogger(__name__)

TOTAL_BUFFER_SIZE = 480000  # bytes
SLOT_SIZE = 48  # bytes per candle (8 slots per double)
NUM_SLOTS = TOTAL_BUFFER_SIZE // SLOT_SIZE
METADATA_SIZE = 32  # bytes for write/read cursors


class RingBuffer:
    """Wrapper around shared memory ring buffer"""
    
    def __init__(self, create: bool = False):
        """
        Initialize ring buffer
        
        Args:
            create: If True, create new buffer; if False, attach to existing
        """
        self.shm = None
        self.metadata_shm = None
        
        try:
            if create:
                # Create metadata buffer (write/read cursors)
                self.metadata_shm = shared_memory.SharedMemory(
                    name="ring_buffer_meta",
                    create=True,
                    size=METADATA_SIZE
                )
                # Initialize cursors to 0 (CRITICAL: Reset on startup)
                self.metadata_shm.buf[:] = b'\x00' * METADATA_SIZE
                self._set_cursors(0, 0)  # ✅ Explicit cursor reset
                
                # Create main buffer
                self.shm = shared_memory.SharedMemory(
                    name="ring_buffer",
                    create=True,
                    size=TOTAL_BUFFER_SIZE
                )
                logger.critical(
                    f"🔄 RingBuffer created: {TOTAL_BUFFER_SIZE} bytes, {NUM_SLOTS} slots (Cursors reset to 0)"
                )
            else:
                # Attach to existing metadata
                self.metadata_shm = shared_memory.SharedMemory(name="ring_buffer_meta")
                # Attach to existing main buffer
                self.shm = shared_memory.SharedMemory(name="ring_buffer")
                logger.debug("✅ Attached to existing RingBuffer")
        
        except FileExistsError:
            # If create=True and buffer already exists, attach to it instead
            if create:
                try:
                    self.metadata_shm = shared_memory.SharedMemory(name="ring_buffer_meta")
                    self.shm = shared_memory.SharedMemory(name="ring_buffer")
                    logger.debug("ℹ️ Ring buffer already existed, attached to existing")
                except Exception as e:
                    logger.error(f"Failed to attach to existing ring buffer: {e}")
                    raise
            else:
                raise
        except Exception as e:
            logger.error(f"Failed to initialize ring buffer: {e}", exc_info=True)
            raise
    
    def _get_cursors(self) -> tuple:
        """Read write and read cursors from metadata"""
        try:
            # Read two unsigned longs (write_cursor, read_cursor)
            data = bytes(self.metadata_shm.buf[:16])
            if len(data) < 16:
                return 0, 0
            write_cursor, read_cursor = struct.unpack('QQ', data)
            return write_cursor, read_cursor
        except Exception as e:
            logger.error(f"Error reading cursors: {e}")
            return 0, 0
    
    def _set_cursors(self, write_cursor: int, read_cursor: int):
        """Write write and read cursors to metadata"""
        try:
            data = struct.pack('QQ', write_cursor, read_cursor)
            self.metadata_shm.buf[:16] = data
        except Exception as e:
            logger.error(f"Error writing cursors: {e}")
    
    def pending_count(self) -> int:
        """Get number of pending candles (unread)"""
        try:
            write_cursor, read_cursor = self._get_cursors()
            pending = write_cursor - read_cursor
            if pending < 0:
                pending = 0
            # 🔍 Diagnostic: Log cursor state
            if pending > 0 and not hasattr(self, '_last_pending_log'):
                logger.critical(f"🔍 RingBuffer pending_count: w={write_cursor}, r={read_cursor}, pending={pending}")
                self._last_pending_log = pending
            return pending
        except Exception as e:
            logger.error(f"Error getting pending count: {e}")
            return 0
    
    def read_new(self):
        """Generator to read new candles from buffer"""
        try:
            read_count = 0
            while True:
                write_cursor, read_cursor = self._get_cursors()
                
                if read_cursor >= write_cursor:
                    # No new data
                    if read_count > 0:
                        logger.critical(f"✅ read_new() delivered {read_count} candles (w={write_cursor}, r={read_cursor})")
                    break
                
                # Calculate position in buffer
                slot_index = read_cursor % NUM_SLOTS
                offset = slot_index * SLOT_SIZE
                
                # Read candle (6 doubles = 48 bytes)
                if offset + SLOT_SIZE <= len(self.shm.buf):
                    candle_data = bytes(self.shm.buf[offset:offset + SLOT_SIZE])
                    
                    # Unpack candle tuple (timestamp, open, high, low, close, volume)
                    try:
                        candle = struct.unpack('dddddd', candle_data)
                        yield candle
                        read_count += 1
                        
                        # Increment read cursor - MUST refresh write_cursor!
                        new_write_cursor, _ = self._get_cursors()
                        self._set_cursors(new_write_cursor, read_cursor + 1)
                    except struct.error:
                        logger.error("Failed to unpack candle data")
                        break
                else:
                    break
        
        except Exception as e:
            logger.error(f"Error reading from buffer: {e}")
            yield None
    
    def write_candle(self, candle: tuple):
        """Write candle to buffer (called by Feed process)"""
        try:
            write_cursor, read_cursor = self._get_cursors()
            
            # ✅ OVERRUN PROTECTION: Check if buffer is getting full (leave 10-slot buffer)
            pending = write_cursor - read_cursor
            if pending >= NUM_SLOTS - 10:
                logger.warning(
                    f"⚠️ RingBuffer Overflow! Pending={pending}/{NUM_SLOTS}. "
                    f"Brain lagging behind. Forcing read cursor forward..."
                )
                # Force Brain to skip old data and catch up to halfway point
                new_read_cursor = write_cursor - (NUM_SLOTS // 2)
                self._set_cursors(write_cursor, new_read_cursor)
                read_cursor = new_read_cursor
            
            # Calculate position in buffer
            slot_index = write_cursor % NUM_SLOTS
            offset = slot_index * SLOT_SIZE
            
            # Pack candle (6 doubles = 48 bytes)
            candle_data = struct.pack('dddddd', *candle)
            self.shm.buf[offset:offset + SLOT_SIZE] = candle_data
            
            # Increment write cursor
            self._set_cursors(write_cursor + 1, read_cursor)
        
        except Exception as e:
            logger.error(f"Error writing candle: {e}", exc_info=True)
    
    def close(self):
        """Clean up shared memory"""
        try:
            if self.shm:
                self.shm.close()
            if self.metadata_shm:
                self.metadata_shm.close()
        except Exception as e:
            logger.error(f"Error closing ring buffer: {e}")
    
    def unlink(self):
        """Remove shared memory (cleanup on exit)"""
        try:
            if self.shm:
                self.shm.unlink()
            if self.metadata_shm:
                self.metadata_shm.unlink()
        except Exception as e:
            logger.debug(f"Ring buffer cleanup: {e}")


def get_ring_buffer(create: bool = False) -> RingBuffer:
    """Get or create ring buffer wrapper"""
    try:
        return RingBuffer(create=create)
    except Exception as e:
        logger.error(f"Failed to get ring buffer: {e}", exc_info=True)
        return None
