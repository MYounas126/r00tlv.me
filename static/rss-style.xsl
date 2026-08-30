<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <xsl:output method="html" encoding="utf-8" indent="yes"/>

  <xsl:template match="/">
    <html lang="en">
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title><xsl:value-of select="rss/channel/title"/> - RSS feed</title>
        <style>
          :root {
            --bg: #1d1e20; --fg: #dadadb; --muted: #9b9c9d;
            --accent: #9fef00; --line: #333; --box: #2e2e33;
          }
          @media (prefers-color-scheme: light) {
            :root {
              --bg: #fff; --fg: #1e1e1e; --muted: #6c6c6c;
              --accent: #1a7f37; --line: #eee; --box: #f5f5f5;
            }
          }
          html { -webkit-text-size-adjust: 100%; }
          body {
            margin: 0; padding: 48px 20px; background: var(--bg); color: var(--fg);
            font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                  Helvetica, Arial, sans-serif;
          }
          .wrap { max-width: 720px; margin: 0 auto; }
          h1 { font-size: 28px; line-height: 1.25; margin: 0 0 6px; }
          .sub { color: var(--muted); margin: 0 0 28px; }
          .note {
            border: 1px solid var(--line); border-radius: 8px;
            padding: 16px 18px; margin: 0 0 36px;
          }
          .note p { margin: 0 0 10px; }
          .note p.last { margin: 0; }
          code {
            background: var(--box); border-radius: 4px; padding: 2px 6px;
            font: 14px/1.5 Menlo, Monaco, Consolas, monospace;
            word-break: break-all;
          }
          a { color: var(--accent); text-decoration: none; }
          a:hover { text-decoration: underline; }
          .item { padding: 22px 0; border-top: 1px solid var(--line); }
          .item h2 { font-size: 20px; line-height: 1.3; margin: 0 0 4px; }
          .date { color: var(--muted); font-size: 14px; margin: 0 0 8px; }
          .desc { color: var(--fg); margin: 0; }
          footer { margin-top: 40px; color: var(--muted); font-size: 14px; }
        </style>
      </head>
      <body>
        <div class="wrap">
          <h1><xsl:value-of select="rss/channel/title"/></h1>
          <p class="sub"><xsl:value-of select="rss/channel/description"/></p>

          <div class="note">
            <p><strong>This is an RSS feed.</strong> It is meant for feed readers,
            not for reading directly in a browser.</p>
            <p>Subscribe by pasting this address into a reader such as Feedly,
            NetNewsWire, Inoreader or Miniflux:</p>
            <p class="last"><code><xsl:value-of select="rss/channel/atom:link/@href"/></code></p>
          </div>

          <xsl:for-each select="rss/channel/item">
            <div class="item">
              <h2>
                <a>
                  <xsl:attribute name="href"><xsl:value-of select="link"/></xsl:attribute>
                  <xsl:value-of select="title" disable-output-escaping="yes"/>
                </a>
              </h2>
              <p class="date"><xsl:value-of select="pubDate"/></p>
              <p class="desc"><xsl:value-of select="description" disable-output-escaping="yes"/></p>
            </div>
          </xsl:for-each>

          <footer>
            <a>
              <xsl:attribute name="href"><xsl:value-of select="rss/channel/link"/></xsl:attribute>
              Back to <xsl:value-of select="rss/channel/title"/>
            </a>
          </footer>
        </div>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
