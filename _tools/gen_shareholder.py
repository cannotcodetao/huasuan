#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从「股东回馈」源 HTML 抽取表格数据，生成划算页面里的股东回馈板块。

只做三件事：
  1. 把三张表的每行抽成结构化数据（不改内容、不改措辞）
  2. 生成用划算设计系统渲染的 HTML + JS（不照搬源文件的蓝色系 CSS）
  3. 把 index.html 里的 SR_SECTION_PLACEHOLDER 替换掉

以后更新数据：改源 HTML（或直接改生成出来的 SR_DATA 数组），重跑本脚本。
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SRC = Path(r"C:/Users/24237/Downloads/股东回馈.html")
TARGET = Path(__file__).resolve().parent.parent / "index.html"
MARK = "<!-- ==== SR_SECTION_PLACEHOLDER ==== -->"

COLS = {
    "a": ["公司名称", "代码", "行业", "伴手礼内容", "大致价值", "最低持股门槛",
          "最低入场成本", "领取方式", "历史变化", "性价比评级", "来源"],
    "hk": ["公司名称", "代码", "行业", "伴手礼内容", "大致价值", "最低持股门槛",
           "最低入场成本", "领取方式", "历史变化", "性价比评级", "来源"],
    "tw": ["公司名称", "代码", "行业", "纪念品内容", "大致价值", "最低持股门槛",
           "领取方式", "历史变化", "性价比评级", "来源"],
}
TITLES = {"a": "A股", "hk": "港股", "tw": "台股"}


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def split_cells(row: str) -> list[str]:
    return re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S | re.I)


def parse_source(cell: str) -> dict:
    """来源列拆成 {t: 链接文字, u: url, a: 可访问性}"""
    m = re.search(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', cell, flags=re.S | re.I)
    acc = re.search(r'<span[^>]*class="acc"[^>]*>(.*?)</span>', cell, flags=re.S | re.I)
    out = {"u": "", "t": strip_tags(cell), "a": strip_tags(acc.group(1)) if acc else ""}
    if m:
        out["u"] = html.unescape(m.group(1)).strip()
        out["t"] = strip_tags(m.group(2))
    return out


def parse_market(src: str, key: str) -> list[list]:
    marker = f"<h3>{TITLES[key]}</h3>"
    i = src.find(marker)
    if i < 0:
        raise SystemExit(f"源文件里找不到 {marker}")
    tb = src.find("<tbody>", i)
    te = src.find("</tbody>", tb)
    body = src[tb:te]
    rows = re.findall(r"<tr>\s*(.*?)\s*</tr>", body, flags=re.S)
    want = len(COLS[key])
    out = []
    for r in rows:
        cells = split_cells(r)
        if len(cells) != want:
            raise SystemExit(
                f"{TITLES[key]} 有一行列数 {len(cells)}，期望 {want}：{strip_tags(r)[:60]}")
        rec = [strip_tags(c) for c in cells]
        rec[-1] = parse_source(cells[-1])
        out.append(rec)
    return out


def js(obj, indent=0) -> str:
    """极简 JSON 序列化（不依赖 json 的 ascii 转义，中文直接输出）"""
    import json
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def js_rows(data: dict) -> str:
    """每个公司一行 —— 保证生成结果可以直接手工改，而不是压成一条长线"""
    import json
    keys = ("a", "hk", "tw")
    out = ["{"]
    for k in keys:
        out.append(f'      {k}: [')
        for rec in data[k]:
            out.append("        " + json.dumps(rec, ensure_ascii=False) + ",")
        out.append("      ],")
    out.append("    }")
    return "\n".join(out)


def js_cols(cols: dict) -> str:
    import json
    out = ["{"]
    for k, v in cols.items():
        out.append(f'      {k}: ' + json.dumps(v, ensure_ascii=False) + ",")
    out.append("    }")
    return "\n".join(out)


def main() -> int:
    raw = SRC.read_text(encoding="utf-8")
    data = {k: parse_market(raw, k) for k in ("a", "hk", "tw")}
    total = sum(len(v) for v in data.values())
    print(f"抽到 A股 {len(data['a'])} · 港股 {len(data['hk'])} · 台股 {len(data['tw'])}，合计 {total} 行")

    section = build_section(data, total)
    page = TARGET.read_text(encoding="utf-8")
    if MARK in page:
        # 首次生成：替换占位符
        page = page.replace(MARK, section)
    else:
        # 二次及以后：原地替换已生成的整块，保证脚本可反复执行
        pat = re.compile(r"\n[ \t]*<!-- =+ v4\.6 股东回馈.*?\n[ \t]*</script>", re.S)
        if not pat.search(page):
            raise SystemExit("找不到占位符，也找不到已生成的股东回馈区块")
        page = pat.sub("\n" + section, page, count=1)
    TARGET.write_text(page, encoding="utf-8")
    print(f"已写入 {TARGET}（{len(section):,} 字符）")
    return 0


def pick(name: str, code: str, desc: str) -> str:
    return (f'<div class="sr__pick"><h4>{html.escape(name)} {html.escape(code)}</h4>'
            f'<p>{html.escape(desc)}</p></div>')


def build_section(data: dict, total: int) -> str:
    cols_js = js_cols(COLS)
    data_js = js_rows(data)

    tiers_top = "".join([
        pick("恒顺醋业", "600305", "100股门槛，约720元入场；礼包电商价约98.9元；可邮寄，无需现场。礼品价值占比约14%-21%。"),
        pick("仲景食品", "300908", "100股门槛；西洋参/香菇酱礼包；线上申领邮寄，连续多年。礼品价值占比约3%-5%。"),
        pick("宋城演艺", "300144", "100股门槛，约800元入场；千古情免票+3名家属5折；体验价值高，需现场使用。"),
        pick("盈新发展", "000620", "门槛极低（约200元）；U盘/酒店抵扣券/开放日；上市30周年活动，可邮寄。"),
        pick("盖世食品", "835669", "无持股数量要求，全体股东可领；消暑礼盒；2022年以来4次回馈，可邮寄。"),
    ])
    tiers_feat = "".join([
        pick("华大基因", "300676", "肠道健康检测礼盒，健康属性强；需持股满1年，限量先到先得。"),
        pick("东北制药", "000597", "「栖芳源」化妆品买1得4+9折，医药跨界美妆的差异化回馈。"),
        pick("周黑鸭", "01458", "游轮晚宴+Venchi巧克力伴手礼，股东大会体验型回馈的代表。"),
        pick("中钢", "2002", "钛金属冷水瓶（380ml/98g），台股纪念品质感代表，零股可领。"),
    ])
    tiers_risk = "".join([
        pick("贵州茅台", "600519", "2024年2瓶50ml飞天+冰淇淋券→2025年笔记本+笔→2026年仅笔记本+笔，持续缩水。"),
        pick("洋河股份", "002304", "2025年取消伴手礼酒，改为笔记本+笔，晚宴从圆桌改为自助餐。"),
        pick("洽洽食品", "002557", "2024年8月有定制礼盒，2026年2月互动易明确回复「暂无」相关活动。"),
        pick("五粮液", "000858", "股东优惠价被指高于电商平台，折扣权实际价值极低，参与前需比价。"),
    ])
    tips = [
        "勿为伴手礼而买股票，伴手礼是锦上添花，不是收益来源。峨眉山A宣布股东免票后股价涨停，但随后冲高回落。",
        "算清全成本：买卖佣金（A股最低5元）、印花税、现场参会差旅费、邮寄等待时间成本。",
        "优先选择「可邮寄 + 低门槛 + 价值明确」的活动，如恒顺醋业、仲景食品、盖世食品。",
        "警惕折扣权陷阱：参与折扣类活动前，务必先对比主流电商平台实际到手价（五粮液案例）。",
        "注意隐性门槛：华大基因要求持股满1年，陈克明食品要求7000股以上，得利斯要求15000股以上。",
        "港股碎股佣金可能远高于A股最低5元，奈雪的茶4股参会需单独核算买卖佣金成本。",
        "台股零股领取需注意最后买进日、电子投票、代领规则，部分公司要求亲自出席。",
        "历史连续性比单次活动更重要，警惕礼品缩水与活动取消，不应将伴手礼作为持仓理由。",
    ]
    tips_html = "".join(f"<li>{html.escape(t)}</li>" for t in tips)

    return f'''  <!-- ========== v4.6 股东回馈（数据来自公开信息整理，样式按划算设计系统重做） ========== -->
  <div class="layout-center srblock">
    <div class="col-head">
      <h2 class="col-head__title">股东回馈</h2>
      <span class="col-head__eyebrow">SHAREHOLDER PERKS</span>
    </div>

    <p class="sr__lead">
      A股 / 港股 / 台股上市公司给股东发的伴手礼、专属优惠与体验型回馈。
      共收录 <b id="srTotal">0</b> 条，按性价比评级排序，点开对应市场展开明细。
    </p>

    <div class="sr__disc">
      <b>不构成投资建议，不承诺收益。</b>
      股价波动才是持仓损益的核心，伴手礼不应被夸大为核心收益来源。
      价值估算依据电商价／公司公告／媒体报道；活动是否延续、门槛是否调整，一律以公司最新公告为准。
    </div>

    <details class="sr__fold" id="srFoldA">
      <summary>A股 <span class="sr__cnt">按性价比评级排序</span></summary>
      <div class="sr__scroll">
        <table class="sr__tab" id="srTableA" aria-label="A股股东回馈总表">
          <caption>A股上市公司股东回馈总表（按性价比评级排序）</caption>
        </table>
      </div>
    </details>

    <details class="sr__fold" id="srFoldHk">
      <summary>港股 <span class="sr__cnt">含股东大会现场体验型回馈</span></summary>
      <div class="sr__scroll">
        <table class="sr__tab" id="srTableHk" aria-label="港股股东回馈总表">
          <caption>港股上市公司股东回馈总表</caption>
        </table>
      </div>
    </details>

    <details class="sr__fold" id="srFoldTw">
      <summary>台股 <span class="sr__cnt">股东会纪念品惯例</span></summary>
      <div class="sr__scroll">
        <table class="sr__tab" id="srTableTw" aria-label="台股股东会纪念品总表">
          <caption>台股股东会纪念品惯例（零股与代领规则另见实操提醒）</caption>
        </table>
      </div>
    </details>

    <h3 class="sr__sub">性价比最高梯队</h3>
    <div class="sr__picks">{tiers_top}</div>

    <h3 class="sr__sub">品类最有特色</h3>
    <div class="sr__picks">{tiers_feat}</div>

    <h3 class="sr__sub">有变化风险的公司</h3>
    <div class="sr__picks">{tiers_risk}</div>

    <h3 class="sr__sub">给普通散户的实操提醒</h3>
    <ol class="sr__tips">{tips_html}</ol>

    <p class="sr__meta">
      数据来源：巨潮资讯、上交所、深交所、港交所披露易、公司公告／公众号、互动易、
      证券时报、中国证券报、上海证券报、新华财经、中时新闻网等公开渠道。
      各条来源见表格「来源」列；✅ 可直接访问 · ⚠️ 需站内搜索 · ❌ 已失效。
      <br>本区块为公开信息整理，数据时点以各条来源的公告日期为准，本页不另行标注「截至今日」。
    </p>
  </div>

  <script>
  (function () {{
    "use strict";
    var COLS = {cols_js};
    var DATA = {data_js};
    /* 列名 → 列宽 class。三张表列顺序不同（台股少「最低入场成本」），
       用列名映射比 nth-child 稳，加列时不用重算序号 */
    var COL_CLASS = {{
      "公司名称": "c-name", "代码": "c-code", "行业": "c-ind",
      "伴手礼内容": "c-item", "纪念品内容": "c-item",
      "大致价值": "c-val", "最低持股门槛": "c-thr", "最低入场成本": "c-cost",
      "领取方式": "c-how", "历史变化": "c-hist",
      "性价比评级": "c-rate", "来源": "c-src"
    }};
    var BADGE = [
      [["待核实"], "todo"],
      [["中高"], "midhigh"],
      [["高"], "high"],
      [["中"], "mid"],
      [["低", "—", "-"], "low"]
    ];

    function esc(s) {{
      return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {{
        return {{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[c];
      }});
    }}

    function badge(text) {{
      var t = String(text || "").trim(), cls = "mid";
      for (var i = 0; i < BADGE.length; i++) {{
        for (var j = 0; j < BADGE[i][0].length; j++) {{
          if (t.indexOf(BADGE[i][0][j]) === 0) {{ cls = BADGE[i][1]; i = BADGE.length; break; }}
        }}
      }}
      return '<span class="sr__badge sr__badge--' + cls + '">' + esc(t || "—") + "</span>";
    }}

    function cellHtml(val, isLast) {{
      if (isLast && val && typeof val === "object") {{
        var a = val.u
          ? '<a href="' + esc(val.u) + '" target="_blank" rel="noopener noreferrer">' + esc(val.t) + "</a>"
          : esc(val.t);
        return '<td class="sr__url">' + a + (val.a ? '<span class="sr__acc">' + esc(val.a) + "</span>" : "") + "</td>";
      }}
      return "<td>" + esc(val) + "</td>";
    }}

    function render(key, tableId) {{
      var cols = COLS[key], rows = DATA[key] || [], tbl = document.getElementById(tableId);
      if (!tbl) return;
      var h = "<thead><tr>";
      for (var i = 0; i < cols.length; i++) {{
        h += '<th class="' + (COL_CLASS[cols[i]] || "") + '">' + esc(cols[i]) + "</th>";
      }}
      h += "</tr></thead><tbody>";
      for (var r = 0; r < rows.length; r++) {{
        h += "<tr>";
        for (var c = 0; c < cols.length; c++) {{
          var v = rows[r][c];
          if (c === cols.length - 2) {{ h += '<td class="is-rate">' + badge(v) + "</td>"; }}
          else {{ h += cellHtml(v, c === cols.length - 1); }}
        }}
        h += "</tr>";
      }}
      h += "</tbody>";
      tbl.innerHTML = h;
    }}

    function boot() {{
      render("a", "srTableA");
      render("hk", "srTableHk");
      render("tw", "srTableTw");
      var n = (DATA.a || []).length + (DATA.hk || []).length + (DATA.tw || []).length;
      var el = document.getElementById("srTotal");
      if (el) el.textContent = n;
    }}

    if (document.readyState === "loading") {{
      document.addEventListener("DOMContentLoaded", boot);
    }} else {{
      boot();
    }}
  }})();
  </script>

'''

if __name__ == "__main__":
    sys.exit(main())
