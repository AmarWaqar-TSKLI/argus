"""Demo target app with intentionally injected bugs.

Ground truth lives in BUGS.md — Argus's recall is measured against it.
Run: python demo_app/app.py  (serves on http://127.0.0.1:5000)
"""
from flask import Flask

app = Flask(__name__)

NAV = """<nav style="padding:12px;background:#1e293b">
  <a href="/" style="color:#fff;margin-right:16px">Home</a>
  <a href="/pricing" style="color:#fff;margin-right:16px">Pricing</a>
  <a href="/about" style="color:#fff;margin-right:16px">About</a>
  <a href="/contact" style="color:#fff;margin-right:16px">Contact</a>
  <a href="/blog" style="color:#fff">Blog</a>
</nav>"""


def page(title: str, body: str) -> str:
    return f"""<!doctype html><html><head><title>{title} — DemoShop</title></head>
<body style="font-family:sans-serif;margin:0">{NAV}
<main style="padding:24px">{body}</main></body></html>"""


@app.route("/")
def home():
    return page("Home", """
      <h1>DemoShop</h1>
      <p>Welcome to the demo store Argus gets to tear apart.</p>
      <!-- BUG 1: link to a page that does not exist -->
      <p><a href="/summer-sale">Check out our summer sale!</a></p>
      <!-- BUG 2: image with no alt attribute -->
      <img src="/static/logo.svg" width="120">
    """)


@app.route("/static/logo.svg")
def logo():
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40">'
            '<rect width="120" height="40" fill="#0ea5e9"/></svg>',
            200, {"Content-Type": "image/svg+xml"})


@app.route("/pricing")
def pricing():
    return page("Pricing", """
      <h1>Pricing</h1>
      <!-- BUG 3: broken image (404) -->
      <img src="/static/plans-chart.png" alt="Plan comparison" width="400">
      <!-- BUG 4 (visual): nearly invisible low-contrast text -->
      <p style="color:#f4f4f4;background:#fff">All plans include a 30-day refund guarantee.</p>
      <p>Basic $9 · Pro $29 · Enterprise: contact us</p>
    """)


@app.route("/about")
def about():
    return page("About", """
      <h1>About us</h1>
      <!-- BUG 5 (visual): overlapping elements -->
      <div style="position:relative;height:60px">
        <p style="position:absolute;top:0">We started DemoShop in 2024 with a simple mission.</p>
        <button style="position:absolute;top:8px;left:40px">Meet the team</button>
      </div>
      <!-- BUG 6: uncaught JS error on load -->
      <script>document.querySelector('#stats-widget').innerHTML = 'loaded';</script>
    """)


@app.route("/contact")
def contact():
    return page("Contact", """
      <h1>Contact</h1>
      <form>
        <!-- BUG 7: input with no label -->
        <input type="email" placeholder="you@example.com">
        <button type="submit">Subscribe</button>
      </form>
      <!-- BUG 8: fetch to an endpoint that 404s -->
      <script>fetch('/api/office-locations').then(r => r.json()).catch(() => {});</script>
    """)


@app.route("/blog")
def blog():
    # Control page: no injected bugs. False positives here count against precision.
    return page("Blog", """
      <h1>Blog</h1>
      <article><h2>How we test software</h2><p>Very carefully, and now with agents.</p></article>
    """)


if __name__ == "__main__":
    app.run(port=5000)
