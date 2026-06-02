"""
core/layout_editor.py  —  AI Layout Editor
===========================================
Understands a page as a collection of named sections.
Can:
  • analyze()   — parse existing sections from HTML
  • add()       — insert a new section (AI generates it)
  • modify()    — rewrite a specific section
  • remove()    — delete a section by name
  • reorder()   — move sections around
  • list_presets() — catalog of ready-made sections
"""

import re, logging
log = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#  Section presets catalog
# ════════════════════════════════════════════════════════════
SECTION_PRESETS = [
    {"id": "hero",         "icon": "🚀", "label": "Hero / Banner",       "desc": "Full-width intro section with headline and CTA button"},
    {"id": "services",     "icon": "⚙️", "label": "Services",            "desc": "Grid of service/feature cards"},
    {"id": "about",        "icon": "👥", "label": "About Us",            "desc": "Story section with image and text"},
    {"id": "pricing",      "icon": "💰", "label": "Pricing Plans",       "desc": "3-column pricing table"},
    {"id": "testimonials", "icon": "💬", "label": "Testimonials",        "desc": "Customer reviews and star ratings"},
    {"id": "team",         "icon": "🧑‍🤝‍🧑", "label": "Team",           "desc": "Team member cards with names and roles"},
    {"id": "faq",          "icon": "❓", "label": "FAQ",                 "desc": "Accordion-style frequently asked questions"},
    {"id": "gallery",      "icon": "🖼️", "label": "Gallery / Portfolio", "desc": "Image/project showcase grid"},
    {"id": "stats",        "icon": "📊", "label": "Stats / Numbers",     "desc": "Key metrics and achievements"},
    {"id": "cta",          "icon": "📣", "label": "Call to Action",      "desc": "Full-width CTA banner with button"},
    {"id": "contact",      "icon": "📬", "label": "Contact Form",        "desc": "Contact form with map or info"},
    {"id": "blog",         "icon": "📝", "label": "Blog / News",         "desc": "Latest articles preview grid"},
    {"id": "video",        "icon": "🎥", "label": "Video Section",       "desc": "Embedded video with description"},
    {"id": "partners",     "icon": "🤝", "label": "Partners / Logos",    "desc": "Logo strip of partner companies"},
    {"id": "newsletter",   "icon": "📧", "label": "Newsletter",          "desc": "Email signup form"},
    {"id": "timeline",     "icon": "⏳", "label": "Timeline",            "desc": "Company history or process steps"},
    {"id": "map",          "icon": "📍", "label": "Location / Map",      "desc": "Address and embedded map"},
    {"id": "products",     "icon": "🛍️", "label": "Products Grid",      "desc": "Product cards with prices"},
    {"id": "features",     "icon": "✨", "label": "Features",            "desc": "3- or 4-column feature highlights"},
    {"id": "footer",       "icon": "🔻", "label": "Footer",              "desc": "Site footer with links and copyright"},
]


# ════════════════════════════════════════════════════════════
#  HTML section analyzer
# ════════════════════════════════════════════════════════════
def analyze_sections(html: str) -> list:
    """
    Parse the HTML and return list of detected sections:
    [{"name": str, "tag": str, "id": str, "start": int, "end": int}, ...]
    """
    sections = []

    # Match <section>, <header>, <footer>, <main>, <article>
    # and top-level <div id="..."> or <div class="...section...">
    patterns = [
        r'<(section|header|footer|main|article)([^>]*)>(.*?)</\1>',
        r'<(div)\s+id=["\']([^"\']+section[^"\']*|hero|about|services|contact|pricing|team|faq|testimonials|gallery|blog|stats|cta|newsletter|footer|products|features|partners|video|map|timeline)["\'][^>]*>',
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, html, re.I | re.S):
            tag  = m.group(1)
            attrs = m.group(2) if len(m.groups()) > 1 else ""

            # Extract id
            id_m  = re.search(r'\bid=["\']([^"\']+)["\']', attrs, re.I)
            cls_m = re.search(r'\bclass=["\']([^"\']+)["\']', attrs, re.I)

            sec_id  = id_m.group(1)  if id_m  else ""
            sec_cls = cls_m.group(1) if cls_m else ""

            # Guess section name
            name = _guess_section_name(tag, sec_id, sec_cls)

            sections.append({
                "name":  name,
                "tag":   tag,
                "id":    sec_id,
                "class": sec_cls,
                "start": m.start(),
                "end":   m.end(),
            })

    # Remove duplicates / overlapping
    sections = _deduplicate(sections)
    return sections


def _guess_section_name(tag: str, sec_id: str, sec_cls: str) -> str:
    combined = f"{tag} {sec_id} {sec_cls}".lower()
    mapping = {
        "hero":         ["hero", "banner", "jumbotron", "masthead"],
        "nav":          ["nav", "header", "navbar", "menu"],
        "services":     ["service", "feature", "offer"],
        "about":        ["about", "story", "who-we"],
        "pricing":      ["pric", "plan", "package"],
        "testimonials": ["testi", "review", "feedback", "client"],
        "team":         ["team", "staff", "people"],
        "faq":          ["faq", "question", "accord"],
        "gallery":      ["gallery", "portfolio", "work", "project"],
        "stats":        ["stat", "number", "metric", "counter"],
        "cta":          ["cta", "call-to-action", "callout"],
        "contact":      ["contact", "reach", "touch", "form"],
        "blog":         ["blog", "news", "article", "post"],
        "footer":       ["footer", "bottom"],
        "products":     ["product", "shop", "store", "item"],
        "partners":     ["partner", "sponsor", "logo", "brand", "client-logo"],
        "newsletter":   ["newsletter", "subscribe", "email"],
        "video":        ["video", "media", "youtube"],
        "map":          ["map", "location", "address"],
        "timeline":     ["timeline", "history", "process", "step"],
    }
    for name, keywords in mapping.items():
        if any(kw in combined for kw in keywords):
            return name
    return tag  # fallback to tag name


def _deduplicate(sections: list) -> list:
    """Remove overlapping sections (keep the outer one)."""
    if not sections:
        return []
    sections.sort(key=lambda s: s["start"])
    result = [sections[0]]
    for s in sections[1:]:
        prev = result[-1]
        if s["start"] >= prev["end"]:  # no overlap
            result.append(s)
    return result


# ════════════════════════════════════════════════════════════
#  AI prompts
# ════════════════════════════════════════════════════════════

_ADD_PROMPT = (
    "You are an expert frontend developer.\n"
    "Generate a single \"{section_name}\" HTML section for an existing website.\n"
    "CRITICAL: Match the site design EXACTLY — same CSS variables, colors, fonts, buttons, border-radius.\n\n"
    "=== SITE DESIGN SYSTEM ===\n{context}\n\n"
    "=== RULES ===\n"
    "1. Output ONLY the section HTML — no <!DOCTYPE> <html> <head> <body>\n"
    "2. Use the exact CSS variables (var(--primary) etc.) listed above\n"
    "3. Use the exact hex colors and font-family from the design system\n"
    "4. Match button styles, card styles, and border-radius exactly\n"
    "5. Section must have id=\"{section_name}\" class=\"section {section_name}\"\n"
    "6. Add <style> inside section only for truly new styles not in the site CSS\n"
    "7. Write realistic meaningful content in the site language — no Lorem Ipsum\n"
    "8. No markdown fences, no explanation\n\n"
    "OUTPUT (section HTML only, starting with <section or <div):"
)

_MODIFY_PROMPT = (
    "You are an expert frontend developer.\n"
    "Modify the following HTML section based on the user request.\n\n"
    "USER REQUEST: {request}\n\n"
    "RULES:\n"
    "1. Return ONLY the modified section HTML — no page wrappers\n"
    "2. Keep same id and class attributes\n"
    "3. Preserve all colors, fonts, and design patterns exactly\n"
    "4. No markdown fences, no explanation\n\n"
    "SECTION HTML:\n{section_html}\n\n"
    "OUTPUT (modified section only):"
)

_REMOVE_PROMPT = """You are an expert frontend developer.
Remove the "{section_name}" section from this HTML completely.
Return the complete HTML without that section.
No explanation. Start directly with <!DOCTYPE html> or <html.

HTML:
{html}

OUTPUT:"""

_REORDER_PROMPT = """You are an expert frontend developer.
Reorder the sections in this HTML page so they appear in this order:
{order}

Keep all section content exactly the same — only change their order.
Return the complete HTML. No explanation. Start with <!DOCTYPE html> or <html.

HTML:
{html}

OUTPUT:"""


# ════════════════════════════════════════════════════════════
#  Core operations
# ════════════════════════════════════════════════════════════

def _call(prompt: str, model: str, provider: str, on_token=None) -> str:
    from core.ai_engine import _call_ai, _call_ai_stream
    if on_token:
        result = _call_ai_stream(prompt, model, provider, on_token=on_token)
    else:
        result = _call_ai(prompt, model, provider)
    result = result.strip()
    result = re.sub(r'^```html\s*', '', result, flags=re.I)
    result = re.sub(r'^```\s*', '', result)
    result = re.sub(r'\s*```$', '', result)
    return result.strip()


def _extract_context(html: str) -> str:
    """Extract rich design context so AI matches site style precisely."""
    import re as _re
    title_m = _re.search(r'<title[^>]*>(.*?)</title>', html, _re.I | _re.S)
    title   = title_m.group(1).strip() if title_m else "Unknown"

    lang_m  = _re.search(r'<html[^>]+lang=["\']([^"\']+)["\']', html, _re.I)
    lang    = lang_m.group(1) if lang_m else "en"

    css_vars   = _re.findall(r'(--[a-zA-Z0-9-]+)[ \t]*:[ \t]*([^;}\r\n]+)', html)
    vars_str   = "\n".join(f"  {k}: {v.strip()}" for k, v in css_vars[:20]) or "  (none)"

    hex_cols   = list(dict.fromkeys(_re.findall(r'#[0-9a-fA-F]{6}\b', html)))[:12]
    colors_str = ", ".join(hex_cols) or "(none)"

    raw_fonts  = _re.findall(r'font-family[ \t]*:[ \t]*([^;}\r\n]+)', html)
    fonts_str  = ", ".join(dict.fromkeys(
        f.split(",")[0].strip().strip("\'\"") for f in raw_fonts[:4]
    )) or "(none)"

    btn_css  = _re.findall(r'\.btn[\w-]*[ \t]*\{([^}]+)\}', html)
    btn_str  = btn_css[0].strip()[:200] if btn_css else "(none)"

    radii    = _re.findall(r'border-radius[ \t]*:[ \t]*([^;}\r\n]+)', html)
    radius_str = radii[0].strip() if radii else "(none)"

    sec_m    = _re.search(
        r'<(?:section|div)[^>]+(?:class|id)=["\'][^"\']*(?:hero|about|service|feature|card)[^"\']*["\'][^>]*>',
        html, _re.I)
    example  = html[sec_m.start(): sec_m.start() + 500] if sec_m else "(none)"

    return (
        "Title:         " + title + "\n" +
        "Language:      " + lang  + "\n" +
        "CSS Variables:\n" + vars_str + "\n" +
        "Colors:        " + colors_str + "\n" +
        "Fonts:         " + fonts_str + "\n" +
        "Button Style:  " + btn_str + "\n" +
        "Border Radius: " + radius_str + "\n" +
        "Style Snippet:\n" + example
    )


def add_section(html: str, section_id: str, model: str, provider: str,
                progress_cb=None) -> str:
    """
    Add a section using zero-AI template engine — instant, free, style-matched.
    Falls back to AI only if section_id has no template.
    """
    from core.section_templates import extract_tokens, build_section, available_sections
    if progress_cb: progress_cb(f"⚙️ جارٍ توليد قسم {section_id}…")

    if section_id in available_sections():
        # ── Zero-AI path: extract tokens + render template ──
        tokens       = extract_tokens(html)
        section_html = build_section(section_id, tokens)
        if progress_cb: progress_cb(f"✏️ إدراج القسم في الصفحة…")
        if re.search(r'</body>', html, re.I):
            return re.sub(r'(?i)</body>', f'\n{section_html}\n</body>', html, count=1)
        return html + f'\n{section_html}'

    # ── AI fallback for unknown section types ──
    if progress_cb: progress_cb(f"🤖 Generating {section_id} section via AI…")
    ctx    = _extract_context(html)
    prompt = _ADD_PROMPT.format(section_name=section_id, context=ctx)
    def _on_token(partial):
        if progress_cb:
            progress_cb(f"🤖 Generating… {len(partial)} chars")
    section_html = _call(prompt, model, provider, on_token=_on_token)
    section_html = re.sub(r'(?i)<!DOCTYPE[^>]*>', '', section_html)
    section_html = re.sub(r'(?i)</?html[^>]*>', '', section_html)
    section_html = re.sub(r'(?i)<head[^>]*>.*?</head>', '', section_html, flags=re.S)
    section_html = re.sub(r'(?i)</?body[^>]*>', '', section_html).strip()
    if not section_html:
        return html
    if re.search(r'</body>', html, re.I):
        return re.sub(r'(?i)</body>', f'\n{section_html}\n</body>', html, count=1)
    return html + f'\n{section_html}'


def modify_section(html: str, section_id: str, request: str,
                   model: str, provider: str, progress_cb=None) -> str:
    """Send only the target section to AI — fast and precise."""
    if progress_cb: progress_cb(f"🤖 Modifying {section_id} section…")
    sections = analyze_sections(html)
    target   = next((s for s in sections
                     if s.get("id") == section_id or s.get("name") == section_id), None)
    if target:
        orig_block     = html[target["start"]:target["end"]]
        prompt         = _MODIFY_PROMPT.format(request=request, section_html=orig_block)
        def _on_tok(p):
            if progress_cb: progress_cb(f'🤖 Modifying… {len(p)} chars')
        modified_block = _call(prompt, model, provider, on_token=_on_tok)
        modified_block = re.sub(r'(?i)<!DOCTYPE[^>]*>', '', modified_block)
        modified_block = re.sub(r'(?i)</?html[^>]*>', '', modified_block)
        modified_block = re.sub(r'(?i)<head[^>]*>.*?</head>', '', modified_block, flags=re.S)
        modified_block = re.sub(r'(?i)</?body[^>]*>', '', modified_block).strip()
        if modified_block:
            return html[:target["start"]] + modified_block + html[target["end"]:]
    # Fallback
    prompt = _MODIFY_PROMPT.format(request=request, section_html=html[:8000])
    result = _call(prompt, model, provider)
    return result if _is_valid_html(result) else html


def remove_section(html: str, section_id: str,
                   model: str, provider: str, progress_cb=None) -> str:
    """Remove a section from the page."""
    if progress_cb: progress_cb(f"🗑 Removing {section_id} section…")

    # Try regex removal first (faster, no AI needed)
    patterns = [
        rf'<section[^>]+id=["\']{re.escape(section_id)}["\'][^>]*>.*?</section>',
        rf'<div[^>]+id=["\']{re.escape(section_id)}["\'][^>]*>.*?</div>',
    ]
    for pat in patterns:
        new_html = re.sub(pat, '', html, flags=re.S | re.I)
        if new_html != html:
            log.info("Section '%s' removed via regex", section_id)
            return new_html

    # Fallback: use AI
    prompt = _REMOVE_PROMPT.format(section_name=section_id, html=html[:14000])
    result = _call(prompt, model, provider)
    return result if _is_valid_html(result) else html


def reorder_sections(html: str, new_order: list,
                     model: str = None, provider: str = None,
                     progress_cb=None) -> str:
    """Reorder sections purely in Python — instant, no AI."""
    if progress_cb: progress_cb("🔀 Reordering sections…")
    sections = analyze_sections(html)
    if len(sections) < 2:
        return html
    order_map   = {sid: i for i, sid in enumerate(new_order)}
    sorted_secs = sorted(sections, key=lambda s: order_map.get(s.get("id") or s["name"], 999))
    orig_sorted = sorted(sections, key=lambda s: s["start"])
    blocks = {(s.get("id") or s["name"]): html[s["start"]:s["end"]] for s in orig_sorted}
    pairs  = list(zip(orig_sorted, sorted_secs))
    pairs.sort(key=lambda p: p[0]["start"], reverse=True)
    result = html
    for orig_sec, new_sec in pairs:
        new_key   = new_sec.get("id") or new_sec["name"]
        new_block = blocks.get(new_key, html[orig_sec["start"]:orig_sec["end"]])
        result    = result[:orig_sec["start"]] + new_block + result[orig_sec["end"]:]
    return result


def _is_valid_html(s: str) -> bool:
    return bool(s) and ("<html" in s.lower() or "<!doctype" in s.lower() or "<body" in s.lower())