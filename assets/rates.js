// 划算 — 利率参考数据（v3.12）
// 更新方式：TRAE 定时任务「划算利率每周更新」每周一自动搜索并更新本文件；手动更新时保持结构不变。
// 数据结构：window.HUASUAN_RATES = { updatedAt, source, bonds: {label, note, items}, deposits: {label, note, items} }
// items 元素：{ term: '期限', rate: 年利率百分比数字 }
window.HUASUAN_RATES = {
  updatedAt: '2026-08-23',
  source: '财政部储蓄国债发行公告 · 国有大行官网挂牌利率',
  bonds: {
    label: '储蓄国债',
    note: '2026年第五、六期（凭证式）',
    items: [
      { term: '3年', rate: 1.63 },
      { term: '5年', rate: 1.70 }
    ]
  },
  deposits: {
    label: '定期存款 · 整存整取',
    note: '国有大行挂牌',
    items: [
      { term: '3个月', rate: 0.65 },
      { term: '6个月', rate: 0.85 },
      { term: '1年', rate: 0.95 },
      { term: '2年', rate: 1.05 },
      { term: '3年', rate: 1.25 },
      { term: '5年', rate: 1.30 }
    ]
  }
};
