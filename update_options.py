#!/usr/bin/env python3
"""每日更新期权数据 -> 生成 data.js，dashboard.html 会自动读取。
用法:  pip install yfinance pandas
       python update_options.py
定时(每天美股收盘后):
  macOS/Linux crontab:  30 13 * * 2-6  cd /你的目录 && python update_options.py
  (北京时间 05:30 附近，按需调整)  Windows: 任务计划程序每日运行
"""
import json, math, datetime as dt
import yfinance as yf

# 请核对代码: SPCX(SpaceX)、SKHY(美股海力士)若取不到数据会自动跳过
# SOXX = 费城半导体指数对应ETF(iShares)；如果你说的是3倍杠杆版，把 SOXX 改成 SOXL
TICKERS = ["SPY", "QQQ", "NVDA", "META", "TSLA", "SPCX", "TSM", "ICE", "INFL",
           "GEV", "GOOGL", "COHR", "SKHY", "BABA", "PDD", "DRAM", "SMH", "SOXX"]
MAX_DAYS = 90
RATE = 0.04  # 无风险利率，用于估算价内概率


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def itm_prob(spot, k, iv, t, is_call):
    """Black-Scholes N(d2) 估算到期价内概率"""
    if not iv or iv <= 0 or t <= 0:
        return None
    d2 = (math.log(spot / k) + (RATE - iv * iv / 2) * t) / (iv * math.sqrt(t))
    return ncdf(d2) if is_call else ncdf(-d2)


def num(v):
    try:
        v = float(v)
        return None if math.isnan(v) else round(v, 4)
    except Exception:
        return None


def side(r, spot, t, is_call):
    bid, ask, last = num(r.get("bid")), num(r.get("ask")), num(r.get("lastPrice"))
    mid = round((bid + ask) / 2, 4) if bid is not None and ask else last
    iv = num(r.get("impliedVolatility"))
    p = itm_prob(spot, r["strike"], iv, t, is_call)
    return {"bid": bid, "ask": ask, "last": last, "mid": mid,
            "chg": num(r.get("change")), "oi": num(r.get("openInterest")),
            "itm": round(p, 4) if p is not None else None}


def fetch(sym):
    tk = yf.Ticker(sym)
    spot = num(tk.fast_info["last_price"])
    prev = num(tk.fast_info["previous_close"])
    today = dt.date.today()
    out = {"spot": spot, "chg": round(spot / prev - 1, 4) if prev else None, "expiries": []}
    for e in tk.options:
        dte = (dt.date.fromisoformat(e) - today).days
        if dte < 0 or dte > MAX_DAYS:
            continue
        ch = tk.option_chain(e)
        t = max(dte, 0.5) / 365
        calls = {r["strike"]: r for _, r in ch.calls.iterrows()}
        puts = {r["strike"]: r for _, r in ch.puts.iterrows()}
        rows = []
        for k in sorted(set(calls) | set(puts)):
            c, p = calls.get(k), puts.get(k)
            iv = num((c if c is not None else p).get("impliedVolatility"))
            rows.append({"k": float(k), "iv": iv,
                         "c": side(c, spot, t, True) if c is not None else None,
                         "p": side(p, spot, t, False) if p is not None else None})
        out["expiries"].append({"date": e, "dte": dte, "rows": rows})
    return out


def main():
    data = {"updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "tickers": {}}
    for s in TICKERS:
        try:
            data["tickers"][s] = fetch(s)
            print("OK  ", s, len(data["tickers"][s]["expiries"]), "个到期日")
        except Exception as ex:
            print("跳过", s, "->", ex)
    with open("data.js", "w", encoding="utf-8") as f:
        f.write("window.OPTIONS_DATA = " + json.dumps(data, ensure_ascii=False) + ";")
    print("已生成 data.js，刷新 dashboard.html 即可")


if __name__ == "__main__":
    main()
