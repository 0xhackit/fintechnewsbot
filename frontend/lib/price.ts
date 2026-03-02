/**
 * Price fetching utilities.
 * CoinGecko for crypto (free, no key needed).
 * Yahoo Finance for stocks/ETFs.
 */

// ── CoinGecko ticker → ID mapping ──

const TICKER_TO_COINGECKO: Record<string, string> = {
  BTC: "bitcoin",
  ETH: "ethereum",
  SOL: "solana",
  XRP: "ripple",
  ADA: "cardano",
  DOGE: "dogecoin",
  DOT: "polkadot",
  AVAX: "avalanche-2",
  LINK: "chainlink",
  MATIC: "matic-network",
  POL: "matic-network",
  UNI: "uniswap",
  AAVE: "aave",
  LTC: "litecoin",
  ATOM: "cosmos",
  FIL: "filecoin",
  ARB: "arbitrum",
  OP: "optimism",
  APT: "aptos",
  SUI: "sui",
  NEAR: "near",
  INJ: "injective-protocol",
  TIA: "celestia",
  SEI: "sei-network",
  PEPE: "pepe",
  WIF: "dogwifcoin",
  ONDO: "ondo-finance",
  RENDER: "render-token",
  RNDR: "render-token",
  FET: "fetch-ai",
  BNB: "binancecoin",
  TRX: "tron",
  TON: "the-open-network",
  HBAR: "hedera-hashgraph",
  MKR: "maker",
  CRV: "curve-dao-token",
  COMP: "compound-governance-token",
  SNX: "havven",
  USDT: "tether",
  USDC: "usd-coin",
  DAI: "dai",
  SHIB: "shiba-inu",
  BCH: "bitcoin-cash",
  ETC: "ethereum-classic",
  XLM: "stellar",
  ALGO: "algorand",
  VET: "vechain",
  SAND: "the-sandbox",
  MANA: "decentraland",
  AXS: "axie-infinity",
  GRT: "the-graph",
  ENS: "ethereum-name-service",
  LDO: "lido-dao",
  RPL: "rocket-pool",
  GMX: "gmx",
  DYDX: "dydx-chain",
  JUP: "jupiter-exchange-solana",
  PYTH: "pyth-network",
  W: "wormhole",
  JTO: "jito-governance-token",
  BONK: "bonk",
  PENDLE: "pendle",
  ENA: "ethena",
  EIGEN: "eigenlayer",
};

export interface PriceResult {
  price: number | null;
  currency: string;
  change24h: number | null;
  source: "coingecko" | "yahoo" | "unavailable";
}

const UNAVAILABLE: PriceResult = {
  price: null,
  currency: "USD",
  change24h: null,
  source: "unavailable",
};

// ── CoinGecko (crypto) ──

async function fetchCryptoPrice(ticker: string): Promise<PriceResult> {
  const id = TICKER_TO_COINGECKO[ticker.toUpperCase()];
  if (!id) return UNAVAILABLE;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);

  try {
    const url = `https://api.coingecko.com/api/v3/simple/price?ids=${id}&vs_currencies=usd&include_24hr_change=true`;
    const resp = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });

    if (!resp.ok) return UNAVAILABLE;

    const data = (await resp.json()) as Record<
      string,
      { usd?: number; usd_24h_change?: number }
    >;

    const coin = data[id];
    if (!coin || coin.usd == null) return UNAVAILABLE;

    return {
      price: coin.usd,
      currency: "USD",
      change24h: coin.usd_24h_change ?? null,
      source: "coingecko",
    };
  } catch {
    return UNAVAILABLE;
  } finally {
    clearTimeout(timeout);
  }
}

// ── Yahoo Finance (stocks / ETFs) ──

async function fetchStockPrice(ticker: string): Promise<PriceResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);

  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker.toUpperCase())}?range=1d&interval=1d`;
    const resp = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; FintechOnchain/1.0)",
      },
    });

    if (!resp.ok) return UNAVAILABLE;

    const data = (await resp.json()) as {
      chart?: {
        result?: Array<{
          meta?: {
            regularMarketPrice?: number;
            previousClose?: number;
            currency?: string;
          };
        }>;
      };
    };

    const meta = data.chart?.result?.[0]?.meta;
    if (!meta || meta.regularMarketPrice == null) return UNAVAILABLE;

    const price = meta.regularMarketPrice;
    const prevClose = meta.previousClose;
    const change24h =
      prevClose != null && prevClose > 0
        ? ((price - prevClose) / prevClose) * 100
        : null;

    return {
      price,
      currency: (meta.currency || "USD").toUpperCase(),
      change24h,
      source: "yahoo",
    };
  } catch {
    return UNAVAILABLE;
  } finally {
    clearTimeout(timeout);
  }
}

// ── Public API ──

/**
 * Fetch price for a single ticker.
 * Dispatches to CoinGecko for crypto/token, Yahoo Finance for stock/etf.
 */
export async function fetchPrice(
  ticker: string,
  assetType: string
): Promise<PriceResult> {
  const t = assetType.toLowerCase();

  if (t === "crypto" || t === "token") {
    return fetchCryptoPrice(ticker);
  }

  if (t === "stock" || t === "etf") {
    return fetchStockPrice(ticker);
  }

  // Unknown type: try crypto first, then stock
  const crypto = await fetchCryptoPrice(ticker);
  if (crypto.price !== null) return crypto;
  return fetchStockPrice(ticker);
}

/**
 * Batch-fetch prices for multiple tickers.
 * Groups crypto tickers into a single CoinGecko call for efficiency.
 */
export async function fetchMultiplePrices(
  tickers: { ticker: string; assetType: string }[]
): Promise<Record<string, PriceResult>> {
  const results: Record<string, PriceResult> = {};

  // Separate crypto vs stock tickers
  const cryptoTickers: string[] = [];
  const stockTickers: string[] = [];

  for (const { ticker, assetType } of tickers) {
    const key = ticker.toUpperCase();
    if (results[key]) continue; // skip dupes

    const t = assetType.toLowerCase();
    if (t === "crypto" || t === "token") {
      const cgId = TICKER_TO_COINGECKO[key];
      if (cgId) {
        cryptoTickers.push(key);
      } else {
        results[key] = UNAVAILABLE;
      }
    } else if (t === "stock" || t === "etf") {
      stockTickers.push(key);
    } else {
      // Unknown: try crypto map first
      const cgId = TICKER_TO_COINGECKO[key];
      if (cgId) {
        cryptoTickers.push(key);
      } else {
        stockTickers.push(key);
      }
    }
  }

  // Batch CoinGecko call
  if (cryptoTickers.length > 0) {
    const ids = cryptoTickers
      .map((t) => TICKER_TO_COINGECKO[t])
      .filter(Boolean);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10_000);

    try {
      const url = `https://api.coingecko.com/api/v3/simple/price?ids=${ids.join(",")}&vs_currencies=usd&include_24hr_change=true`;
      const resp = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });

      if (resp.ok) {
        const data = (await resp.json()) as Record<
          string,
          { usd?: number; usd_24h_change?: number }
        >;

        for (const ticker of cryptoTickers) {
          const cgId = TICKER_TO_COINGECKO[ticker];
          const coin = data[cgId];
          if (coin && coin.usd != null) {
            results[ticker] = {
              price: coin.usd,
              currency: "USD",
              change24h: coin.usd_24h_change ?? null,
              source: "coingecko",
            };
          } else {
            results[ticker] = UNAVAILABLE;
          }
        }
      } else {
        for (const ticker of cryptoTickers) {
          results[ticker] = UNAVAILABLE;
        }
      }
    } catch {
      for (const ticker of cryptoTickers) {
        results[ticker] = UNAVAILABLE;
      }
    } finally {
      clearTimeout(timeout);
    }
  }

  // Parallel Yahoo Finance calls for stocks
  if (stockTickers.length > 0) {
    const stockResults = await Promise.all(
      stockTickers.map((t) => fetchStockPrice(t))
    );
    stockTickers.forEach((ticker, i) => {
      results[ticker] = stockResults[i];
    });
  }

  return results;
}
