# coding=utf-8
"""
行情数据获取模块

基于 AKShare 获取股票、指数、加密货币等行情数据
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def retry_on_error(max_retries: int = 3, delay: float = 2.0, backoff: float = 1.5):
    """
    重试装饰器，处理网络错误
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍增因子
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logger.info(f"重试 {func.__name__} (第 {attempt} 次)")
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    
                    # 判断是否为可重试的网络错误
                    retryable = any(x in error_str for x in [
                        'connection', 'timeout', 'remote', 'reset',
                        'aborted', 'refused', 'network', 'temporary'
                    ])
                    
                    if not retryable or attempt >= max_retries:
                        raise
                    
                    logger.warning(f"{func.__name__} 失败，{current_delay:.1f}秒后重试: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_error
        return wrapper
    return decorator


@dataclass
class IndexQuote:
    """指数行情"""
    symbol: str
    name: str
    price: float
    change: float           # 涨跌额
    change_pct: float       # 涨跌幅 (%)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0     # 成交量（手）
    amount: float = 0.0     # 成交额（元）
    timestamp: str = ""


@dataclass
class StockQuote:
    """个股行情"""
    symbol: str
    name: str
    price: float
    change: float           # 涨跌额
    change_pct: float       # 涨跌幅 (%)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0     # 成交量（手）
    amount: float = 0.0     # 成交额（元）
    turnover: float = 0.0   # 换手率 (%)
    pe: float = 0.0         # 市盈率
    pb: float = 0.0         # 市净率
    market_cap: float = 0.0 # 总市值（亿元）
    timestamp: str = ""


@dataclass
class CryptoQuote:
    """加密货币行情"""
    symbol: str
    name: str
    price_usd: float        # 美元价格
    price_cny: float        # 人民币价格
    change_pct_24h: float   # 24小时涨跌幅 (%)
    volume_24h: float = 0.0 # 24小时成交量
    market_cap: float = 0.0 # 市值（美元）
    timestamp: str = ""


@dataclass
class NorthboundFlow:
    """北向资金数据"""
    date: str
    sh_connect: float       # 沪股通净流入（亿元）
    sz_connect: float       # 深股通净流入（亿元）
    total: float            # 北向资金合计（亿元）
    sh_buy: float = 0.0     # 沪股通买入
    sh_sell: float = 0.0    # 沪股通卖出
    sz_buy: float = 0.0     # 深股通买入
    sz_sell: float = 0.0    # 深股通卖出


@dataclass
class SectorFlow:
    """板块资金流向"""
    name: str
    change_pct: float       # 涨跌幅 (%)
    net_flow: float         # 净流入（亿元）
    net_flow_pct: float     # 净流入占比 (%)
    main_flow: float = 0.0  # 主力净流入
    retail_flow: float = 0.0  # 散户净流入


@dataclass
class MarketSnapshot:
    """市场快照（聚合所有行情数据）"""
    timestamp: str
    indices: List[IndexQuote] = field(default_factory=list)
    stocks: List[StockQuote] = field(default_factory=list)
    crypto: List[CryptoQuote] = field(default_factory=list)
    northbound: Optional[NorthboundFlow] = None
    sector_flows: List[SectorFlow] = field(default_factory=list)


class MarketDataFetcher:
    """行情数据获取器"""

    # 请求间隔（秒），避免频繁请求被限流
    REQUEST_INTERVAL = 0.5

    def __init__(self, config: Dict[str, Any]):
        """
        初始化行情数据获取器

        Args:
            config: investment 配置字典
        """
        self.config = config
        self._ak = None  # 延迟导入 akshare
        self._last_request_time = 0

        # 禁用代理：东方财富网等数据源是国内网站，不需要代理
        # 保存环境变量以便后续恢复
        import os
        self._proxy_env_backup = {}
        proxy_vars = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]

        for var in proxy_vars:
            if var in os.environ:
                self._proxy_env_backup[var] = os.environ[var]
                del os.environ[var]

        logger.debug("MarketDataFetcher 已禁用代理（国内数据源）")

    def _get_akshare(self):
        """延迟导入 akshare（首次使用时导入）"""
        if self._ak is None:
            try:
                # 代理已在 __init__ 中禁用
                import akshare as ak
                self._ak = ak
                logger.info("AKShare 模块加载成功")
            except ImportError:
                logger.error("AKShare 未安装，请运行: pip install akshare")
                raise ImportError("akshare 未安装")
        return self._ak

    def _rate_limit(self):
        """请求限流，确保请求间隔"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_INTERVAL:
            time.sleep(self.REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def get_index_quotes(self, indices: List[Dict[str, str]]) -> List[IndexQuote]:
        """
        获取指数行情

        Args:
            indices: 指数配置列表 [{"symbol": "sh000001", "name": "上证指数", "provider": "akshare"}, ...]

        Returns:
            List[IndexQuote]: 指数行情列表
        """
        results = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for idx_config in indices:
            symbol = idx_config.get("symbol", "")
            name = idx_config.get("name", symbol)
            provider = idx_config.get("provider", "akshare")  # 默认使用akshare

            try:
                quote = None
                if provider == "yfinance":
                    quote = self._fetch_yfinance_index(symbol, name)
                else:  # 默认使用akshare
                    ak = self._get_akshare()
                    quote = self._fetch_single_index(ak, symbol, name, timestamp)

                if quote:
                    results.append(quote)
                    logger.info(f"✓ 获取指数 {name}: {quote.price:.2f} ({quote.change_pct:+.2f}%)")
            except Exception as e:
                logger.warning(f"✗ 获取指数 {name}({symbol}) 失败（已重试）: {e}")

        return results

    # 缓存指数数据
    _index_cache = {}
    _index_cache_time = {}
    CACHE_TTL = 60  # 缓存有效期（秒）

    @retry_on_error(max_retries=3, delay=1.0)
    def _fetch_yfinance_index(self, symbol: str, name: str) -> Optional[IndexQuote]:
        """
        使用 yfinance 获取港股/美股指数

        Args:
            symbol: 指数代码（如 "HSI", "IXIC", "DJI"）
            name: 指数名称

        Returns:
            IndexQuote: 指数行情
        """
        try:
            import yfinance as yf

            self._rate_limit()

            # 添加 ^ 前缀（如 HSI -> ^HSI）
            ticker_symbol = f"^{symbol}" if not symbol.startswith("^") else symbol
            ticker = yf.Ticker(ticker_symbol)

            # 获取2天数据用于计算涨跌
            hist = ticker.history(period="2d")

            if hist.empty:
                logger.warning(f"yfinance: {symbol} 数据为空")
                return None

            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest

            price = float(latest['Close'])
            prev_price = float(prev['Close'])
            change = price - prev_price
            change_pct = (change / prev_price * 100) if prev_price > 0 else 0.0

            return IndexQuote(
                symbol=symbol,
                name=name,
                price=price,
                change=change,
                change_pct=change_pct,
                open=float(latest['Open']),
                high=float(latest['High']),
                low=float(latest['Low']),
                volume=float(latest['Volume']) if 'Volume' in latest else 0.0,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        except ImportError:
            logger.error("yfinance 未安装，请运行: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"yfinance 获取 {symbol} 失败: {e}")
            raise  # 让重试装饰器处理

    @retry_on_error(max_retries=3, delay=1.0)
    def _fetch_single_index(self, ak, symbol: str, name: str, timestamp: str) -> Optional[IndexQuote]:
        """获取单个指数行情（使用东方财富日线数据）"""
        self._rate_limit()
        
        try:
            # A股指数（使用 stock_zh_index_daily_em 接口 - 稳定可靠）
            if symbol.startswith("sh") or symbol.startswith("sz"):
                # 检查缓存
                current_time = time.time()
                if (symbol in self._index_cache and 
                    current_time - self._index_cache_time.get(symbol, 0) < self.CACHE_TTL):
                    return self._index_cache[symbol]
                
                df = ak.stock_zh_index_daily_em(symbol=symbol)
                if not df.empty:
                    # 获取最新一行数据
                    row = df.iloc[-1]
                    prev_close = df.iloc[-2]['close'] if len(df) > 1 else row['close']
                    change = row['close'] - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0
                    
                    result = IndexQuote(
                        symbol=symbol,
                        name=name,
                        price=float(row.get("close", 0) or 0),
                        change=float(change),
                        change_pct=float(change_pct),
                        open=float(row.get("open", 0) or 0),
                        high=float(row.get("high", 0) or 0),
                        low=float(row.get("low", 0) or 0),
                        volume=float(row.get("volume", 0) or 0),
                        amount=float(row.get("amount", 0) or 0),
                        timestamp=timestamp,
                    )
                    # 缓存结果
                    self._index_cache[symbol] = result
                    self._index_cache_time[symbol] = current_time
                    return result

            # 港股/美股指数已通过 yfinance 处理，这里只处理A股
            else:
                logger.warning(f"未找到指数 {name}({symbol}) 的行情数据")
            return None

        except Exception as e:
            logger.warning(f"获取指数 {name}({symbol}) 失败: {e}")
            raise  # 让重试装饰器处理

    def get_stock_quotes(self, watchlist: List[Dict[str, str]]) -> List[StockQuote]:
        """
        获取个股行情

        Args:
            watchlist: 个股配置列表 [{"symbol": "sh601127", "name": "赛力斯"}, ...]

        Returns:
            List[StockQuote]: 个股行情列表
        """
        ak = self._get_akshare()
        results = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for stock_config in watchlist:
            symbol = stock_config.get("symbol", "")
            name = stock_config.get("name", symbol)

            try:
                quote = self._fetch_single_stock(ak, symbol, name, timestamp)
                if quote:
                    results.append(quote)
                    logger.info(f"✓ 获取个股 {name}: {quote.price:.2f} ({quote.change_pct:+.2f}%)")
            except Exception as e:
                logger.warning(f"✗ 获取个股 {name}({symbol}) 失败（已重试）: {e}")

        return results

    @retry_on_error(max_retries=3, delay=1.0)
    def _fetch_single_stock(self, ak, symbol: str, name: str, timestamp: str) -> Optional[StockQuote]:
        """获取单个股票行情（使用日K线历史数据接口 - 稳定可靠）"""
        self._rate_limit()
        
        try:
            # A股（使用 stock_zh_a_hist 接口 - 稳定可靠）
            if symbol.startswith("sh") or symbol.startswith("sz"):
                code = symbol[2:]  # 去掉前缀
                
                # 获取最近 5 天的日K线数据
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
                
                df = ak.stock_zh_a_hist(
                    symbol=code, 
                    period="daily", 
                    start_date=start_date, 
                    end_date=end_date, 
                    adjust="qfq"
                )
                
                if not df.empty:
                    # 获取最新一行数据
                    row = df.iloc[-1]
                    
                    return StockQuote(
                        symbol=symbol,
                        name=name,
                        price=float(row.get("收盘", 0) or 0),
                        change=float(row.get("涨跌额", 0) or 0),
                        change_pct=float(row.get("涨跌幅", 0) or 0),
                        open=float(row.get("开盘", 0) or 0),
                        high=float(row.get("最高", 0) or 0),
                        low=float(row.get("最低", 0) or 0),
                        volume=float(row.get("成交量", 0) or 0),
                        amount=float(row.get("成交额", 0) or 0),
                        turnover=float(row.get("换手率", 0) or 0),
                        pe=0,  # 日K线接口不含 PE
                        pb=0,  # 日K线接口不含 PB
                        market_cap=0,
                        timestamp=timestamp,
                    )

            # 港股/美股 - 暂不支持（接口不稳定）
            elif symbol.isdigit() and len(symbol) == 5:
                logger.info(f"跳过港股: {name}({symbol}) - 暂不支持")
            elif symbol.isalpha():
                logger.info(f"跳过美股: {name}({symbol}) - 暂不支持")
            else:
                logger.warning(f"未找到个股 {name}({symbol}) 的行情数据")
            return None

        except Exception as e:
            logger.warning(f"获取个股 {name}({symbol}) 失败: {e}")
            raise  # 让重试装饰器处理

    def get_crypto_quotes(self, crypto_config: Dict[str, Any]) -> List[CryptoQuote]:
        """
        获取加密货币行情（使用 CoinGecko API）

        Args:
            crypto_config: 加密货币配置

        Returns:
            List[CryptoQuote]: 加密货币行情列表
        """
        if not crypto_config.get("enabled", False):
            return []

        results = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        symbols = crypto_config.get("symbols", [])
        provider = crypto_config.get("provider", "akshare")  # 默认使用akshare

        try:
            if provider == "coingecko":
                results = self._fetch_coingecko_crypto(symbols, timestamp)
            else:
                # 使用原有的AKShare方式
                results = self._fetch_akshare_crypto(symbols, timestamp)
        except Exception as e:
            logger.warning(f"获取加密货币行情失败: {e}")

        return results

    def _fetch_coingecko_crypto(self, symbols: List[Dict[str, str]], timestamp: str) -> List[CryptoQuote]:
        """使用 CoinGecko API 获取加密货币行情"""
        try:
            from pycoingecko import CoinGeckoAPI

            self._rate_limit()
            cg = CoinGeckoAPI()

            results = []

            # 批量获取所有加密货币的价格
            ids_list = [s.get("symbol", "").lower() for s in symbols if isinstance(s, dict)]
            price_data = cg.get_price(ids=ids_list, vs_currencies='usd,cny', include_market_cap='true', include_24hr_vol='true', include_24hr_change='true')

            for item in symbols:
                if not isinstance(item, dict):
                    continue

                symbol = item.get("symbol", "").lower()
                name = item.get("name", symbol)

                if symbol in price_data:
                    data = price_data[symbol]
                    results.append(CryptoQuote(
                        symbol=symbol.upper(),
                        name=name,
                        price_usd=float(data.get('usd', 0)),
                        price_cny=float(data.get('cny', 0)),
                        change_pct_24h=float(data.get('usd_24h_change', 0)),
                        volume_24h=float(data.get('usd_24h_vol', 0)),
                        market_cap=float(data.get('usd_market_cap', 0)),
                        timestamp=timestamp
                    ))
                    logger.info(f"✓ 获取加密货币 {name}: ${data.get('usd', 0):,.2f}")
                else:
                    logger.warning(f"✗ 未找到加密货币 {name}({symbol}) 的数据")

            return results

        except ImportError:
            logger.error("pycoingecko 未安装，请运行: pip install pycoingecko")
            return []
        except Exception as e:
            logger.error(f"CoinGecko API 调用失败: {e}")
            return []

    def _fetch_akshare_crypto(self, symbols: List[Dict[str, str]], timestamp: str) -> List[CryptoQuote]:
        """使用 AKShare 获取加密货币行情（原有逻辑）"""
        ak = self._get_akshare()
        results = []

        # 一次性获取所有加密货币数据
        self._rate_limit()
        try:
            df = ak.crypto_js_spot()
            if not df.empty:
                for crypto in symbols:
                    symbol = crypto.get("symbol", "") if isinstance(crypto, dict) else crypto
                    name = crypto.get("name", symbol) if isinstance(crypto, dict) else crypto

                    quote = self._parse_crypto_from_df(df, symbol, name, timestamp)
                    if quote:
                        results.append(quote)
        except Exception as e:
            logger.warning(f"AKShare 获取加密货币行情失败: {e}")

        return results
    
    # USD/CNY 汇率（可以后续从 API 获取实时汇率）
    USD_CNY_RATE = 7.25

    def _parse_crypto_from_df(self, df, symbol: str, name: str, timestamp: str) -> Optional[CryptoQuote]:
        """从数据框中解析加密货币行情"""
        try:
            symbol_upper = symbol.upper()
            
            # 优先匹配 XXXUSD 交易对（美元计价）
            usd_pair = f"{symbol_upper}USD"
            row = df[df["交易品种"].str.upper() == usd_pair]
            
            # 如果没有找到，尝试其他美元交易对
            if row.empty:
                row = df[df["交易品种"].str.upper().str.startswith(f"{symbol_upper}USD")]
            
            # 如果还没找到，排除 JPY/EUR 等，尝试其他匹配
            if row.empty:
                # 排除日元、欧元等非美元计价
                mask = (
                    df["交易品种"].str.upper().str.contains(symbol_upper, na=False) &
                    ~df["交易品种"].str.upper().str.contains("JPY|EUR|GBP|CHF", na=False, regex=True)
                )
                row = df[mask]
            
            if not row.empty:
                row = row.iloc[0]
                price_usd = float(row.get("最近报价", 0) or 0)
                
                # 检查价格是否合理（BTC 价格应该在 10000-200000 USD 范围内）
                if symbol_upper == "BTC" and (price_usd < 1000 or price_usd > 500000):
                    logger.warning(f"BTC 价格异常: {price_usd}，可能是非 USD 计价")
                    return None
                
                # 解析涨跌幅
                change_str = row.get("涨跌幅", "0")
                if isinstance(change_str, str):
                    change_pct = float(change_str.replace("%", "").replace(",", "") or 0)
                else:
                    change_pct = float(change_str or 0)
                
                # 解析24小时成交量
                volume = float(row.get("24小时成交量", 0) or 0)
                
                # 计算人民币价格
                price_cny = price_usd * self.USD_CNY_RATE
                
                return CryptoQuote(
                    symbol=symbol,
                    name=name,
                    price_usd=price_usd,
                    price_cny=price_cny,
                    change_pct_24h=change_pct,
                    volume_24h=volume,
                    timestamp=timestamp,
                )
        except Exception as e:
            logger.warning(f"解析加密货币 {symbol} 失败: {e}")
        
        return None

    @retry_on_error(max_retries=3, delay=1.0)
    def get_northbound_flow(self) -> Optional[NorthboundFlow]:
        """
        获取北向资金数据

        Returns:
            NorthboundFlow: 北向资金数据
        """
        ak = self._get_akshare()
        self._rate_limit()

        try:
            # 使用 stock_hsgt_fund_flow_summary_em 获取沪深港通资金流向
            # 列名: 交易日, 类型, 板块, 资金方向, 交易状态, 成交净买额, 资金净流入, ...
            df = ak.stock_hsgt_fund_flow_summary_em()
            if not df.empty:
                # 筛选北向资金（沪股通和深股通的北向）
                north_df = df[(df["资金方向"] == "北向")]
                
                sh_value = 0.0
                sz_value = 0.0
                date_str = datetime.now().strftime("%Y-%m-%d")
                
                for _, row in north_df.iterrows():
                    board = str(row.get("板块", ""))
                    # 获取资金净流入（单位：亿元）
                    flow = float(row.get("资金净流入", 0) or row.get("成交净买额", 0) or 0)
                    
                    if "沪股通" in board:
                        sh_value = flow
                        date_str = str(row.get("交易日", date_str))
                    elif "深股通" in board:
                        sz_value = flow
                
                return NorthboundFlow(
                    date=date_str,
                    sh_connect=sh_value,
                    sz_connect=sz_value,
                    total=sh_value + sz_value,
                )
        except Exception as e:
            logger.warning(f"获取北向资金数据失败: {e}")

        # 尝试备用方法：使用历史数据接口
        self._rate_limit()
        try:
            df = ak.stock_hsgt_hist_em(symbol="沪股通")
            if not df.empty:
                latest = df.iloc[-1]
                sh_value = float(latest.get("当日资金流入", 0) or latest.get("净买额", 0) or 0)
                
                self._rate_limit()
                df_sz = ak.stock_hsgt_hist_em(symbol="深股通")
                sz_value = 0
                if not df_sz.empty:
                    sz_value = float(df_sz.iloc[-1].get("当日资金流入", 0) or df_sz.iloc[-1].get("净买额", 0) or 0)
                
                return NorthboundFlow(
                    date=datetime.now().strftime("%Y-%m-%d"),
                    sh_connect=sh_value,
                    sz_connect=sz_value,
                    total=sh_value + sz_value,
                )
        except Exception as e:
            logger.warning(f"备用接口获取北向资金数据失败: {e}")

        return None

    @retry_on_error(max_retries=3, delay=1.0)
    def get_sector_flows(self, top_n: int = 10) -> List[SectorFlow]:
        """
        获取板块资金流向

        Args:
            top_n: 返回前 N 个板块

        Returns:
            List[SectorFlow]: 板块资金流向列表
        """
        ak = self._get_akshare()
        results = []
        self._rate_limit()

        try:
            # 获取行业板块资金流向
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
            if not df.empty:
                for _, row in df.head(top_n).iterrows():
                    # 动态获取列名
                    name_col = "名称" if "名称" in df.columns else df.columns[0]
                    
                    # 查找涨跌幅列
                    change_col = None
                    for col in df.columns:
                        if "涨跌" in col:
                            change_col = col
                            break
                    
                    # 查找净流入列
                    flow_col = None
                    flow_pct_col = None
                    for col in df.columns:
                        if "净流入" in col and "净额" in col:
                            flow_col = col
                        elif "净流入" in col and "占比" in col:
                            flow_pct_col = col
                    
                    change_pct = float(row.get(change_col, 0) or 0) if change_col else 0
                    net_flow = float(row.get(flow_col, 0) or 0) / 1e8 if flow_col else 0
                    net_flow_pct = float(row.get(flow_pct_col, 0) or 0) if flow_pct_col else 0
                    
                    results.append(SectorFlow(
                        name=str(row.get(name_col, "")),
                        change_pct=change_pct,
                        net_flow=net_flow,
                        net_flow_pct=net_flow_pct,
                        main_flow=net_flow,
                    ))
                return results
        except Exception as e:
            logger.warning(f"获取板块资金流向失败: {e}")
            
            # 尝试备用接口
            self._rate_limit()
            try:
                df = ak.stock_fund_flow_industry(symbol="即时")
                if not df.empty:
                    for _, row in df.head(top_n).iterrows():
                        results.append(SectorFlow(
                            name=str(row.iloc[0]) if len(row) > 0 else "",
                            change_pct=float(row.get("涨跌幅", 0) or 0),
                            net_flow=float(row.get("主力净流入", 0) or 0) / 1e8,
                            net_flow_pct=0,
                            main_flow=float(row.get("主力净流入", 0) or 0) / 1e8,
                        ))
            except Exception as e2:
                logger.warning(f"备用接口获取板块资金流向失败: {e2}")

        return results

    def get_market_snapshot(self) -> MarketSnapshot:
        """
        获取完整市场快照

        Returns:
            MarketSnapshot: 聚合的市场数据快照
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 获取各项数据
        indices = self.get_index_quotes(self.config.get("indices", []))
        stocks = self.get_stock_quotes(self.config.get("watchlist", []))
        crypto = self.get_crypto_quotes(self.config.get("crypto", {}))

        # 获取资金流数据
        northbound = None
        sector_flows = []
        sources_config = self.config.get("sources", {}).get("akshare", {})
        money_flow_config = sources_config.get("money_flow", {})

        if money_flow_config.get("northbound", False):
            northbound = self.get_northbound_flow()

        if money_flow_config.get("sector_flow", False):
            sector_flows = self.get_sector_flows()

        return MarketSnapshot(
            timestamp=timestamp,
            indices=indices,
            stocks=stocks,
            crypto=crypto,
            northbound=northbound,
            sector_flows=sector_flows,
        )
