import re
import os
import logging

log = logging.getLogger(__name__)


# ================================
#  CLIENT FACTORY  (multi-provider)
# ================================

def _get_client(provider: str, api_key: str = ""):
    provider = provider.lower()

    if provider == "anthropic":
        from anthropic import Anthropic
        key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError("Anthropic API key is missing. Set it in Settings.")
        return Anthropic(api_key=key), "anthropic"

    elif provider == "gemini":
        import google.generativeai as genai
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("Gemini API key is missing. Set it in Settings.")
        genai.configure(api_key=key)
        return genai, "gemini"

    else:  # openai
        from openai import OpenAI
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OpenAI API key is missing. Set it in Settings.")
        return OpenAI(api_key=key), "openai"


def _chat(client, provider: str, model: str, prompt: str, max_tokens: int = 8000) -> str:
    provider = provider.lower()

    if provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    elif provider == "gemini":
        gemini_model = client.GenerativeModel(model)
        response = gemini_model.generate_content(prompt)
        return response.text.strip()

    else:  # openai
        _is_reasoning = any(model.startswith(p) for p in ("gpt-5", "o1", "o3", "o4"))
        kwargs = {
            "model":    model,
            "messages": [{"role": "user", "content": prompt}],
            "stream":   False,
        }
        if _is_reasoning:
            # نماذج reasoning تستهلك tokens في التفكير الداخلي
            # نرفع الحد لـ 32000 ونضع reasoning_effort=low لتوفير tokens للرد
            kwargs["max_completion_tokens"] = 32000
            try:
                kwargs["reasoning_effort"] = "low"
                response = client.chat.completions.create(**kwargs)
            except Exception:
                # إذا لم يدعم reasoning_effort نحذفه ونحاول مجدداً
                del kwargs["reasoning_effort"]
                response = client.chat.completions.create(**kwargs)
        else:
            kwargs["max_tokens"] = max_tokens
            response = client.chat.completions.create(**kwargs)

        # تسجيل تفاصيل الرد كاملة لتشخيص المشاكل
        choice = response.choices[0]
        log.info("finish_reason: %s", choice.finish_reason)
        log.info("usage: %s", response.usage)

        content = choice.message.content

        # بعض نماذج o-series ترجع None عند استخدام reasoning داخلي
        if content is None:
            log.warning("content is None — checking refusal...")
            refusal = getattr(choice.message, "refusal", None)
            if refusal:
                raise RuntimeError(f"Model refused the request: {refusal}")
            raise RuntimeError(
                f"Model '{model}' returned empty content.\n"
                f"finish_reason: {choice.finish_reason}\n"
                f"Try switching to gpt-4o or gpt-4o-mini in Settings."
            )

        return content.strip()


# ================================
#  MAIN WEBSITE GENERATOR
# ================================

def generate_advanced_website(idea, design_system, language, model,
                               provider="openai", api_key=""):
    """
    Generate a complete multi-file website.
    Returns a dict: {filename: content, ...}
    """
    client, provider = _get_client(provider, api_key)

    # طلب واحد يولّد CSS + كل صفحات HTML معاً
    raw = _generate_all(idea, language, model, client, provider)

    log.info("AI raw output (first 500 chars): %s", raw[:500])

    files = extract_files(raw)

    log.info("Extracted files: %s", {k: len(v) for k, v in files.items()})

    # إذا فشل الاستخراج — محاولة ثانية بـ prompt مبسّط
    if not files.get("index.html"):
        log.warning("First extraction failed, retrying with simplified prompt...")
        raw2 = _generate_all_simple(idea, language, model, client, provider)
        log.info("Retry raw output (first 500 chars): %s", raw2[:500])
        files = extract_files(raw2)

    if not files.get("script.js"):
        files["script.js"] = _default_script()

    if not files.get("style.css"):
        files["style.css"] = _generate_css_only(idea, language, model, client, provider)

    return files


def _generate_all(idea, language, model, client, provider):
    """Generate a world-class website — maximum quality prompt."""
    prompt = f"""You are the lead designer and engineer at a top-tier digital agency.
Your clients include Fortune 500 companies. Your sites win Awwwards every year.
This is your best work ever. No shortcuts. No generic templates.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT BRIEF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Concept : {idea}
Language : {language}
Benchmark: Stripe.com · linear.app · vercel.com · resend.com · raycast.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY CSS FOUNDATION (use verbatim as base)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; font-size: 16px; }}
body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; -webkit-font-smoothing: antialiased; }}
img {{ max-width: 100%; height: auto; display: block; }}
a {{ text-decoration: none; color: inherit; }}

Then define these exact CSS variables (adapt colors to the brand):
:root {{
  /* Brand colors — choose a sophisticated palette */
  --primary: #[brand-color];
  --primary-hover: [darker 10%];
  --primary-light: [primary at 10% opacity];
  --accent: [complementary color];
  --bg: #fafaf9 or #0a0a0a (light or dark based on brand);
  --bg-secondary: [slightly different from bg];
  --bg-card: #ffffff or #111111;
  --text: #0f0f0f or #f5f5f5;
  --text-muted: #6b7280;
  --text-subtle: #9ca3af;
  --border: rgba(0,0,0,0.08);
  --border-strong: rgba(0,0,0,0.16);
  --radius-sm: 8px;
  --radius: 12px;
  --radius-lg: 20px;
  --radius-xl: 28px;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow: 0 4px 16px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
  --shadow-lg: 0 20px 60px rgba(0,0,0,0.12), 0 8px 24px rgba(0,0,0,0.06);
  --shadow-hover: 0 24px 64px rgba(0,0,0,0.18);
  --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-spring: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  --max-width: 1200px;
  --nav-height: 72px;
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NAVBAR — elite level
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
.navbar {{
  position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
  height: var(--nav-height);
  display: flex; align-items: center;
  padding: 0 clamp(1.5rem, 5vw, 3rem);
  background: rgba(255,255,255,0.72);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid var(--border);
  transition: var(--transition);
}}
.navbar.scrolled {{ background: rgba(255,255,255,0.95); box-shadow: var(--shadow-sm); }}
.navbar.hidden {{ transform: translateY(-100%); }}
.nav-logo {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.1rem; }}
.nav-logo-icon {{ width: 36px; height: 36px; border-radius: 10px; background: var(--primary); display:flex; align-items:center; justify-content:center; color:white; font-weight:800; }}
.nav-links {{ display: flex; align-items: center; gap: 2rem; margin: 0 auto; list-style:none; }}
.nav-links a {{ font-size: 0.9rem; font-weight: 500; color: var(--text-muted); transition: var(--transition); padding: 4px 0; position:relative; }}
.nav-links a::after {{ content:''; position:absolute; bottom:-2px; left:0; width:0; height:2px; background:var(--primary); transition:var(--transition); border-radius:2px; }}
.nav-links a:hover, .nav-links a.active {{ color: var(--text); }}
.nav-links a:hover::after, .nav-links a.active::after {{ width:100%; }}
.nav-cta {{ display:flex; align-items:center; gap:1rem; }}
.btn {{ display:inline-flex; align-items:center; gap:8px; padding: 10px 20px; border-radius: var(--radius); font-weight: 600; font-size: 0.9rem; cursor:pointer; border:none; transition: var(--transition); white-space:nowrap; }}
.btn-primary {{ background: var(--primary); color: white; box-shadow: 0 2px 8px rgba(var(--primary-rgb),0.3); }}
.btn-primary:hover {{ background: var(--primary-hover); transform: translateY(-1px); box-shadow: 0 4px 16px rgba(var(--primary-rgb),0.4); }}
.btn-primary:active {{ transform: translateY(0); }}
.btn-ghost {{ background: transparent; color: var(--text); border: 1px solid var(--border-strong); }}
.btn-ghost:hover {{ background: var(--bg-secondary); border-color: var(--text-muted); }}
.menu-toggle {{ display:none; flex-direction:column; gap:5px; cursor:pointer; padding:8px; border:none; background:none; }}
.menu-toggle span {{ width:22px; height:2px; background:var(--text); border-radius:2px; transition:var(--transition); display:block; }}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HERO SECTION — stunning, full viewport
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
.hero {{
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-items: center;
  gap: clamp(2rem, 6vw, 5rem);
  padding: calc(var(--nav-height) + 4rem) clamp(1.5rem, 5vw, 3rem) 4rem;
  max-width: var(--max-width); margin: 0 auto;
}}
.hero-eyebrow {{ display:inline-flex; align-items:center; gap:8px; background:var(--primary-light); color:var(--primary); padding:6px 14px; border-radius:100px; font-size:0.8rem; font-weight:600; letter-spacing:0.05em; text-transform:uppercase; margin-bottom:1.5rem; }}
.hero h1 {{
  font-size: clamp(2.8rem, 6vw, 5.5rem);
  font-weight: 800;
  line-height: 1.08;
  letter-spacing: -0.03em;
  color: var(--text);
  margin-bottom: 1.5rem;
}}
.hero h1 span {{ color: var(--primary); }}
.hero-sub {{ font-size: clamp(1rem, 2vw, 1.2rem); color: var(--text-muted); max-width: 480px; line-height: 1.7; margin-bottom: 2.5rem; }}
.hero-actions {{ display:flex; align-items:center; gap:1rem; flex-wrap:wrap; }}
.hero-visual {{ position:relative; }}
.hero-img-wrap {{
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  aspect-ratio: 4/3;
  position: relative;
}}
.hero-img-wrap img {{ width:100%; height:100%; object-fit:cover; transition: transform 0.6s ease; }}
.hero-img-wrap:hover img {{ transform: scale(1.03); }}
.hero-badge {{
  position:absolute; bottom:-20px; left:-20px;
  background: white;
  border-radius: var(--radius);
  padding: 16px 20px;
  box-shadow: var(--shadow-lg);
  display:flex; align-items:center; gap:12px;
  font-weight:600; font-size:0.85rem;
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CARDS & SECTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
.section {{ padding: clamp(5rem, 10vw, 9rem) clamp(1.5rem, 5vw, 3rem); }}
.section-inner {{ max-width: var(--max-width); margin: 0 auto; }}
.section-tag {{ display:inline-block; color:var(--primary); font-weight:600; font-size:0.8rem; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:1rem; }}
.section-title {{ font-size: clamp(1.8rem, 4vw, 3rem); font-weight:800; letter-spacing:-0.025em; line-height:1.15; margin-bottom:1rem; }}
.section-sub {{ font-size:1.1rem; color:var(--text-muted); max-width:560px; line-height:1.7; margin-bottom:3.5rem; }}
.grid-3 {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap:1.5rem; }}
.grid-2 {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap:2rem; }}
.card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 2rem;
  transition: var(--transition);
  position: relative;
  overflow: hidden;
}}
.card::before {{ content:''; position:absolute; inset:0; background:linear-gradient(135deg, var(--primary-light) 0%, transparent 60%); opacity:0; transition:var(--transition); border-radius:inherit; }}
.card:hover {{ transform: translateY(-6px); box-shadow: var(--shadow-hover); border-color: var(--primary-light); }}
.card:hover::before {{ opacity:1; }}
.card-icon {{ width:52px; height:52px; border-radius:14px; background:var(--primary-light); color:var(--primary); display:flex; align-items:center; justify-content:center; font-size:1.4rem; margin-bottom:1.25rem; transition: var(--transition-spring); }}
.card:hover .card-icon {{ transform: scale(1.1) rotate(-5deg); }}
.card h3 {{ font-size:1.1rem; font-weight:700; margin-bottom:0.6rem; letter-spacing:-0.01em; }}
.card p {{ color:var(--text-muted); font-size:0.92rem; line-height:1.65; }}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STATS, TESTIMONIALS, CTA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
.stats-bar {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr)); gap:2rem; padding:3rem; background:var(--bg-card); border-radius:var(--radius-xl); border:1px solid var(--border); box-shadow:var(--shadow); }}
.stat-item {{ text-align:center; }}
.stat-number {{ font-size:clamp(2rem,5vw,3.5rem); font-weight:900; color:var(--primary); letter-spacing:-0.04em; line-height:1; }}
.stat-label {{ font-size:0.85rem; color:var(--text-muted); margin-top:0.35rem; font-weight:500; }}

.testimonial-card {{
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:var(--radius-lg); padding:2rem;
  transition:var(--transition);
}}
.testimonial-card:hover {{ transform:translateY(-4px); box-shadow:var(--shadow-lg); }}
.stars {{ color:#f59e0b; font-size:0.9rem; margin-bottom:1rem; letter-spacing:2px; }}
.testimonial-text {{ font-size:1rem; line-height:1.7; color:var(--text); margin-bottom:1.5rem; font-style:italic; }}
.testimonial-author {{ display:flex; align-items:center; gap:12px; }}
.avatar {{ width:44px; height:44px; border-radius:50%; background:linear-gradient(135deg, var(--primary), var(--accent)); display:flex; align-items:center; justify-content:center; color:white; font-weight:700; font-size:0.9rem; }}
.author-info strong {{ display:block; font-size:0.9rem; font-weight:600; }}
.author-info span {{ font-size:0.8rem; color:var(--text-muted); }}

.cta-section {{
  background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
  border-radius: var(--radius-xl);
  padding: clamp(3rem, 8vw, 6rem) clamp(2rem, 5vw, 4rem);
  text-align:center; color:white;
  position:relative; overflow:hidden;
  margin: 0 clamp(1.5rem, 5vw, 3rem);
}}
.cta-section::before {{ content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%; background: radial-gradient(ellipse at center, rgba(255,255,255,0.12) 0%, transparent 60%); }}
.cta-section h2 {{ font-size:clamp(2rem,5vw,3.5rem); font-weight:800; letter-spacing:-0.025em; margin-bottom:1rem; position:relative; }}
.cta-section p {{ font-size:1.1rem; opacity:0.85; max-width:480px; margin: 0 auto 2.5rem; position:relative; }}
.btn-white {{ background:white; color:var(--primary); font-weight:700; }}
.btn-white:hover {{ background:rgba(255,255,255,0.9); transform:translateY(-2px); box-shadow:0 8px 24px rgba(0,0,0,0.2); }}

.footer {{
  background: var(--text);
  color: rgba(255,255,255,0.5);
  padding: clamp(3rem, 8vw, 5rem) clamp(1.5rem, 5vw, 3rem) 2rem;
}}
.footer-inner {{ max-width:var(--max-width); margin:0 auto; }}
.footer-grid {{ display:grid; grid-template-columns:2fr 1fr 1fr 1fr; gap:3rem; margin-bottom:3rem; }}
.footer-brand p {{ font-size:0.9rem; line-height:1.7; max-width:280px; margin-top:0.75rem; }}
.footer-col h4 {{ color:white; font-size:0.85rem; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:1.25rem; }}
.footer-col ul {{ list-style:none; display:flex; flex-direction:column; gap:0.6rem; }}
.footer-col a {{ font-size:0.875rem; transition:var(--transition); }}
.footer-col a:hover {{ color:white; }}
.footer-bottom {{ padding-top:2rem; border-top:1px solid rgba(255,255,255,0.08); display:flex; justify-content:space-between; align-items:center; font-size:0.82rem; }}

/* Animations */
.fade-up {{ opacity:0; transform:translateY(30px); transition: opacity 0.7s ease, transform 0.7s ease; }}
.fade-up.visible {{ opacity:1; transform:translateY(0); }}
.fade-up:nth-child(2) {{ transition-delay:0.1s; }}
.fade-up:nth-child(3) {{ transition-delay:0.2s; }}
.fade-up:nth-child(4) {{ transition-delay:0.3s; }}

/* Form */
.form-group {{ margin-bottom:1.25rem; }}
.form-group label {{ display:block; font-size:0.85rem; font-weight:500; margin-bottom:6px; color:var(--text); }}
.form-group input, .form-group textarea, .form-group select {{
  width:100%; padding:12px 16px;
  background:var(--bg-secondary); border:1px solid var(--border);
  border-radius:var(--radius); font-family:inherit; font-size:0.95rem;
  color:var(--text); outline:none; transition:var(--transition);
}}
.form-group input:focus, .form-group textarea:focus {{
  border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-light);
}}

/* Responsive */
@media (max-width: 768px) {{
  .hero {{ grid-template-columns:1fr; text-align:center; }}
  .hero-sub {{ max-width:100%; }}
  .hero-actions {{ justify-content:center; }}
  .hero-visual {{ order:-1; }}
  .grid-3 {{ grid-template-columns:1fr; }}
  .grid-2 {{ grid-template-columns:1fr; }}
  .footer-grid {{ grid-template-columns:1fr 1fr; }}
  .nav-links {{ display:none; position:fixed; top:var(--nav-height); left:0; right:0; background:white; padding:2rem; flex-direction:column; gap:1.5rem; border-bottom:1px solid var(--border); box-shadow:var(--shadow-lg); }}
  .nav-links.open {{ display:flex; }}
  .menu-toggle {{ display:flex; }}
}}
@media (max-width: 480px) {{
  .footer-grid {{ grid-template-columns:1fr; }}
  .stats-bar {{ grid-template-columns:1fr 1fr; }}
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY JAVASCRIPT (use verbatim + expand)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
document.addEventListener('DOMContentLoaded', () => {{

  // 1. Navbar scroll behavior
  const navbar = document.querySelector('.navbar');
  let lastScroll = 0;
  window.addEventListener('scroll', () => {{
    const current = window.scrollY;
    navbar.classList.toggle('scrolled', current > 20);
    navbar.classList.toggle('hidden', current > 150 && current > lastScroll);
    lastScroll = current;
  }}, {{passive:true}});

  // 2. Mobile menu
  const toggle = document.querySelector('.menu-toggle');
  const navLinks = document.querySelector('.nav-links');
  if(toggle) toggle.addEventListener('click', () => navLinks.classList.toggle('open'));

  // 3. Fade-up on scroll
  const observer = new IntersectionObserver(entries => {{
    entries.forEach(e => {{ if(e.isIntersecting) {{ e.target.classList.add('visible'); observer.unobserve(e.target); }} }});
  }}, {{threshold: 0.12}});
  document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));

  // 4. Count-up animation
  const countUp = (el) => {{
    const target = parseFloat(el.dataset.count);
    const isFloat = el.dataset.count.includes('.');
    const duration = 2000;
    const start = performance.now();
    const update = (time) => {{
      const progress = Math.min((time - start) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      const value = target * ease;
      el.textContent = isFloat ? value.toFixed(1) : Math.floor(value).toLocaleString();
      if(progress < 1) requestAnimationFrame(update);
    }};
    requestAnimationFrame(update);
  }};
  const statsObserver = new IntersectionObserver(entries => {{
    entries.forEach(e => {{ if(e.isIntersecting) {{ countUp(e.target); statsObserver.unobserve(e.target); }} }});
  }}, {{threshold:0.5}});
  document.querySelectorAll('.stat-number[data-count]').forEach(el => statsObserver.observe(el));

  // 5. Active nav link on scroll
  const sections = document.querySelectorAll('section[id]');
  const navAnchors = document.querySelectorAll('.nav-links a');
  const activateNav = () => {{
    const scrollY = window.scrollY + 100;
    sections.forEach(sec => {{
      if(scrollY >= sec.offsetTop && scrollY < sec.offsetTop + sec.offsetHeight) {{
        navAnchors.forEach(a => {{ a.classList.toggle('active', a.getAttribute('href') === '#'+sec.id); }});
      }}
    }});
  }};
  window.addEventListener('scroll', activateNav, {{passive:true}});

  // 6. Contact form
  const form = document.querySelector('.contact-form');
  if(form) form.addEventListener('submit', (e) => {{
    e.preventDefault();
    const btn = form.querySelector('button[type=submit]');
    btn.textContent = '✓ Sent!';
    btn.style.background = '#10b981';
    setTimeout(() => {{ btn.textContent = 'Send Message'; btn.style.background = ''; form.reset(); }}, 3000);
  }});

  // 7. Smooth scroll anchors
  document.querySelectorAll('a[href^="#"]').forEach(a => {{
    a.addEventListener('click', e => {{
      const t = document.querySelector(a.getAttribute('href'));
      if(t) {{ e.preventDefault(); t.scrollIntoView({{behavior:'smooth', block:'start'}}); navLinks.classList.remove('open'); }}
    }});
  }});

}});

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HTML CONTENT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
index.html MUST include these sections in order:
1. <nav class="navbar"> — logo + links + CTA button + hamburger
2. <section class="hero"> — eyebrow tag + H1 with <span> accent + subtext + 2 buttons + hero-img-wrap with hero-badge
3. <section class="stats-bar"> — 4 stats with data-count attribute for animation
4. <section class="section" id="features"> — section-tag + section-title + section-sub + grid-3 of 3 cards with card-icon
5. <section class="section bg-secondary" id="products"> — 3-4 product/offer cards with images
6. <section class="section" id="testimonials"> — 3 testimonial-card with stars + quote + avatar
7. <section class="cta-section"> — bold H2 + subtext + btn-white
8. <footer class="footer"> — footer-grid with brand + 3 link columns + footer-bottom

Images: https://picsum.photos/seed/RELEVANT_WORD/WIDTH/HEIGHT
Use meaningful seed words related to the brand (e.g. /seed/bread/800/500 for a bakery)

Every HTML file: <link rel="stylesheet" href="style.css"> + <script src="script.js" defer></script>
Add class="fade-up" to every card, section title, and content block.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — MANDATORY (no backticks, no markdown)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

---style.css---
[complete CSS — extend the foundation above with brand colors and any extras]

---script.js---
[complete JavaScript — use the template above verbatim then add any extras]

---index.html---
[complete HTML for homepage]

---about.html---
[complete HTML for about page]

---services.html---
[complete HTML for services page]

---contact.html---
[complete HTML with styled form and map placeholder]
"""
    return _chat(client, provider, model, prompt, max_tokens=8000)


def _generate_all_simple(idea, language, model, client, provider):
    """High-quality fallback prompt."""
    prompt = f"""You are a world-class frontend developer. Build a stunning professional website.

Website: {idea}
Language: {language}

Use the following CSS foundation (mandatory):
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Inter', sans-serif; -webkit-font-smoothing: antialiased; }}

Design level: Stripe / Linear / Vercel — premium, minimal, world-class.
Hero: full viewport, clamp() headline, 2 CTA buttons.
Navbar: sticky glassmorphism.
Cards: hover lift + shadow.
Images: https://picsum.photos/seed/[brand_word]/800/500

Output EXACTLY (no backticks):

---style.css---
[CSS]

---script.js---
[JS with IntersectionObserver, navbar scroll, mobile menu, count-up, smooth scroll]

---index.html---
[HTML]

---about.html---
[HTML]

---services.html---
[HTML]

---contact.html---
[HTML with contact form]
"""
    return _chat(client, provider, model, prompt, max_tokens=8000)


def _generate_css_only(idea, language, model, client, provider):
    prompt = f"""Generate a world-class CSS design system for: {idea}.
Use Inter from Google Fonts. Full CSS variables system. Premium minimal design like Stripe.
Return ONLY CSS."""
    return _chat(client, provider, model, prompt, max_tokens=4000)


# ================================
#  Design System
# ================================

def generate_design_system(idea, language, model,
                            client=None, provider="openai", api_key=""):
    if client is None:
        client, provider = _get_client(provider, api_key)

    prompt = f"""
You are a senior UI designer.

Create a modern responsive CSS design system.

Website idea:
{idea}

Language:
{language}

Return ONLY CSS — no markdown, no explanation.

Design style:
- Modern, clean, minimal startup landing page
- Large spacing, rounded cards, soft shadows

Include:
- CSS variables (--primary, --accent, --bg, --text)
- Color palette and typography
- Container (max-width 1200px), grid system
- Cards, buttons, navbar, footer
- Responsive mobile layout

Animations:
.fade-in {{ opacity:0; transform:translateY(20px); transition:opacity .6s,transform .6s; }}
.fade-in-visible {{ opacity:1; transform:translateY(0); }}

Images:
img {{ max-width:100%; border-radius:12px; }}

Maximum 300 lines.
"""
    return _chat(client, provider, model, prompt, max_tokens=5000)


# ================================
#  Page Generator
# ================================

def generate_pages(idea, language, model,
                   client=None, provider="openai", api_key=""):
    if client is None:
        client, provider = _get_client(provider, api_key)

    prompt = f"""
You are an expert UI designer and senior frontend developer.
Use modern CSS layout with Flexbox and Grid.
Use large padding between sections (80px+).
Each section must be visually separated.

Create a modern professional website.

Website idea:
{idea}

Language:
{language}

The CSS file "style.css" already exists.
Use classes: container, grid, card, btn, fade-in, navbar, footer

LAYOUT STRUCTURE:
<header class="navbar"></header>
<section class="hero container"></section>
<section class="features container grid"></section>
<section class="products container grid"></section>
<section class="testimonials container grid"></section>
<section class="gallery container grid"></section>
<section class="cta container"></section>
<footer class="footer"></footer>

Images: use https://picsum.photos (e.g. <img src="https://picsum.photos/600/400" alt="image">)

Every HTML page must include:
<link rel="stylesheet" href="style.css">
<script src="script.js"></script>

INDEX PAGE SECTIONS:
1. Hero (headline, description, button, image)
2. Features (3 cards)
3. Products/Offers (grid cards)
4. Testimonials (3 cards)
5. Gallery
6. Call to action
7. Footer

TEXT RULES: Short marketing sentences, max 16 words each.

IMPORTANT OUTPUT FORMAT — use EXACTLY this pattern (no markdown, no backticks):

---script.js---
JavaScript code here

---index.html---
HTML code here

---about.html---
HTML code here

---services.html---
HTML code here

---contact.html---
HTML code here
"""
    return _chat(client, provider, model, prompt, max_tokens=5000)


# ================================
#  Available Models
# ================================

DEFAULT_MODEL    = "gpt-5-mini"
DEFAULT_PROVIDER = "openai"

def get_models_for_provider(provider: str) -> list:
    """Return all available models for each provider."""
    provider = provider.lower()

    if provider == "openai":
        return [
            # --- GPT-5 family (latest) ---
            "gpt-5-mini",
            "gpt-5-mini-2025-08-07",
            "gpt-5",
            "gpt-5-2025-08-07",
            "gpt-5.1",
            "gpt-5.2",
            "gpt-5.4",
            # --- GPT-4o family ---
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4o-2024-11-20",
            "gpt-4o-2024-08-06",
            "gpt-4o-2024-05-13",
            # --- GPT-4.1 family ---
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            # --- GPT-4 Turbo ---
            "gpt-4-turbo",
            "gpt-4-turbo-2024-04-09",
            # --- GPT-4 base ---
            "gpt-4",
            "gpt-4-32k",
            # --- GPT-3.5 ---
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            # --- o-series (reasoning) ---
            "o1",
            "o1-mini",
            "o3",
            "o3-mini",
            "o4-mini",
        ]
    elif provider == "anthropic":
        return [
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
        ]
    elif provider == "gemini":
        return [
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]
    else:
        return []


def get_default_model(provider: str = DEFAULT_PROVIDER) -> str:
    """Return the default model for the given provider."""
    defaults = {
        "openai":    "gpt-5-mini",
        "anthropic": "claude-sonnet-4-5",
        "gemini":    "gemini-2.0-flash",
    }
    return defaults.get(provider.lower(), "gpt-5-mini")


# ================================
#  FILE EXTRACTION
# ================================

def extract_files(result: str) -> dict:
    """Parse AI multi-file output — handles several separator styles."""
    if not result:
        return {}

    # 1. تنظيف markdown fences
    result = re.sub(r"```(?:html|css|javascript|js)?\n?", "", result)
    result = result.replace("```", "")

    files = {}
    targets = ["style.css", "script.js", "index.html",
               "about.html", "services.html", "contact.html"]

    for name in targets:
        content = ""

        # نمط 1: ---filename---
        m = re.search(rf"---\s*{re.escape(name)}\s*---(.*?)(?=---\w|$)", result, re.S | re.I)
        if m:
            content = m.group(1).strip()

        # نمط 2: === filename === أو == filename ==
        if not content:
            m = re.search(rf"={2,3}\s*{re.escape(name)}\s*={2,3}(.*?)(?====|$)", result, re.S | re.I)
            if m:
                content = m.group(1).strip()

        # نمط 3: # filename أو ## filename
        if not content:
            m = re.search(rf"#+\s*{re.escape(name)}\s*\n(.*?)(?=#+\s*\w|$)", result, re.S | re.I)
            if m:
                content = m.group(1).strip()

        files[name] = content

    # fallback خاص: إذا لم يُوجد index.html لكن الرد يحتوي على DOCTYPE
    if not files.get("index.html"):
        m = re.search(r"(<!DOCTYPE html>.*?</html>)", result, re.S | re.I)
        if m:
            files["index.html"] = m.group(1).strip()
            log.info("index.html recovered via DOCTYPE fallback")

    return files


# ================================
#  HTML IMPROVER
# ================================

def improve_html(html: str, model: str, provider="openai", api_key="") -> str:
    """Redesign and improve HTML to world-class quality."""
    client, provider = _get_client(provider, api_key)

    prompt = f"""You are a world-class UI/UX designer (think Stripe, Linear, Apple level).
Redesign and elevate this HTML to a premium, professional standard.

IMPROVEMENTS TO MAKE:
✦ Semantic HTML5 (header, nav, main, section, article, footer)
✦ Add missing sections if thin (stats bar, testimonials, CTA)
✦ Upgrade typography: larger headings with clamp(), better line-height
✦ Upgrade spacing: generous padding (80-120px sections), breathing room
✦ Upgrade cards: add hover lift effect classes, better shadow
✦ Upgrade buttons: add proper classes for hover/active states
✦ Upgrade navbar: add sticky + glassmorphism class
✦ Add aria-labels, alt text, meta description
✦ Add fade-in animation classes to all sections
✦ Upgrade image usage: use https://picsum.photos/seed/[word]/800/500
✦ Ensure mobile responsive structure

Return ONLY the improved HTML — no explanation, no markdown fences.

HTML TO IMPROVE:
{html}
"""
    improved = _chat(client, provider, model, prompt, max_tokens=6000)
    improved = re.sub(r"^```[a-z]*\n?", "", improved.strip())
    improved = re.sub(r"\n?```$", "", improved.strip())
    return improved


# ================================
#  DEFAULT script.js FALLBACK
# ================================

def _default_script() -> str:
    return """document.addEventListener("DOMContentLoaded", () => {

  // Scroll fade-in animations
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("fade-in-visible");
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll(".fade-in").forEach(el => observer.observe(el));

  // Mobile menu toggle
  const menuBtn = document.querySelector(".menu-toggle");
  const nav     = document.querySelector(".nav-links");
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", () => nav.classList.toggle("active"));
  }

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener("click", e => {
      const target = document.querySelector(a.getAttribute("href"));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: "smooth" });
      }
    });
  });

});
"""