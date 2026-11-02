#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在部署产物里注入备案页脚（幂等，只改 _release/，不碰源文件）。

用法：
    python .github/scripts/inject_beian.py _release
    python .github/scripts/inject_beian.py _release --check   # 只报告，不写盘

规矩（来自 my-sites/_templates/footer-beian.html）：
  1. 编号必须与 cannotcode.cn 真实对应
  2. 图标必须是官方徽章，base64 内嵌，不引外链、不自绘 SVG
  3. 版式：备案单独一行，底部居中；插在 </footer> 前，与页脚同容器

设计取舍：颜色写成十六进制而非 var(--line) 之类 —— 划算各页的主题变量名不统一
（index/calculator 用 --color-border，freedom.html 用 --line），
留悬空 var() 会让整条规则失效、页脚变成无样式的裸链接。
这里直接用设计系统的真实色值：border #E8E6E1 / muted #8A8A8A / primary #2D4A3E。
"""
from __future__ import annotations

import re

import sys
from pathlib import Path

ICP = "粤ICP备2026107109号-1"
ICP_HREF = "https://beian.miit.gov.cn/"
GA = "浙公网安备33019202003186号"
GA_HREF = "https://www.beian.gov.cn/portal/registerSystemInfo?recordcode=33019202003186"

# 官方徽章（20×20 原图经 Edge canvas 原尺寸重编码，1321 B），显示 14px
GH_SRC = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAE3klEQVR4AXzSfWwTZRwH8O9dr9eu68t1fadV3JiMKS8TytsYS1g0QNx4MxnwB0zMBOVFgi8kCBIJ/EGiEpSJkkUjIxgHYqJsEgGH4zVAkMGAOcbaubV76Xt7fW+v53WERpTwS37J3eWez3P3e74knlI8bzdGHrSsbWnYef3EJx/e8tw+tpHneyxPWYIngnzsj3ndP+9o/u7trfbm3TsO3bh41tpl65h86vgPBxrX77LfO77zJz7eUf0k+H8gz/PStkPfttW9eaY2HP9bOl4uQr10BG9JB1A+24CC2Qaqft2ZpacP7D0pvCv5L/oYyPNeS+Lm9t8+PxrEyvoivG4JQXXoLrzdHLy9HILVX2Mx14nNTSvQeCIFvnv/cWEs0n+jOTDB95X2t2zvrazurGSKDdig7YT9aAjkMww4NgkkMiB0DC5vuoRa2U0Y5ryEl6tba9wXG23uv/aXPEJzIB1tlZ/sVtDXBq1YaGUR7hCw/iAIRgKJj0P80gjEhRpIwzF4Dl/FsvlJtD14AUcucCYVGch7DPTeOmfhrp3blyGE51QUSnYQoWFAzKUAXxzEOBnoaQzIoQhoZOCxx2AuSAAEAX+YhFhH7+NjgUIIRQoNh+3X11JOZ4VaTgNpCXiTCdoKI8LgwZZrwK20QL6rDLLNk0HqZNBP0yISTQI8D5NeBjg65nmH2t/IWqNgfr66NMSmUKSLA1INTl+VgapSwlszFpyTBXE7gmjrCFL2AOgPKlCwZQp+bPIL6/NRNolCpNeFeL9tNJ+jIOcbqgn5KUy0sLDMoHHwSD7a9zpQNt0ElUyB6F0/Mq4E4p1+KJwB3Nl9H180SWAoYzDJHITHmUDa31Uh7PAw2CQVYdgQCaX7Pmrnc0in5Ei1DEPTfAOkWYykToSMnoK2ygRTmw2exjuIJEVYtkgMhbcHbIiCSCES58A82bNnVSVScAYz1sxkAbMOB1GKlgEK3tYeEMIXxn55APaqCzfVJhwjnwcYBmtmuZBWWMC8aECe2tKaAwFCz4d4DPaymKi3Y8/7+WihKrGYXYGK4eXYOzQHDbG5mNpqhfV8Ob7KVOHd9VJML3bCNeAD4lHwqfAUCDU6Q4pJWdMKAyLDaTjau/BOxR3cO0ugYWsUG7eVYu2XRmzaR2JJnRm1i6R4b6sM2xf0YeRyH6KD2XwRoNT0BMF7OEP15Jo6xbNJiDUJhDgZBprPoIjqw4Z6CgfqLmBBkRvjRFEc2dKP5sMZfLqqC8H2DniFPNMGBSRmNeT6GctyoEQ+83vDrJ2rFMXqoLpMCU6lg+2aA/6QGJ4BFVwe4a/kagSFzUKONOyXvUhrjNCWl0DEmL2ysUtfEatfPZ8DsxesJ+6MD8tiIokQh6piMBPGgGNDgIwQFjGQqKRIBsLw/WmDdKwG2srxyCSFKDk9fDwcxKManWH2Rsyf36afqjCKhVNMBDPIcJTQIsTdwqnzGSS9QYR73CCy6SAIxIc8EOeRMMw1aSXy8Lqske0cmC+pWsLGmIaowxGhRQEo9WmIiShoIgVRIgA+FoNighbKYiVIOgxKRYNQG/vTVNlHcr1veRbLdg4kxlij+pIdmyK9Y54buJ6/+tap4W8CbvJKyEV3xljKCYnGyQ5RVxIRze+igoWf+RyFCwuaUKg2rt5DEB9nsli2/wEAAP//YXzz/gAAAAZJREFUAwBE4gfiCTe1WQAAAABJRU5ErkJggg=="
)

STYLE = """<style id="beian-style">
/* 备案页脚 · cannotcode.cn 站群统一片段，只在部署产物里注入，源码不含 */
.beian{margin-top:18px;padding-top:14px;border-top:1px solid #E8E6E1;display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:6px 18px;font-family:"JetBrains Mono",Consolas,monospace;font-size:11px;letter-spacing:.1em}
.beian a{display:inline-flex;align-items:center;gap:5px;color:#8A8A8A;text-decoration:none;transition:color .18s ease}
.beian a:hover{color:#2D4A3E}
.beian a img{display:block;width:14px;height:14px}
</style>
"""

BLOCK = (
    '<div class="beian">'
    f'<a href="{ICP_HREF}" target="_blank" rel="noopener noreferrer">{ICP}</a>'
    f'<a href="{GA_HREF}" target="_blank" rel="noopener noreferrer" title="公安联网备案查询">'
    f'<img src="{GH_SRC}" width="14" height="14" alt="公安备案图标">{GA}</a>'
    "</div>"
)


def _block_for(html: str) -> str:
    """按页面的内容列宽度包一层，避免备案行横跨整个视口而与正文错位。

    · 划算多数页：<footer class="footer"> 是通栏块，列宽由内部的
      .footer__inner(.container) 提供 → 备案行要自己补一层 .container
    · freedom.html：<footer class="wrap"> 本身就是 1200px 列
      → 再包一层只是在列内再缩 24px，横向错位，所以不包
    """
    m = re.search(r"<footer[^>]*>", html)
    tag = m.group(0) if m else ""
    if "wrap" in tag or "container" in tag:
        return BLOCK
    if 'class="container' in html:
        return f'<div class="container">{BLOCK}</div>'
    return BLOCK


def inject_one(path: Path, check: bool) -> str:
    """返回 'injected' / 'already' / 'no-anchor'。"""
    html = path.read_text(encoding="utf-8", errors="surrogateescape")
    if ICP in html:
        return "already"

    anchor = "</footer>"
    if anchor not in html:
        anchor = "</body>"
    if anchor not in html:
        return "no-anchor"

    out = html.replace(anchor, "  " + _block_for(html) + "\n  " + anchor, 1)

    if "</head>" in out and 'id="beian-style"' not in out:
        out = out.replace("</head>", STYLE + "</head>", 1)

    if not check:
        path.write_text(out, encoding="utf-8", errors="surrogateescape")
    return "injected"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    if not args:
        print("用法: python inject_beian.py <产物目录> [--check]", file=sys.stderr)
        return 2

    root = Path(args[0])
    if not root.is_dir():
        print(f"[{chr(10007)}] 目录不存在: {root}", file=sys.stderr)
        return 2

    pages = sorted(p for p in root.rglob("*.html"))
    should = len(pages)
    tally = {"injected": 0, "already": 0, "no-anchor": 0}

    for p in pages:
        r = inject_one(p, check)
        tally[r] = tally.get(r, 0) + 1
        mark = {"injected": "OK", "already": "=", "no-anchor": "!"}[r]
        rel = p.relative_to(root).as_posix()
        print(f"  [{mark}] {rel}  ({p.stat().st_size} B)  {r}")

    covered = tally["injected"] + tally["already"]
    print(f"\n应注入 {should} 页 / 已覆盖 {covered} 页 "
          f"(本次新注入 {tally['injected']}，原本已有 {tally['already']})")
    if tally["no-anchor"]:
        print(f"缺少 </footer> 与 </body> 锚点 {tally['no-anchor']} 页 —— 需人工处理")
        return 1
    if covered != should:
        print("页数不相等，拒绝宣告完成")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
