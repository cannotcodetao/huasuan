#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按「性价比评级」口径全表重算，并按评级重排。

用法：
    python _tools/recalc_rating.py            # 预览差异，不改文件
    python _tools/recalc_rating.py --write    # 真正写入 index.html

口径（与 doc/股东回馈更新文档.md 第四节、页面尾注一致）：

    价值     = 表格「大致价值」里所有区间的中位数之和（A股与港股各自本币）
    占比     = 价值 ÷ 最低入场成本

    硬性判低（命中即定「低」，不再看占比）
        H1 门槛 ≥ 1000 股
        H2 占比 < 0.5%
        H3 活动已停办 / 名不副实（命中页面 RISK 里的「已无相关活动」「取消」「高于电商」）

    分档
        占比 > 2%     → 从「高」起评，按短板逐项降一档（最低降到「中」）
        0.5%–2%       → 「中」
        价值无法量化   → 「待核实」（写了「折扣节省有限」这类定性结论的，直接「低」）

    短板（每项降一档）
        S1 门槛 > 100 股，或带附加条件（如「100股+持股满1年」）
           「全体股东」「碎股」不算短板：按 A股最小买入单位 100 股计成本
        S2 必须到现场（景区核验 / 现场凭证 / 股东会现场）
           体验型场景不扣——到场本身就是回馈的一部分，见 EXPERIENCE
        S3 只是折扣权（价值列以「折扣节省」开头，领完还得再花钱买）

评级顺序：高 → 中高 → 中 → 低 → 待核实，同档内保持原有相对顺序（稳定排序）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "index.html"
WRITE = "--write" in sys.argv

RANK = {"高": 0, "中高": 1, "中": 2, "低": 3, "待核实": 4}
SCORE_NAME = {3: "高", 2: "中高", 1: "中"}

# 到场即回馈本身的场景：景区免票、游轮晚宴。这些不扣 S2，
# 否则「去景区玩」会被当成差旅成本，把最好的几条评成中档。
EXPERIENCE = {"宋城演艺", "峨眉山A", "天目湖", "周黑鸭"}

STOP_WORDS = ("已无相关活动", "取消", "高于电商")   # 命中 RISK 即判低（H3）


def money(s: str) -> float:
    t = str(s).replace("HK$", "").replace("¥", "").replace(",", "").strip()
    return float(t)


def parse_value(cell: str) -> tuple[float | None, bool, bool]:
    """→ (价值中位数, 是否只是折扣权, 是否「待核实」)"""
    t = str(cell).strip()
    if "待核实" in t:
        return None, False, True
    if "折扣节省有限" in t:          # 有结论但量化不了 → 按低处理
        return None, False, False
    discount = t.startswith("折扣节省")
    work = re.sub(r"(?:19|20)\d{2}\s*年", "", t)      # 去掉「2026年」，别当金额
    total = 0.0
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*[-–~—至]\s*(\d+(?:\.\d+)?)", work):
        total += (float(m.group(1)) + float(m.group(2))) / 2
    work = re.sub(r"(\d+(?:\.\d+)?)\s*[-–~—至]\s*(\d+(?:\.\d+)?)", "", work)
    for m in re.finditer(r"\d+(?:\.\d+)?", work):
        total += float(m.group(0))
    return (total or None), discount, False


def parse_shares(cell: str) -> tuple[int | None, bool]:
    """→ (门槛股数, 是否有附加条件)"""
    t = str(cell).strip()
    if "全体股东" in t or "无持股数量要求" in t:
        return 100, False
    m = re.search(r"(\d[\d,]*)\s*股", t)
    if not m:
        return None, False
    n = int(m.group(1).replace(",", ""))
    extra = ("+" in t) or ("满1年" in t)
    return n, extra


def main() -> int:
    s = P.read_text(encoding="utf-8")

    # RISK 只从页面读，不另存一份，避免两处对不上
    mr = re.search(r"var RISK = \{(.*?)\n    \};", s, re.S)
    if not mr:
        sys.exit("[中止] 找不到 var RISK")
    risk = json.loads("{" + mr.group(1).rstrip().rstrip(",") + "}")

    start = s.index("    var DATA = {")
    end = s.index("\n    };", start)
    block = s[start:end]

    market = None
    groups: dict[str, list] = {}          # market → [rec]
    rows: list[tuple[str, str, object]] = []   # (kind, market, payload)

    for line in block.split("\n"):
        st = line.strip()
        m = re.match(r"^(a|hk|tw): \[$", st)
        if m:
            market = m.group(1)
            groups[market] = []
            rows.append(("hdr", market, line))
            continue
        if st == "],":
            rows.append(("end", market, line))
            continue
        if st.startswith('["') and st.endswith("],"):
            rec = json.loads(st[:-1])
            if json.dumps(rec, ensure_ascii=False) != st[:-1]:
                sys.exit(f"[中止] JSON 往返不一致，不敢改写：{st[:80]}")
            groups[market].append(rec)
            rows.append(("row", market, rec))
            continue
        rows.append(("other", market, line))

    diffs: list[str] = []
    bad: list[str] = []

    for mk in ("a", "hk"):
        for rec in groups[mk]:
            name, cost = rec[0], money(rec[6])
            val, discount, unknown = parse_value(rec[4])
            shares, extra = parse_shares(rec[5])
            if shares is None:
                bad.append(f"{mk}:{name}（门槛解析不出股数：{rec[5]}）")
                continue

            why = ""
            if unknown or val is None:
                rating = "待核实" if unknown else "低"
                why = "价值不可量化"
            elif shares >= 1000:
                rating = "低"
                why = f"H1 门槛 {shares} 股"
            elif val / cost < 0.005:
                rating = "低"
                why = f"H2 占比 {val / cost:.2%}"
            elif any(w in risk.get(name, "") for w in STOP_WORDS):
                rating = "低"
                why = "H3 " + risk[name]
            else:
                ratio = val / cost
                if ratio <= 0.02:
                    rating = "中"
                    why = f"占比 {ratio:.2%}"
                else:
                    pen, tags = 0, []
                    if shares > 100 or extra:
                        pen += 1
                        tags.append(f"S1 门槛 {shares} 股" + ("+条件" if extra else ""))
                    onsite = ("现场" in rec[7]) or ("参会" in rec[7])
                    if onsite and name not in EXPERIENCE:
                        pen += 1
                        tags.append("S2 需到场")
                    if discount:
                        pen += 1
                        tags.append("S3 仅折扣")
                    rating = SCORE_NAME[max(1, 3 - pen)]
                    why = f"占比 {ratio:.2%}" + ("；" + "、".join(tags) if tags else "")
            if rec[9] != rating:
                diffs.append(f"  {name:<7}{str(rec[9]):<12}→ {rating:<6}{why}")
            rec[9] = rating

    if bad:
        sys.exit("[中止] 有行解析失败，先把门槛/价值写规范再跑：\n  " + "\n  ".join(bad))

    print(f"需改动 {len(diffs)} 行评级：")
    print("\n".join(diffs) if diffs else "  （无）")

    order = {mk: sorted(groups[mk], key=lambda r: RANK[r[9]]) for mk in ("a", "hk")}
    moved = sum(1 for mk in ("a", "hk")
                if [r[0] for r in order[mk]] != [r[0] for r in groups[mk]])
    print(f"\n重排：{'A股' if moved else '无需重排'}，共 {sum(len(v) for v in order.values())} 行按评级降序")

    if not WRITE:
        print("\n[dry-run] 未写入。确认后加 --write。")
        return 0

    out: list[str] = []
    seen: dict[str, int] = {}
    for kind, mk, payload in rows:
        if kind == "hdr":
            seen[mk] = 0
            out.append(payload)
        elif kind == "row":
            rec = order[mk][seen[mk]] if mk in order else payload
            seen[mk] += 1
            out.append("        " + json.dumps(rec, ensure_ascii=False) + ",")
        elif kind == "end":
            # 兜底：行数对不上说明分组出错，宁可中止也不要写出半截表
            if mk in order and seen.get(mk, 0) != len(order[mk]):
                sys.exit(f"[中止] {mk} 段行数不匹配（写 {seen.get(mk, 0)} / 应有 {len(order[mk])}）")
            out.append(payload)
        else:
            out.append(payload)

    page = s[:start] + "\n".join(out) + s[end:]
    page = page.replace("version: '4.11',", "version: '4.12',", 1)
    P.write_text(page, encoding="utf-8")
    print(f"\n已写入 {P.name}，版本号 → 4.12")
    return 0


if __name__ == "__main__":
    sys.exit(main())
