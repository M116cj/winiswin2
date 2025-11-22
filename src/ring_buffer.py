"""
🔄 Shared Memory Ring Buffer - LMAX Disruptor Pattern
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Zero-lock inter-process communication between Feed and Brain processes.
Single-writer/single-reader design using struct packing for speed.

Structure:
- Buffer: 10,000 slots × 6 floats (48 bytes) = ~480KB (fits L2 cache)
- Cursors: write_cursor, read_cursor (separate tiny SharedMemory)
- Thread/process-safe: No locks needed (single writer, single reader)
"""

import logging
import struct
from multiprocessing import shared_memory
from typing import Optional, Iterator, Tuple
import atexit

logger = logging.getLogger(__name__)

# Constants
BUFFER_SLOTS = 10000
FLOATS_PER_SLOT = 6  # timestamp, open, high, low, close, volume
BYTES_PER_SLOT = FLOATS_PER_SLOT * 8  # 6 * 8 = 48 bytes (float64)
TOTAL_BUFFER_SIZE = BUFFER_SLOTS * BYTES_PER_SLOT  # ~480KB

# Struct format: 6 double (float64) values
SLOT_FORMAT = '6d'  # d = double (float64)
SLOT_SIZE = struct.calcsize(SLOT_FORMAT)

# Shared memory names
BUFFER_NAME = 'aeg_candle_buffer'
CURSOR_NAME = 'aeg_cursors'


class RingBuffer:
    """
    Shared memory ring buffer for zero-lock IPC.
    Single writer, single reader. No mutexes needed.
    """
    
    def __init__(self, create: bool = True):
        """
        Initialize ring buffer
        
        Args:
            create: If True, create new buffer. If False, attach to existing.
        """
        self.create_mode = create
        self.buffer_mem: Optional[shared_memory.SharedMemory] = None
        self.cursor_mem: Optional[shared_memory.SharedMemory] = None
        self.write_cursor_offset = 0  # Offset 0: write_cursor
        self.read_cursor_offset = 8   # Offset 8: read_cursor
        
        try:
            if create:
                # Create new buffers
                self._create_buffers()
                logger.info(f"🔄 RingBuffer created: {TOTAL_BUFFER_SIZE} bytes, {BUFFER_SLOTS} slots")
            else:
                # Attach to existing buffers
                self._attach_buffers()
                logger.info(f"🔄 RingBuffer attached: {TOTAL_BUFFER_SIZE} bytes, {BUFFER_SLOTS} slots")
        except Exception as e:
            logger.error(f"❌ RingBuffer init error: {e}")
            raise
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
    
    def _create_buffers(self) -> None:
        """Create new shared memory blocks"""
        try:
            # Unlink old buffers if they exist
            try:
                shared_memory.SharedMemory(name=BUFFER_NAME).unlink()
            except FileNotFoundError:
                pass
            try:
                shared_memory.SharedMemory(name=CURSOR_NAME).unlink()
            except FileNotFoundError:
                pass
        except Exception:
            pass
        
        # Create candle buffer (480KB)
        self.buffer_mem = shared_memory.SharedMemory(
            name=BUFFER_NAME,
            create=True,
            size=TOTAL_BUFFER_SIZE
        )
        
        # Create cursor buffer (16 bytes: 2 × uint64)
        self.cursor_mem = shared_memory.SharedMemory(
            name=CURSOR_NAME,
            create=True,
            size=16
        )
        
        # Initialize cursors to 0
        self._write_cursor(0)
        self._write_read_cursor(0)
    
    def _attach_buffers(self) -> None:
        """Attach to existing shared memory blocks"""
        self.buffer_mem = shared_memory.SharedMemory(name=BUFFER_NAME)
        self.cursor_mem = shared_memory.SharedMemory(name=CURSOR_NAME)
    
    def _write_cursor(self, value: int) -> None:
        """Write to write_cursor (offset 0)"""
        if self.cursor_mem:
            self.cursor_mem.buf[self.write_cursor_offset:self.write_cursor_offset+8] = struct.pack('Q', value)
    
    def _read_cursor_value(self) -> int:
        """Read write_cursor value"""
        if self.cursor_mem:
            return struct.unpack_from('Q', self.cursor_mem.buf, self.write_cursor_offset)[0]
        return 0
    
    def _write_read_cursor(self, value: int) -> None:
        """Write to read_cursor (offset 8)"""
        if self.cursor_mem:
            self.cursor_mem.buf[self.read_cursor_offset:self.read_cursor_offset+8] = struct.pack('Q', value)
    
    def _read_read_cursor_value(self) -> int:
        """Read read_cursor value"""
        if self.cursor_mem:
            return struct.unpack_from('Q', self.cursor_mem.buf, self.read_cursor_offset)[0]
        return 0
    
    def write(self, candle: Tuple[float, float, float, float, float, float]) -> None:
        """
        Write candle to buffer (WRITER ONLY)
        
        Args:
            candle: (timestamp, open, high, low, close, volume)
        """
        cursor = self._read_cursor_value()
        slot_index = cursor % BUFFER_SLOTS
        offset = slot_index * BYTES_PER_SLOT
        
        # Pack candle tuple into struct format
        packed = struct.pack(SLOT_FORMAT, *candle)
        
        # Write to buffer
        if self.buffer_mem:
            self.buffer_mem.buf[offset:offset+SLOT_SIZE] = packed
        
        # Increment write cursor
        self._write_cursor(cursor + 1)
    
    def read_new(self) -> Iterator[Optional[Tuple[float, float, float, float, float, float]]]:
        """
        Read new candles from buffer (READER ONLY)
        Generator that yields candles since last read
        """
        read_cursor = self._read_read_cursor_value()
        
        while True:
            write_cursor = self._read_cursor_value()
            
            if read_cursor >= write_cursor:
                # No new data
                yield None
            else:
                # Read next slot
                slot_index = read_cursor % BUFFER_SLOTS
                offset = slot_index * BYTES_PER_SLOT
                
                # Unpack from buffer
                if self.buffer_mem:
                    candle = struct.unpack_from(SLOT_FORMAT, self.buffer_mem.buf, offset)
                else:
                    yield None
                    continue
                
                # Update read cursor
                read_cursor += 1
                self._write_read_cursor(read_cursor)
                
                yield candle
    
    def pending_count(self) -> int:
        """Get number of pending candles to read"""
        write_cursor = self._read_cursor_value()
        read_cursor = self._read_read_cursor_value()
        return write_cursor - read_cursor
    
    def cleanup(self) -> None:
        """Cleanup shared memory on exit"""
        if self.buffer_mem:
            try:
                self.buffer_mem.close()
                if self.create_mode:
                    self.buffer_mem.unlink()
            except Exception as e:
                logger.warning(f"Error closing buffer: {e}")
        
        if self.cursor_mem:
            try:
                self.cursor_mem.close()
                if self.create_mode:
                    self.cursor_mem.unlink()
            except Exception as e:
                logger.warning(f"Error closing cursors: {e}")


# Global instance
_ring_buffer: Optional[RingBuffer] = None


def get_ring_buffer(create: bool = True) -> RingBuffer:
    """Get or create global ring buffer instance"""
    global _ring_buffer
    if _ring_buffer is None:
        _ring_buffer = RingBuffer(create=create)
    return _ring_buffer
