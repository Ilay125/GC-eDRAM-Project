from gem5.components.boards.abstract_board import AbstractBoard
from gem5.components.cachehierarchies.classic.abstract_classic_cache_hierarchy import AbstractClassicCacheHierarchy
from gem5.components.cachehierarchies.classic.caches.l1dcache import L1DCache
from gem5.components.cachehierarchies.classic.caches.l1icache import L1ICache
from gem5.components.cachehierarchies.classic.caches.l2cache import L2Cache

from m5.objects import BadAddr, SystemXBar, NULL, L2XBar
from m5.proxy import Parent


class ForgettingCacheBlock(L1DCache):
    def __init__(self, size, assoc, drt, debug_drt_mode, top_mru, refresh_dirty_daemon):
        super().__init__(size=size, assoc=assoc)
        self.drt = drt
        self.debug_drt_mode = debug_drt_mode
        self.top_mru = top_mru
        self.refresh_dirty_daemon = refresh_dirty_daemon

class ForgettingCache(AbstractClassicCacheHierarchy):
    def __init__(self, l1d_size, l1d_assoc, l1i_size, l1i_assoc, l2d_size, l2d_assoc,
                        drt, debug_drt_mode, top_mru, refresh_dirty_daemon):
        super().__init__()
        self._l1d_size = l1d_size
        self._l1d_assoc = l1d_assoc
        self._l1i_size = l1i_size
        self._l1i_assoc = l1i_assoc

        self._l2d_size = l2d_size
        self._l2d_assoc = l2d_assoc

        self._drt = drt
        self._debug_drt_mode = debug_drt_mode
        self._top_mru = top_mru
        self._refresh_dirty_daemon = refresh_dirty_daemon
        
        self.membus = SystemXBar(width=128) 
        self.membus.badaddr_responder = BadAddr()
        self.membus.default = self.membus.badaddr_responder.pio

        self.l2bus = L2XBar(width=128)

    def get_mem_side_port(self):
        return self.membus.mem_side_ports

    def get_cpu_side_port(self):
        return self.membus.cpu_side_ports

    def incorporate_cache(self, board: AbstractBoard):
        board.connect_system_port(self.membus.cpu_side_ports)

        for cntr in board.get_memory().get_memory_controllers():
            cntr.port = self.membus.mem_side_ports

        # Create the caches
        self.l1icache = L1ICache(size=self._l1i_size, assoc=self._l1i_assoc)

        self.l1dcache = ForgettingCacheBlock(
            size=self._l1d_size,
            assoc=self._l1d_assoc,
            drt=self._drt,
            debug_drt_mode=self._debug_drt_mode,
            top_mru = self._top_mru,
            refresh_dirty_daemon = self._refresh_dirty_daemon
        )

        print("L1D cache drt:", self.l1dcache.drt)
        print("L1I cache drt:", self.l1icache.drt)

        self.l2cache = L2Cache(size=self._l2d_size, assoc=self._l2d_assoc)

        # Disables prefetchers
        self.l1icache.prefetcher = NULL
        self.l1dcache.prefetcher = NULL
        self.l2cache.prefetcher = NULL

        # Loop through cores and connect
        for i, cpu in enumerate(board.get_processor().get_cores()):
            # Connect CPU to Caches
            cpu.connect_icache(self.l1icache.cpu_side)
            cpu.connect_dcache(self.l1dcache.cpu_side)

            # Connect Interrupts 
            cpu.connect_interrupt(self.membus.mem_side_ports, self.membus.cpu_side_ports)
        
        # Connect L1 to L2
        self.l1dcache.mem_side = self.l2bus.cpu_side_ports
        self.l1icache.mem_side = self.l2bus.cpu_side_ports

        # Connect L2 Bus to Cache
        self.l2cache.cpu_side = self.l2bus.mem_side_ports

        # Connect L2 to membus
        self.l2cache.mem_side = self.membus.cpu_side_ports
