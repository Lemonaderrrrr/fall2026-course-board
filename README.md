# Fall 2026 课程总表

UCI Fall 2026 五门课的 deadline 看板，按星期排列。课程安排来自各课 syllabus，Canvas 日历每天自动合并进来。

- `index.html`：页面本体，syllabus 数据写在页面里，打开时读取 `data/canvas.json` 合并。
- `scripts/sync_canvas.py`：拉取 Canvas 日历 feed，只用 Python 标准库，输出 `data/canvas.json`（只包含标题、日期和课程，不含描述）。
- `.github/workflows/sync.yml`：每天 06:00（美西时间）运行同步脚本，有变化就提交，然后部署到 GitHub Pages。也可以在 Actions 页手动运行。

Canvas feed 链接存在 repo secret `CANVAS_FEED_URL` 里，不进代码库。

本地手动同步：

```bash
CANVAS_FEED_URL='<feed 链接>' python3 scripts/sync_canvas.py
```
