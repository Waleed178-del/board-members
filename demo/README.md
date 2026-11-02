# Board Room Simulator

| File | Use |
|---|---|
| `index.html` | Open this on any static server (GitHub Codespaces port, `python3 -m http.server`, GitHub Pages). Full HTML document with UTF-8 declared. |
| `board_room.html` | Source for the claude.ai artifact. No document skeleton, because the artifact publisher adds one. |
| `build_standalone.py` | Regenerates `index.html` from `board_room.html`. Run it after every edit. |

```bash
python3 demo/build_standalone.py
```

```bash
cd demo && python3 -m http.server 8000
```

Then open `http://localhost:8000/` (in Codespaces, the forwarded port 8000).

The page loads React, ReactDOM and htm from cdnjs and jsDelivr, and fonts from Google Fonts. It needs internet access in the browser.
