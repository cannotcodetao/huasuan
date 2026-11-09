#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按指定日收盘价重算「股东回馈」表的最低入场成本，并修掉几处硬错误。

用法：
    python _tools/recalc_cost.py            # 预览差异，不改文件
    python _tools/recalc_cost.py --write    # 真正写入 index.html

价格来源：腾讯自选股行情快照（data_quote），A股/港股为当日收盘价。
口径（必须与页面 sr__meta 里的说明一致）：
    A股   = 门槛股数 × 收盘价，A股最低 5 元佣金未计入（占比 <2%）
    港股   = 碎股市值 + 单边最低佣金 50 港元
            碎股市值只有 1–3 港元，50 港元佣金是成本主体，不计会严重误导
    无门槛（「全体股东」）按 A股最小买入单位 100 股计
    台股  不设「最低入场成本」列，原样保留

刷新流程（换日期时只改 PRICE 和 AS_OF）：
    1. 用 data_quote 逐个取收盘价，更新 PRICE
    2. python _tools/recalc_cost.py          核对差异
    3. python _tools/recalc_cost.py --write  写入
    4. 同步改页面 sr__meta 里的 AS_OF 日期
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---- 数据时点：改这里必须同步改 index.html 的 sr__meta ----
AS_OF = "2026-11-09"

P = Path(__file__).resolve().parent.parent / "index.html"
WRITE = "--write" in sys.argv

# 公司名 → (收盘价, 门槛股数)。股数取表格「最低持股门槛」列；
# 「全体股东」的按 A股最小买入单位 100 股计。
A_SHARES = {
    "恒顺醋业": (6.93, 100),
    "仲景食品": (18.22, 100),
    "盖世食品": (8.54, 100),
    "宋城演艺": (5.45, 100),
    "盈新发展": (2.63, 100),
    "千味央厨": (30.78, 100),
    "好想你": (9.98, 100),
    "莲花控股": (8.77, 500),
    "峨眉山A": (10.22, 500),
    "天目湖": (8.20, 100),
    "苏盐井神": (8.85, 100),
    "佳禾食品": (9.11, 100),
    "全聚德": (9.02, 100),
    "华大基因": (38.39, 100),
    "舍得酒业": (33.18, 100),
    "迎驾贡酒": (44.94, 100),
    "寿仙谷": (13.64, 100),
    "东北制药": (4.41, 500),
    "海峡股份": (5.57, 100),
    "荣泰健康": (14.04, 100),
    "洽洽食品": (19.11, 100),
    "欢乐家": (16.64, 100),
    "爱朋医疗": (20.27, 1000),
    "五芳斋": (13.98, 1000),
    "得利斯": (3.76, 15000),
    "贵州茅台": (1444.99, 100),
    "五粮液": (74.74, 100),
    "洋河股份": (37.41, 100),
    "康冠科技": (21.99, 1000),
    "陈克明食品": (6.84, 7000),
    "劲仔食品": (9.29, 100),
}
# 港股：碎股即可参会，佣金按单边最低 50 港元计
HK_SHARES = {
    "周黑鸭": (0.93, 1),
    "奈雪的茶": (0.695, 4),
}
HK_MIN_COMMISSION = 50.0

CODE_FIX = {"盖世食品": "920826"}   # 原 835669 查无此票，北交所现用 920826


def money(n: float) -> str:
    """精确到元，千分位。"""
    return f"{round(n):,}"


def a_cost(price: float, shares: int) -> str:
    return "¥" + money(price * shares)


def hk_cost(price: float, shares: int) -> str:
    return "HK$" + money(price * shares + HK_MIN_COMMISSION)


s = P.read_text(encoding="utf-8")
start = s.index("    var DATA = {")
end = s.index("\n    };", start)
block = s[start:end]

diffs: list[str] = []
skipped: list[str] = []
out_lines: list[str] = []
market = None

for line in block.split("\n"):
    st = line.strip()
    m = re.match(r"^(a|hk|tw): \[$", st)
    if m:
        market = m.group(1)
        out_lines.append(line)
        continue
    if not (st.startswith('["') and st.endswith("],")):
        out_lines.append(line)
        continue

    rec = json.loads(st[:-1])
    if json.dumps(rec, ensure_ascii=False) != st[:-1]:
        sys.exit(f"[中止] JSON 往返不一致，不敢改写：{st[:80]}")

    # 台股没有「最低入场成本」这一列（10 列），原样保留
    if market == "tw" or len(rec) != 11:
        out_lines.append(line)
        continue

    name = rec[0]
    table = A_SHARES if market == "a" else HK_SHARES
    if name not in table:
        skipped.append(f"{market}:{name}")
        out_lines.append(line)
        continue

    price, shares = table[name]
    new_cost = a_cost(price, shares) if market == "a" else hk_cost(price, shares)
    if rec[6] != new_cost:
        diffs.append(f"  {name:<6} {rec[6]:<22} → {new_cost}")
        rec[6] = new_cost
    if name in CODE_FIX and rec[1] != CODE_FIX[name]:
        diffs.append(f"  {name:<6} 代码 {rec[1]} → {CODE_FIX[name]}")
        rec[1] = CODE_FIX[name]
    out_lines.append("        " + json.dumps(rec, ensure_ascii=False) + ",")

if skipped:
    sys.exit(f"[中止] 有行没匹配到价格，先补 PRICE 再跑：{skipped}")

print(f"成本口径基准日：{AS_OF}")
print(f"需改动 {len(diffs)} 处：")
print("\n".join(diffs) if diffs else "  （无）")

if not WRITE:
    print("\n[dry-run] 未写入。确认后加 --write。")
    sys.exit(0)

s = s[:start] + "\n".join(out_lines) + s[end:]
s = s.replace("version: '4.10',", "version: '4.11',", 1)
P.write_text(s, encoding="utf-8")
print(f"\n已写入 {P.name}，版本号 → 4.11")
