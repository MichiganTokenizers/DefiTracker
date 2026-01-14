"""
Enosys DEX V3 Position Analysis Utilities

Provides functions to analyze concentrated liquidity positions:
- Range bucketing and categorization
- APR/reward distribution by range width
- Position performance comparison
- Historical trend analysis

Usage:
    from src.adapters.flare.enosys_analysis import EnosysPositionAnalyzer
    
    analyzer = EnosysPositionAnalyzer(db_connection)
    stats = analyzer.get_range_distribution_stats(pool_address)
    report = analyzer.generate_apr_report(pool_address, days=7)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from src.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


@dataclass
class RangeCategoryStats:
    """Statistics for a single range category."""
    category: str
    position_count: int = 0
    active_count: int = 0
    active_pct: Decimal = Decimal(0)
    total_liquidity: Decimal = Decimal(0)
    total_tvl_usd: Decimal = Decimal(0)
    avg_range_width_pct: Decimal = Decimal(0)
    
    # APR metrics
    avg_fee_apr: Optional[Decimal] = None
    avg_incentive_apr: Optional[Decimal] = None
    avg_total_apr: Optional[Decimal] = None
    
    # Min/Max for range
    min_apr: Optional[Decimal] = None
    max_apr: Optional[Decimal] = None
    
    # Fee earnings
    total_fees_24h_usd: Decimal = Decimal(0)


@dataclass
class PoolAnalysisSummary:
    """Summary analysis for a pool."""
    pool_address: str
    token0_symbol: str
    token1_symbol: str
    snapshot_time: datetime
    
    # Overall metrics
    total_tvl_usd: Decimal = Decimal(0)
    total_positions: int = 0
    active_positions: int = 0
    active_pct: Decimal = Decimal(0)
    
    # By category
    narrow_stats: Optional[RangeCategoryStats] = None
    medium_stats: Optional[RangeCategoryStats] = None
    wide_stats: Optional[RangeCategoryStats] = None
    
    # Best performing category
    best_category: str = ""
    best_category_apr: Optional[Decimal] = None


@dataclass
class PositionPerformance:
    """Performance metrics for a single position over time."""
    token_id: int
    pool_address: str
    range_category: str
    range_width_pct: Decimal
    
    # Aggregated metrics
    avg_apr: Optional[Decimal] = None
    total_fees_earned_usd: Decimal = Decimal(0)
    time_in_range_pct: Decimal = Decimal(0)
    snapshot_count: int = 0
    
    # Current state
    current_liquidity: Decimal = Decimal(0)
    is_currently_in_range: bool = False


class EnosysPositionAnalyzer:
    """
    Analyzer for Enosys DEX V3 concentrated liquidity positions.
    
    Provides methods to analyze historical position data and
    calculate performance metrics by range category.
    """
    
    def __init__(self, db: Optional[DatabaseConnection] = None):
        self.db = db or DatabaseConnection()
    
    # ============================================
    # Range Distribution Analysis
    # ============================================
    
    def get_range_distribution_stats(
        self, 
        pool_address: str,
        snapshot_time: Optional[datetime] = None
    ) -> Dict[str, RangeCategoryStats]:
        """
        Get position distribution statistics by range category.
        
        Args:
            pool_address: Pool contract address
            snapshot_time: Specific snapshot time (default: latest)
            
        Returns:
            Dict mapping category -> RangeCategoryStats
        """
        conn = self.db.get_connection()
        
        try:
            with conn.cursor() as cur:
                # Get the target snapshot time
                if snapshot_time is None:
                    cur.execute("""
                        SELECT MAX(timestamp) FROM enosys_position_snapshots
                        WHERE pool_address = %s
                    """, (pool_address,))
                    result = cur.fetchone()
                    if not result or not result[0]:
                        return {}
                    snapshot_time = result[0]
                
                # Query aggregated stats by range category
                cur.execute("""
                    SELECT 
                        range_category,
                        COUNT(*) as position_count,
                        SUM(CASE WHEN is_in_range THEN 1 ELSE 0 END) as active_count,
                        SUM(liquidity::numeric) as total_liquidity,
                        SUM(COALESCE(amount_usd, 0)) as total_tvl_usd,
                        AVG(range_width_percent) as avg_range_width,
                        AVG(fee_apr) as avg_fee_apr,
                        AVG(incentive_apr) as avg_incentive_apr,
                        AVG(total_apr) as avg_total_apr,
                        MIN(total_apr) as min_apr,
                        MAX(total_apr) as max_apr,
                        SUM(COALESCE(fees_24h_usd, 0)) as total_fees_24h
                    FROM enosys_position_snapshots
                    WHERE pool_address = %s
                      AND timestamp = %s
                    GROUP BY range_category
                    ORDER BY range_category
                """, (pool_address, snapshot_time))
                
                rows = cur.fetchall()
                
                stats = {}
                for row in rows:
                    category = row[0]
                    position_count = row[1] or 0
                    active_count = row[2] or 0
                    
                    stats[category] = RangeCategoryStats(
                        category=category,
                        position_count=position_count,
                        active_count=active_count,
                        active_pct=Decimal(active_count / position_count * 100) if position_count else Decimal(0),
                        total_liquidity=Decimal(str(row[3])) if row[3] else Decimal(0),
                        total_tvl_usd=Decimal(str(row[4])) if row[4] else Decimal(0),
                        avg_range_width_pct=Decimal(str(row[5])) if row[5] else Decimal(0),
                        avg_fee_apr=Decimal(str(row[6])) if row[6] else None,
                        avg_incentive_apr=Decimal(str(row[7])) if row[7] else None,
                        avg_total_apr=Decimal(str(row[8])) if row[8] else None,
                        min_apr=Decimal(str(row[9])) if row[9] else None,
                        max_apr=Decimal(str(row[10])) if row[10] else None,
                        total_fees_24h_usd=Decimal(str(row[11])) if row[11] else Decimal(0)
                    )
                
                return stats
                
        finally:
            self.db.return_connection(conn)
    
    def get_pool_analysis_summary(
        self, 
        pool_address: str,
        snapshot_time: Optional[datetime] = None
    ) -> Optional[PoolAnalysisSummary]:
        """
        Get comprehensive analysis summary for a pool.
        
        Args:
            pool_address: Pool contract address
            snapshot_time: Specific snapshot time (default: latest)
            
        Returns:
            PoolAnalysisSummary or None if no data
        """
        conn = self.db.get_connection()
        
        try:
            with conn.cursor() as cur:
                # Get pool info from latest snapshot
                cur.execute("""
                    SELECT 
                        token0_symbol, token1_symbol, 
                        tvl_usd, total_positions, active_positions,
                        timestamp
                    FROM enosys_pool_snapshots
                    WHERE pool_address = %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (pool_address,))
                
                pool_row = cur.fetchone()
                if not pool_row:
                    return None
                
                # Get range distribution stats
                range_stats = self.get_range_distribution_stats(pool_address, snapshot_time)
                
                # Calculate totals
                total_positions = sum(s.position_count for s in range_stats.values())
                active_positions = sum(s.active_count for s in range_stats.values())
                total_tvl = sum(s.total_tvl_usd for s in range_stats.values())
                
                # Find best performing category
                best_category = ""
                best_apr = None
                for category, stats in range_stats.items():
                    if stats.avg_total_apr is not None:
                        if best_apr is None or stats.avg_total_apr > best_apr:
                            best_apr = stats.avg_total_apr
                            best_category = category
                
                summary = PoolAnalysisSummary(
                    pool_address=pool_address,
                    token0_symbol=pool_row[0],
                    token1_symbol=pool_row[1],
                    snapshot_time=pool_row[5],
                    total_tvl_usd=Decimal(str(pool_row[2])) if pool_row[2] else total_tvl,
                    total_positions=pool_row[3] or total_positions,
                    active_positions=pool_row[4] or active_positions,
                    active_pct=Decimal(active_positions / total_positions * 100) if total_positions else Decimal(0),
                    narrow_stats=range_stats.get('narrow'),
                    medium_stats=range_stats.get('medium'),
                    wide_stats=range_stats.get('wide'),
                    best_category=best_category,
                    best_category_apr=best_apr
                )
                
                return summary
                
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # Historical Trend Analysis
    # ============================================
    
    def get_apr_trend_by_category(
        self, 
        pool_address: str,
        days: int = 7
    ) -> Dict[str, List[Tuple[datetime, Decimal]]]:
        """
        Get APR trend over time for each range category.
        
        Args:
            pool_address: Pool contract address
            days: Number of days to look back
            
        Returns:
            Dict mapping category -> list of (timestamp, avg_apr) tuples
        """
        conn = self.db.get_connection()
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        range_category,
                        DATE_TRUNC('day', timestamp) as day,
                        AVG(total_apr) as avg_apr
                    FROM enosys_position_snapshots
                    WHERE pool_address = %s
                      AND timestamp >= NOW() - INTERVAL '%s days'
                      AND total_apr IS NOT NULL
                    GROUP BY range_category, DATE_TRUNC('day', timestamp)
                    ORDER BY range_category, day
                """, (pool_address, days))
                
                rows = cur.fetchall()
                
                trends = {'narrow': [], 'medium': [], 'wide': []}
                for row in rows:
                    category = row[0]
                    if category in trends:
                        trends[category].append((row[1], Decimal(str(row[2]))))
                
                return trends
                
        finally:
            self.db.return_connection(conn)
    
    def get_position_performance_history(
        self, 
        token_id: int,
        days: int = 30
    ) -> List[Dict]:
        """
        Get historical performance data for a specific position.
        
        Args:
            token_id: NFT token ID
            days: Number of days to look back
            
        Returns:
            List of daily performance records
        """
        conn = self.db.get_connection()
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        DATE_TRUNC('day', timestamp) as day,
                        is_in_range,
                        range_category,
                        amount_usd,
                        fee_apr,
                        incentive_apr,
                        total_apr,
                        fees_24h_usd
                    FROM enosys_position_snapshots
                    WHERE token_id = %s
                      AND timestamp >= NOW() - INTERVAL '%s days'
                    ORDER BY timestamp DESC
                """, (token_id, days))
                
                rows = cur.fetchall()
                
                history = []
                for row in rows:
                    history.append({
                        'date': row[0],
                        'is_in_range': row[1],
                        'range_category': row[2],
                        'amount_usd': Decimal(str(row[3])) if row[3] else None,
                        'fee_apr': Decimal(str(row[4])) if row[4] else None,
                        'incentive_apr': Decimal(str(row[5])) if row[5] else None,
                        'total_apr': Decimal(str(row[6])) if row[6] else None,
                        'fees_24h_usd': Decimal(str(row[7])) if row[7] else None
                    })
                
                return history
                
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # Top Performers Analysis
    # ============================================
    
    def get_top_positions_by_apr(
        self, 
        pool_address: str,
        limit: int = 10,
        category: Optional[str] = None
    ) -> List[PositionPerformance]:
        """
        Get top performing positions by average APR.
        
        Args:
            pool_address: Pool contract address
            limit: Maximum number of positions to return
            category: Filter by range category (optional)
            
        Returns:
            List of PositionPerformance objects
        """
        conn = self.db.get_connection()
        
        try:
            with conn.cursor() as cur:
                category_filter = "AND range_category = %s" if category else ""
                params = [pool_address]
                if category:
                    params.append(category)
                params.append(limit)
                
                cur.execute(f"""
                    SELECT 
                        token_id,
                        pool_address,
                        range_category,
                        AVG(range_width_percent) as avg_range_width,
                        AVG(total_apr) as avg_apr,
                        SUM(COALESCE(fees_24h_usd, 0)) as total_fees,
                        AVG(CASE WHEN is_in_range THEN 100 ELSE 0 END) as time_in_range_pct,
                        COUNT(*) as snapshot_count,
                        MAX(liquidity::numeric) as current_liquidity,
                        BOOL_OR(is_in_range) as is_currently_in_range
                    FROM enosys_position_snapshots
                    WHERE pool_address = %s
                      {category_filter}
                      AND total_apr IS NOT NULL
                    GROUP BY token_id, pool_address, range_category
                    ORDER BY avg_apr DESC
                    LIMIT %s
                """, tuple(params))
                
                rows = cur.fetchall()
                
                positions = []
                for row in rows:
                    positions.append(PositionPerformance(
                        token_id=row[0],
                        pool_address=row[1],
                        range_category=row[2],
                        range_width_pct=Decimal(str(row[3])) if row[3] else Decimal(0),
                        avg_apr=Decimal(str(row[4])) if row[4] else None,
                        total_fees_earned_usd=Decimal(str(row[5])) if row[5] else Decimal(0),
                        time_in_range_pct=Decimal(str(row[6])) if row[6] else Decimal(0),
                        snapshot_count=row[7] or 0,
                        current_liquidity=Decimal(str(row[8])) if row[8] else Decimal(0),
                        is_currently_in_range=row[9] or False
                    ))
                
                return positions
                
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # Report Generation
    # ============================================
    
    def generate_apr_report(
        self, 
        pool_address: str,
        days: int = 7
    ) -> Dict:
        """
        Generate a comprehensive APR analysis report.
        
        Args:
            pool_address: Pool contract address
            days: Number of days to analyze
            
        Returns:
            Dict with report sections
        """
        summary = self.get_pool_analysis_summary(pool_address)
        if not summary:
            return {'error': 'No data available for pool'}
        
        range_stats = self.get_range_distribution_stats(pool_address)
        apr_trends = self.get_apr_trend_by_category(pool_address, days)
        top_narrow = self.get_top_positions_by_apr(pool_address, limit=5, category='narrow')
        top_medium = self.get_top_positions_by_apr(pool_address, limit=5, category='medium')
        top_wide = self.get_top_positions_by_apr(pool_address, limit=5, category='wide')
        
        report = {
            'pool': {
                'address': pool_address,
                'pair': f"{summary.token0_symbol}-{summary.token1_symbol}",
                'snapshot_time': summary.snapshot_time.isoformat(),
                'total_tvl_usd': float(summary.total_tvl_usd),
                'total_positions': summary.total_positions,
                'active_positions': summary.active_positions,
                'active_pct': float(summary.active_pct)
            },
            'best_strategy': {
                'category': summary.best_category,
                'avg_apr': float(summary.best_category_apr) if summary.best_category_apr else None
            },
            'range_analysis': {},
            'apr_trends': {},
            'top_performers': {
                'narrow': [],
                'medium': [],
                'wide': []
            }
        }
        
        # Range analysis
        for category, stats in range_stats.items():
            report['range_analysis'][category] = {
                'position_count': stats.position_count,
                'active_pct': float(stats.active_pct),
                'total_tvl_usd': float(stats.total_tvl_usd),
                'avg_range_width_pct': float(stats.avg_range_width_pct),
                'avg_fee_apr': float(stats.avg_fee_apr) if stats.avg_fee_apr else None,
                'avg_incentive_apr': float(stats.avg_incentive_apr) if stats.avg_incentive_apr else None,
                'avg_total_apr': float(stats.avg_total_apr) if stats.avg_total_apr else None,
                'apr_range': {
                    'min': float(stats.min_apr) if stats.min_apr else None,
                    'max': float(stats.max_apr) if stats.max_apr else None
                },
                'fees_24h_usd': float(stats.total_fees_24h_usd)
            }
        
        # APR trends
        for category, trend in apr_trends.items():
            report['apr_trends'][category] = [
                {'date': t[0].isoformat(), 'apr': float(t[1])} 
                for t in trend
            ]
        
        # Top performers
        for pos in top_narrow:
            report['top_performers']['narrow'].append({
                'token_id': pos.token_id,
                'range_width_pct': float(pos.range_width_pct),
                'avg_apr': float(pos.avg_apr) if pos.avg_apr else None,
                'time_in_range_pct': float(pos.time_in_range_pct)
            })
        
        for pos in top_medium:
            report['top_performers']['medium'].append({
                'token_id': pos.token_id,
                'range_width_pct': float(pos.range_width_pct),
                'avg_apr': float(pos.avg_apr) if pos.avg_apr else None,
                'time_in_range_pct': float(pos.time_in_range_pct)
            })
        
        for pos in top_wide:
            report['top_performers']['wide'].append({
                'token_id': pos.token_id,
                'range_width_pct': float(pos.range_width_pct),
                'avg_apr': float(pos.avg_apr) if pos.avg_apr else None,
                'time_in_range_pct': float(pos.time_in_range_pct)
            })
        
        return report
    
    def print_summary_report(self, pool_address: str):
        """Print a formatted summary report to console."""
        summary = self.get_pool_analysis_summary(pool_address)
        if not summary:
            print(f"No data available for pool {pool_address}")
            return
        
        print("=" * 70)
        print(f"Enosys V3 Position Analysis: {summary.token0_symbol}-{summary.token1_symbol}")
        print(f"Pool: {pool_address}")
        print(f"Snapshot: {summary.snapshot_time}")
        print("=" * 70)
        print()
        print(f"Total TVL: ${summary.total_tvl_usd:,.2f}")
        print(f"Total Positions: {summary.total_positions}")
        print(f"Active (In-Range): {summary.active_positions} ({summary.active_pct:.1f}%)")
        print()
        print("-" * 70)
        print("APR by Range Category:")
        print("-" * 70)
        print(f"{'Category':<10} {'Positions':>10} {'Active %':>10} {'Avg APR':>12} {'APR Range':>20}")
        print("-" * 70)
        
        for category, stats in [
            ('Narrow', summary.narrow_stats),
            ('Medium', summary.medium_stats),
            ('Wide', summary.wide_stats)
        ]:
            if stats:
                apr_str = f"{stats.avg_total_apr:.2f}%" if stats.avg_total_apr else "N/A"
                range_str = ""
                if stats.min_apr is not None and stats.max_apr is not None:
                    range_str = f"{stats.min_apr:.1f}% - {stats.max_apr:.1f}%"
                print(f"{category:<10} {stats.position_count:>10} {stats.active_pct:>9.1f}% {apr_str:>12} {range_str:>20}")
        
        print("-" * 70)
        if summary.best_category:
            print(f"\nBest Performing Category: {summary.best_category.upper()} "
                  f"(Avg APR: {summary.best_category_apr:.2f}%)")
        print("=" * 70)

