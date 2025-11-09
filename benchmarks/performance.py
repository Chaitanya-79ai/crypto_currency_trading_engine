"""Performance benchmarking for the matching engine."""

import time
import random
from decimal import Decimal
from statistics import mean, median, stdev
from typing import List

from src.models.orders import Order, OrderType, OrderSide
from src.matching_engine.engine import MatchingEngine


class PerformanceBenchmark:
    """Benchmark matching engine performance."""
    
    def __init__(self):
        self.engine = MatchingEngine()
        self.latencies: dict[str, List[float]] = {
            "order_submission": [],
            "order_matching": [],
            "bbo_calculation": [],
        }
    
    def benchmark_order_submission(self, num_orders: int = 10000):
        """Benchmark order submission latency."""
        print(f"\nBenchmarking order submission ({num_orders} orders)...")
        
        symbol = "BTC-USDT"
        base_price = Decimal("50000")
        
        for i in range(num_orders):
            side = OrderSide.BUY if i % 2 == 0 else OrderSide.SELL
            price_offset = Decimal(random.randint(-1000, 1000))
            price = base_price + price_offset
            
            order = Order(
                symbol=symbol,
                order_type=OrderType.LIMIT,
                side=side,
                quantity=Decimal("0.1"),
                price=price
            )
            
            start = time.perf_counter()
            self.engine.submit_order(order)
            end = time.perf_counter()
            
            self.latencies["order_submission"].append((end - start) * 1_000_000)  # microseconds
        
        self._print_stats("Order Submission", self.latencies["order_submission"])
    
    def benchmark_matching(self, num_orders: int = 5000):
        """Benchmark order matching latency."""
        print(f"\nBenchmarking order matching ({num_orders} matching orders)...")
        
        symbol = "BTC-USDT"
        base_price = Decimal("50000")
        
        # Pre-populate book with resting orders
        for i in range(num_orders):
            order = Order(
                symbol=symbol,
                order_type=OrderType.LIMIT,
                side=OrderSide.SELL,
                quantity=Decimal("0.1"),
                price=base_price + Decimal(i)
            )
            self.engine.submit_order(order)
        
        # Submit matching orders and measure latency
        for i in range(num_orders):
            order = Order(
                symbol=symbol,
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("0.1"),
                price=base_price + Decimal(i)
            )
            
            start = time.perf_counter()
            result = self.engine.submit_order(order)
            end = time.perf_counter()
            
            if len(result["trades"]) > 0:
                self.latencies["order_matching"].append((end - start) * 1_000_000)
        
        self._print_stats("Order Matching", self.latencies["order_matching"])
    
    def benchmark_bbo_calculation(self, num_calculations: int = 100000):
        """Benchmark BBO calculation latency."""
        print(f"\nBenchmarking BBO calculation ({num_calculations} calculations)...")
        
        symbol = "BTC-USDT"
        base_price = Decimal("50000")
        
        # Populate book
        for i in range(100):
            buy_order = Order(
                symbol=symbol,
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("1.0"),
                price=base_price - Decimal(i * 10)
            )
            self.engine.submit_order(buy_order)
            
            sell_order = Order(
                symbol=symbol,
                order_type=OrderType.LIMIT,
                side=OrderSide.SELL,
                quantity=Decimal("1.0"),
                price=base_price + Decimal(i * 10)
            )
            self.engine.submit_order(sell_order)
        
        # Measure BBO calculation
        for _ in range(num_calculations):
            start = time.perf_counter()
            self.engine.get_bbo(symbol)
            end = time.perf_counter()
            
            self.latencies["bbo_calculation"].append((end - start) * 1_000_000)
        
        self._print_stats("BBO Calculation", self.latencies["bbo_calculation"])
    
    def benchmark_throughput(self, duration_seconds: int = 10):
        """Benchmark order processing throughput."""
        print(f"\nBenchmarking throughput ({duration_seconds} seconds)...")
        
        symbol = "BTC-USDT"
        base_price = Decimal("50000")
        
        start_time = time.time()
        order_count = 0
        
        while (time.time() - start_time) < duration_seconds:
            side = OrderSide.BUY if order_count % 2 == 0 else OrderSide.SELL
            price = base_price + Decimal(random.randint(-100, 100))
            
            order = Order(
                symbol=symbol,
                order_type=OrderType.LIMIT,
                side=side,
                quantity=Decimal("0.1"),
                price=price
            )
            
            self.engine.submit_order(order)
            order_count += 1
        
        elapsed = time.time() - start_time
        throughput = order_count / elapsed
        
        print(f"\n  Orders Processed: {order_count:,}")
        print(f"  Duration: {elapsed:.2f} seconds")
        print(f"  Throughput: {throughput:,.2f} orders/second")
        print(f"  Avg Latency: {1_000_000 / throughput:.2f} microseconds/order")
    
    def _print_stats(self, name: str, latencies: List[float]):
        """Print statistics for a benchmark."""
        if not latencies:
            print(f"\n  No data collected for {name}")
            return
        
        print(f"\n  {name} Latency Statistics (microseconds):")
        print(f"    Count: {len(latencies):,}")
        print(f"    Mean: {mean(latencies):.2f} μs")
        print(f"    Median: {median(latencies):.2f} μs")
        print(f"    Min: {min(latencies):.2f} μs")
        print(f"    Max: {max(latencies):.2f} μs")
        if len(latencies) > 1:
            print(f"    Std Dev: {stdev(latencies):.2f} μs")
        print(f"    P95: {self._percentile(latencies, 95):.2f} μs")
        print(f"    P99: {self._percentile(latencies, 99):.2f} μs")
    
    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def run_all_benchmarks(self):
        """Run all benchmarks."""
        print("=" * 70)
        print("MATCHING ENGINE PERFORMANCE BENCHMARK")
        print("=" * 70)
        
        self.benchmark_order_submission(num_orders=10000)
        self.latencies["order_submission"].clear()
        
        # Create fresh engine
        self.engine = MatchingEngine()
        self.benchmark_matching(num_orders=5000)
        self.latencies["order_matching"].clear()
        
        # Create fresh engine
        self.engine = MatchingEngine()
        self.benchmark_bbo_calculation(num_calculations=100000)
        
        # Create fresh engine
        self.engine = MatchingEngine()
        self.benchmark_throughput(duration_seconds=10)
        
        print("\n" + "=" * 70)
        print("BENCHMARK COMPLETE")
        print("=" * 70)


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()
