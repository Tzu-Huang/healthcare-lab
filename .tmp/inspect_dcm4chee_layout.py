import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(".tmp/dcm4chee-layout")
OUT.mkdir(parents=True, exist_ok=True)
BASE_URL = os.environ.get("INSPECT_BASE_URL", "http://127.0.0.1:5000")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for width, height in ((1440, 900), (1024, 768), (768, 900)):
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        page.locator('[data-nav-target="dcm4chee-view"]').click()
        page.wait_for_timeout(1500)

        # Expand patient/result disclosure widgets so nested tables are measurable.
        page.locator("#dcm4chee-view details").evaluate_all(
            "(items) => items.forEach((item) => item.open = true)"
        )
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / f"page-{width}.png"), full_page=True)

        report = page.locator("#dcm4chee-view").evaluate(
            """(root) => {
              const rootRect = root.getBoundingClientRect();
              const visible = (el) => {
                const s = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
              };
              const describe = (el) => {
                const r = el.getBoundingClientRect();
                const ancestors = [];
                let p = el.parentElement;
                while (p && p !== root) {
                  const s = getComputedStyle(p);
                  const pr = p.getBoundingClientRect();
                  if (/hidden|clip/.test(s.overflow + s.overflowX + s.overflowY)) {
                    ancestors.push({
                      selector: p.id ? '#' + p.id : '.' + [...p.classList].join('.'),
                      left: Math.round(pr.left), right: Math.round(pr.right),
                      overflow: `${s.overflow}/${s.overflowX}/${s.overflowY}`
                    });
                  }
                  p = p.parentElement;
                }
                return {
                  tag: el.tagName,
                  text: (el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 90),
                  className: el.className,
                  left: Math.round(r.left), right: Math.round(r.right),
                  top: Math.round(r.top), bottom: Math.round(r.bottom),
                  outsideRoot: r.left < rootRect.left || r.right > rootRect.right,
                  clippedBy: ancestors.filter(a => r.left < a.left || r.right > a.right)
                };
              };
              return {
                root: {left: Math.round(rootRect.left), right: Math.round(rootRect.right),
                       scrollWidth: root.scrollWidth, clientWidth: root.clientWidth},
                buttons: [...root.querySelectorAll('button')].filter(visible).map(describe),
                tables: [...root.querySelectorAll('table')].filter(visible).map(describe),
                horizontalScrollers: [...root.querySelectorAll('*')].filter(el =>
                  visible(el) && el.scrollWidth > el.clientWidth + 2
                ).map(el => ({
                  selector: el.id ? '#' + el.id : '.' + [...el.classList].join('.'),
                  scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
                  overflowX: getComputedStyle(el).overflowX
                })).slice(0, 30)
              };
            }"""
        )
        (OUT / f"report-{width}.txt").write_text(repr(report), encoding="utf-8")
        print(width, report)
        page.close()
    browser.close()
