from gem5.components.boards.abstract_board import AbstractBoard
from gem5.components.cachehierarchies.classic.abstract_classic_cache_hierarchy import AbstractClassicCacheHierarchy
from gem5.components.cachehierarchies.classic.caches.l1dcache import L1DCache
from gem5.components.cachehierarchies.classic.caches.l1icache import L1ICache

from m5.proxy import Parent
from m5.objects import BadAddr, SystemXBar, NULL, BaseSetAssoc, ModuloTaggedSetAssociative


class ModuloL1DCache(L1DCache):
    tags = BaseSetAssoc(
        size=Parent.size,
        assoc=Parent.assoc,
        indexing_policy=ModuloTaggedSetAssociative()
    )

class SimpleL1Cache(AbstractClassicCacheHierarchy):
    def __init__(self, l1d_size, l1d_assoc, l1i_size, l1i_assoc, idx_policy):
        super().__init__()
        self._l1d_size = l1d_size
        self._l1d_assoc = l1d_assoc
        self._l1i_size = l1i_size
        self._l1i_assoc = l1i_assoc
        self._idx_policy = idx_policy
        
        self.membus = SystemXBar(width=64)
        self.membus.badaddr_responder = BadAddr()
        self.membus.default = self.membus.badaddr_responder.pio

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

        # Check for indexing policy and cread dCache accodingaly
        if self._idx_policy == "modulo":
            # Create the data cache with the custom indexing policy from the start
            self.l1dcache = ModuloL1DCache(
                size=self._l1d_size,
                assoc=self._l1d_assoc
            )
        else:
            self.l1dcache = L1DCache(size=self._l1d_size, assoc=self._l1d_assoc)

        # Disables prefetchers
        self.l1icache.prefetcher = NULL
        self.l1dcache.prefetcher = NULL

        

        # Loop through cores and connect
        for i, cpu in enumerate(board.get_processor().get_cores()):
            # Connect CPU to Caches
            cpu.connect_icache(self.l1icache.cpu_side)
            cpu.connect_dcache(self.l1dcache.cpu_side)

            # Connect Caches to Bus
            self.l1icache.mem_side = self.membus.cpu_side_ports
            self.l1dcache.mem_side = self.membus.cpu_side_ports

            # Connect Interrupts 
            cpu.connect_interrupt(self.membus.mem_side_ports, self.membus.cpu_side_ports)