import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

"""
Visual Editor v9  —  Enhanced Panel
=====================================
New in v9:
  • Resizable panel (drag handle on left edge + width presets)
  • Copy / Paste style between elements
  • Copy text / hex colors to clipboard
  • Pinned "quick bar" always visible at top (selected element + quick actions)
  • Smooth section collapse with memory
  • Compact / Normal / Wide view modes
  • Better color pickers with recent colors strip
  • Undo stack (per-session)
"""

import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
import threading, webbrowser, json, re, os, base64, mimetypes, shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# ══════════════════════════════════════════════════════
#  Global state
# ══════════════════════════════════════════════════════
_server       = None
_html_path           = None
_get_current_file_fn = None   # lambda that returns the currently open file path
_code_editor  = None
_provider_fn  = None
_model_fn     = None
_port         = 7788
_last_click   = {}
_pending_cmds = []
_lock         = threading.Lock()

# ══════════════════════════════════════════════════════
#  JS injected into page
# ══════════════════════════════════════════════════════
INJECT_JS = r"""<!-- __VE__ -->
<style>
#__ve_ov__{position:fixed;pointer-events:none;z-index:2147483646;
  outline:2px dashed #00d4aa;background:rgba(0,212,170,.06);display:none;border-radius:3px;
  transition:top .05s,left .05s,width .05s,height .05s;}
#__ve_tag__{position:fixed;z-index:2147483647;background:#00d4aa;color:#000;
  font:700 10px/1 monospace;padding:2px 6px;border-radius:0 0 4px 0;pointer-events:none;display:none;}
</style>
<div id="__ve_ov__"></div><div id="__ve_tag__"></div>
<script>
(function(){
  var sel=null,ov=document.getElementById('__ve_ov__'),tg=document.getElementById('__ve_tag__');
  function rgb2hex(c){
    if(!c||c==='transparent')return '#000000';
    if(c[0]==='#')return c.length===4?'#'+c[1]+c[1]+c[2]+c[2]+c[3]+c[3]:c;
    var m=c.match(/\d+/g);if(!m)return '#000000';
    return '#'+[m[0],m[1],m[2]].map(function(n){return('0'+parseInt(n).toString(16)).slice(-2)}).join('');
  }
  function snap(el){
    var r=el.getBoundingClientRect(),st=window.scrollY||0,sl=window.scrollX||0;
    Object.assign(ov.style,{display:'block',
      top:(r.top+st)+'px',left:(r.left+sl)+'px',
      width:r.width+'px',height:r.height+'px'});
    tg.style.cssText='display:block;top:'+(r.top+st)+'px;left:'+(r.left+sl)+'px;';
    tg.textContent='<'+el.tagName.toLowerCase()+'>';
  }
  function getInfo(el){
    var cs=window.getComputedStyle(el),st=el.style;
    var bgImg=cs.backgroundImage||'';
    var bgUrl='';
    var bgMatch=bgImg.match(/url\(["']?([^"')]+)["']?\)/);
    if(bgMatch) bgUrl=bgMatch[1];
    var tag=el.tagName.toLowerCase();
    var cls=(el.className&&el.className.toString?el.className.toString().trim():'');
    var eid=el.id||'';
    // Index among same tag+firstClass siblings — for Python to pick exact element
    var elIndex=0;
    try{
      var selector=tag+(eid?'#'+eid:(cls?'.'+cls.split(/\s+/)[0]:''));
      var sibs=document.querySelectorAll(selector);
      for(var i=0;i<sibs.length;i++){if(sibs[i]===el){elIndex=i;break;}}
    }catch(e){}
    // cleanStyle: real HTML style attribute minus VE-injected outline
    var rawStyle=el.getAttribute('style')||'';
    var cleanStyle=rawStyle.replace(/;?\s*outline\s*:[^;]*/gi,'').replace(/^;\s*/,'').trim();
    return {
      tag:tag,id:eid,
      cls:(cls?cls.substring(0,120):''),
      elIndex:elIndex,
      cleanStyle:cleanStyle,
      inlineStyle:rawStyle,
      text:(el.childNodes.length===1&&el.childNodes[0].nodeType===3)?(el.innerText||'').substring(0,400):(el.innerText||'').substring(0,400),
      href:el.tagName==='A'?(el.getAttribute('href')||''):'',
      src:el.tagName==='IMG'?(el.getAttribute('src')||''):'',
      alt:el.tagName==='IMG'?(el.getAttribute('alt')||''):'',
      isImg:el.tagName==='IMG',isLink:el.tagName==='A',
      isBgImg:el.tagName!=='IMG'&&bgUrl!='',bgImage:bgUrl,
      color:rgb2hex(cs.color),background:rgb2hex(cs.backgroundColor),
      fontSize:parseFloat(cs.fontSize)||16,fontFamily:cs.fontFamily,
      fontWeight:cs.fontWeight,fontStyle:cs.fontStyle,
      textAlign:cs.textAlign,textDecoration:cs.textDecoration,
      letterSpacing:cs.letterSpacing,lineHeight:cs.lineHeight,
      paddingTop:parseFloat(cs.paddingTop)||0,paddingRight:parseFloat(cs.paddingRight)||0,
      paddingBottom:parseFloat(cs.paddingBottom)||0,paddingLeft:parseFloat(cs.paddingLeft)||0,
      marginTop:parseFloat(cs.marginTop)||0,marginRight:parseFloat(cs.marginRight)||0,
      marginBottom:parseFloat(cs.marginBottom)||0,marginLeft:parseFloat(cs.marginLeft)||0,
      borderWidth:parseFloat(cs.borderTopWidth)||0,
      borderStyle:cs.borderTopStyle||'none',borderColor:rgb2hex(cs.borderTopColor),
      borderRadius:parseFloat(cs.borderTopLeftRadius)||0,
      width:cs.width,height:cs.height,display:cs.display,opacity:cs.opacity,
      boxShadow:st.boxShadow||'',transform:st.transform||''
    };
  }
  document.addEventListener('mouseover',function(e){
    if(e.target.id==='__ve_ov__'||e.target.id==='__ve_tag__') return;
    snap(e.target);
  },true);
  document.addEventListener('mouseout',function(){
    ov.style.display='none'; tg.style.display='none';
  },true);
  document.addEventListener('click',function(e){
    if(e.target.id==='__ve_ov__'||e.target.id==='__ve_tag__') return;
    e.preventDefault(); e.stopPropagation();
    if(sel) sel.style.outline='';
    sel=e.target; sel.style.outline='2px solid #ff6b35';
    ov.style.display='none'; tg.style.display='none';
    fetch('/__ve_click__',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(getInfo(sel))}).catch(function(){});
  },true);
  window.__ve_apply__=function(p,v){
    if(!sel) return;
    var s=sel.style;
    if(p==='text'){if(sel.childNodes.length===1&&sel.childNodes[0].nodeType===3)sel.childNodes[0].nodeValue=v;else sel.innerText=v;}
    else if(p==='href'&&sel.tagName==='A')sel.href=v;
    else if(p==='src'){
      var imgEl=sel;
      if(imgEl.tagName!=='IMG'){imgEl=imgEl.querySelector('img')||imgEl.closest('img');}
      if(imgEl&&imgEl.tagName==='IMG'){imgEl.setAttribute('src',v);imgEl.src=v;}
    }
    else if(p==='alt'){
      var imgEl2=sel;
      if(imgEl2.tagName!=='IMG'){imgEl2=imgEl2.querySelector('img')||imgEl2.closest('img');}
      if(imgEl2&&imgEl2.tagName==='IMG'){imgEl2.setAttribute('alt',v);imgEl2.alt=v;}
    }
    else if(p==='color')s.color=v;
    else if(p==='background'){
      // Don't overwrite background-image with background shorthand
      // Only set background-color
      s.backgroundColor=v;
    }
    else if(p==='fontSize')s.fontSize=v+'px';
    else if(p==='fontFamily')s.fontFamily=v;
    else if(p==='fontWeight')s.fontWeight=v;
    else if(p==='fontStyle')s.fontStyle=v;
    else if(p==='textAlign')s.textAlign=v;
    else if(p==='textDecoration')s.textDecoration=v;
    else if(p==='letterSpacing')s.letterSpacing=v+'px';
    else if(p==='lineHeight')s.lineHeight=v;
    else if(p==='paddingTop')s.paddingTop=v+'px';
    else if(p==='paddingRight')s.paddingRight=v+'px';
    else if(p==='paddingBottom')s.paddingBottom=v+'px';
    else if(p==='paddingLeft')s.paddingLeft=v+'px';
    else if(p==='marginTop')s.marginTop=v+'px';
    else if(p==='marginRight')s.marginRight=v+'px';
    else if(p==='marginBottom')s.marginBottom=v+'px';
    else if(p==='marginLeft')s.marginLeft=v+'px';
    else if(p==='borderWidth')s.borderWidth=v+'px';
    else if(p==='borderStyle')s.borderStyle=v;
    else if(p==='borderColor')s.borderColor=v;
    else if(p==='borderRadius')s.borderRadius=v+'px';
    else if(p==='width')s.width=v;
    else if(p==='height')s.height=v;
    else if(p==='opacity')s.opacity=v;
    else if(p==='display')s.display=v;
    else if(p==='boxShadow')s.boxShadow=v;
    else if(p==='transform')s.transform=v;
    else if(p==='__paste_style__'){
      try{var obj=JSON.parse(v);Object.keys(obj).forEach(function(k){s[k]=obj[k];});}catch(e){}
    }
  };
  window.__ve_get_style__=function(){
    if(!sel) return '{}';
    var s=sel.style,out={};
    ['color','background','fontSize','fontFamily','fontWeight','fontStyle',
     'textAlign','textDecoration','letterSpacing','lineHeight',
     'paddingTop','paddingRight','paddingBottom','paddingLeft',
     'marginTop','marginRight','marginBottom','marginLeft',
     'borderWidth','borderStyle','borderColor','borderRadius',
     'opacity','boxShadow','transform'].forEach(function(k){if(s[k])out[k]=s[k];});
    return JSON.stringify(out);
  };
  window.__ve_save__=function(){
    var cl=document.documentElement.cloneNode(true);
    // Remove VE injected elements
    cl.querySelectorAll('[id^="__ve_"]').forEach(function(el){el.remove();});
    cl.querySelectorAll('style,script').forEach(function(el){
      if(el.textContent&&el.textContent.includes('__ve_'))el.remove();
    });
    var origin=window.location.origin;
    // Clean ALL inline styles: remove ONLY browser-computed junk, keep user edits
    cl.querySelectorAll('[style]').forEach(function(el){
      var s=el.getAttribute('style')||'';
      // Remove VE outline
      s=s.replace(/;?\s*outline\s*:[^;]*/gi,'');
      // Remove computed-only properties (rgb values not set by user)
      s=s.replace(/;?\s*color\s*:\s*rgb\s*\([^)]*\)/gi,'');
      s=s.replace(/;?\s*background\s*:\s*rgb\s*\([^)]*\)/gi,'');
      s=s.replace(/;?\s*background-color\s*:\s*rgb\s*\([^)]*\)/gi,'');
      s=s.replace(/;?\s*border-color\s*:\s*rgb\s*\([^)]*\)/gi,'');
      // Remove broken partial properties left by cleanup (e.g. "border-;")
      s=s.replace(/;?\s*[\w-]+\s*:\s*;/g,'');
      s=s.replace(/;?\s*[\w-]+\s*-\s*;/g,'');
      // Remove display/border-style/other computed-only props browsers inject
      s=s.replace(/;?\s*border-style\s*:\s*none/gi,'');
      s=s.replace(/;?\s*display\s*:\s*(block|inline-block|flex|grid|inline)/gi,'');
      // Clean up leading/trailing semicolons and spaces
      s=s.replace(/^\s*;+\s*/,'').replace(/;\s*;+/g,';').trim();
      if(s) el.setAttribute('style',s);
      else el.removeAttribute('style');
    });
    // Fix img src: decode URL encoding and strip server origin
    cl.querySelectorAll('img[src]').forEach(function(img){
      var s=img.getAttribute('src')||'';
      if(s.indexOf(origin)===0) s=s.replace(origin,'');
      try{ s=decodeURIComponent(s); }catch(e){}
      img.setAttribute('src',s);
    });
    // Fix background-image urls: decode URL encoding and strip origin
    cl.querySelectorAll('[style]').forEach(function(el){
      var s=el.getAttribute('style')||'';
      if(s.indexOf(origin)>=0){
        s=s.replace(new RegExp(origin.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'g'),'');
      }
      try{ s=s.replace(/url\("([^"]+)"\)/g,function(m,u){return 'url("'+decodeURIComponent(u)+'")';});}catch(e){}
      el.setAttribute('style',s);
    });
    return '<!DOCTYPE html>\n'+cl.outerHTML;
  };
  window.__ve_do_save__=function(){
    // DISABLED: Python (_upload_img) is the sole file writer.
    // DOM-based save pollutes the HTML with computed styles.
    document.title='✓ '+document.title.replace(/^[✓✗][^—]*— /,'');
    setTimeout(function(){document.title=document.title.replace(/^✓ /,'');},1500);
  };
  setInterval(function(){
    fetch('/__ve_poll__').then(function(r){return r.json();}).then(function(cmds){
      cmds.forEach(function(c){
        if(c.p==='__save__') window.__ve_do_save__();
        else if(c.p==='__reload__') window.location.reload();
        else if(c.p==='__get_style__'){
          var st=window.__ve_get_style__();
          fetch('/__ve_style_reply__',{method:'POST',
            headers:{'Content-Type':'application/json'},body:JSON.stringify({style:st})}).catch(function(){});
        }
        else window.__ve_apply__(c.p,c.v);
      });
    }).catch(function(){});
  },150);
})();
</script>"""

# ══════════════════════════════════════════════════════
#  HTTP Handler
# ══════════════════════════════════════════════════════
_style_reply = {}
_undo_stack  = []   # list of (html_path, html_content) snapshots

class VEHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, body, mime="text/html; charset=utf-8", status=200):
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data):
        self._send(json.dumps(data).encode(), "application/json")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/__ve_poll__":
            with _lock:
                cmds = list(_pending_cmds); _pending_cmds.clear()
            self._json(cmds); return
        if path in ("/", ""):
            html_file = os.path.abspath(_html_path) if _html_path else None
            print(f"[VE SERVER] Serving: {html_file}")
            try: html = open(html_file, encoding="utf-8").read()
            except Exception as e: self._send(f"Error: {e}".encode(), status=500); return
            pos = html.lower().rfind("</body>")
            if pos >= 0: html = html[:pos] + "\n" + INJECT_JS + "\n" + html[pos:]
            else: html += "\n" + INJECT_JS
            self._send(html); return
        folder = os.path.dirname(_html_path)
        fpath  = os.path.join(folder, path.lstrip("/"))
        if os.path.isfile(fpath):
            mime = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
            with open(fpath, "rb") as f: self._send(f.read(), mime)
        else:
            self._send(b"404", status=404)

    def do_POST(self):
        global _last_click, _style_reply
        length = int(self.headers.get("Content-Length", 0))
        try: body = json.loads(self.rfile.read(length))
        except Exception as e: self._json({"ok": False, "error": str(e)}); return
        path = urllib.parse.urlparse(self.path).path

        if path == "/__ve_click__":
            with _lock: _last_click = dict(body)
            self._json({"ok": True})
        elif path == "/__ve_style_reply__":
            with _lock: _style_reply = dict(body)
            self._json({"ok": True})
        elif path == "/__ve_save__":
            # Browser-side save: update the code editor display ONLY
            # Do NOT write to disk — Python (_upload_img) is the single source of truth
            try:
                html = body.get("html", "")
                # Only update editor display, skip file write
                if _code_editor:
                    def _u():
                        _code_editor.delete("1.0", tk.END)
                        _code_editor.insert(tk.END, html)
                        try: _code_editor.edit_modified(False)
                        except: pass
                    _code_editor.after(0, _u)
                self._json({"ok": True})
            except Exception as e: self._json({"ok": False, "error": str(e)})
        elif path == "/__ve_upload__":
            try:
                data = body.get("data", ""); name = body.get("name", "img.png")
                if "," in data: data = data.split(",", 1)[1]
                dest = os.path.join(os.path.dirname(_html_path), name)
                with open(dest, "wb") as f: f.write(base64.b64decode(data))
                self._json({"ok": True, "url": f"/{name}"})
            except Exception as e: self._json({"ok": False, "error": str(e)})
        elif path == "/__ve_ai__":
            try:
                html = body.get("html", ""); req = body.get("request", "")
                from core.ai_engine import _call_ai
                prompt = (f"You are a senior frontend engineer.\nUser request: {req}\n"
                          f"Current HTML:\n{html}\nReturn ONLY the complete updated HTML. No markdown.")
                new_html = _call_ai(prompt, _model_fn(), _provider_fn())
                new_html = re.sub(r'^```[a-z]*\n?', '', new_html.strip())
                new_html = re.sub(r'\n?```$', '', new_html.strip())
                with open(_html_path, "w", encoding="utf-8") as f: f.write(new_html)
                if _code_editor:
                    def _u():
                        _code_editor.delete("1.0", tk.END)
                        _code_editor.insert(tk.END, new_html)
                    _code_editor.after(0, _u)
                self._json({"ok": True})
            except Exception as e: self._json({"ok": False, "error": str(e)})
        else:
            self._send(b"404", status=404)


def _find_free_port():
    import socket
    for p in range(7788, 7900):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", p)); s.close(); return p
        except: pass
    return 7788

def _start_server():
    global _server, _port
    if _server: return
    _port = _find_free_port()
    _server = HTTPServer(("127.0.0.1", _port), VEHandler)
    threading.Thread(target=_server.serve_forever, daemon=True).start()


# ══════════════════════════════════════════════════════
#  Design tokens
# ══════════════════════════════════════════════════════
C = {
    "bg":      "#0c0c16",
    "bg2":     "#12121e",
    "bg3":     "#1a1a2c",
    "bg4":     "#222238",
    "border":  "#2a2a42",
    "accent":  "#00d4aa",
    "accent2": "#7c6fff",
    "accent3": "#ff6b35",
    "text":    "#d0d0ec",
    "muted":   "#5a5a7a",
    "label":   "#8888aa",
    "green":   "#2d6a4f",
    "red":     "#ff5555",
    "yellow":  "#f4c430",
}

PANEL_WIDTHS = {"Compact": 260, "Normal": 320, "Wide": 420}

# ══════════════════════════════════════════════════════
#  Reusable UI widgets
# ══════════════════════════════════════════════════════
def lbl(parent, text, size=9, color=None, bold=False, mono=False):
    font_family = "Consolas" if mono else "Segoe UI"
    font = (font_family, size, "bold") if bold else (font_family, size)
    return tk.Label(parent, text=text, fg=color or C["label"],
                    bg=C["bg"], font=font)

def entry(parent, var, width=None, mono=False):
    font = ("Consolas", 10) if mono else ("Segoe UI", 10)
    kw = dict(textvariable=var, bg=C["bg2"], fg=C["text"],
              insertbackground=C["text"], relief="flat", font=font, bd=0,
              highlightthickness=1, highlightcolor=C["accent2"],
              highlightbackground=C["border"])
    if width: kw["width"] = width
    return tk.Entry(parent, **kw)

def btn(parent, text, cmd, fg=None, bg=None, padx=10, pady=5, size=9, bold=False):
    font = ("Segoe UI", size, "bold") if bold else ("Segoe UI", size)
    return tk.Button(parent, text=text, command=cmd,
                     bg=bg or C["bg3"], fg=fg or C["text"],
                     activebackground=C["bg4"], activeforeground="white",
                     bd=0, padx=padx, pady=pady, font=font,
                     cursor="hand2", relief="flat")

def sep(parent, color=None, pady=4):
    tk.Frame(parent, bg=color or C["border"], height=1).pack(
        fill="x", pady=pady)


# ══════════════════════════════════════════════════════
#  Color picker with recent colors
# ══════════════════════════════════════════════════════
_recent_colors = []

class ColorPicker(tk.Frame):
    def __init__(self, parent, on_change, label=""):
        super().__init__(parent, bg=C["bg"])
        self._cb = on_change
        self._val = "#000000"
        self._build(label)

    def _build(self, label):
        # row: swatch | hex entry | pick btn | copy btn
        row = tk.Frame(self, bg=C["bg"]); row.pack(fill="x")

        self._swatch = tk.Label(row, bg="#000000", width=3,
                                 cursor="hand2", relief="flat", bd=1)
        self._swatch.pack(side="left", padx=(0,6), ipady=9)
        self._swatch.bind("<Button-1>", self._pick)

        self._var = tk.StringVar(value="#000000")
        e = entry(row, self._var, width=8, mono=True)
        e.pack(side="left", ipady=4)
        self._var.trace_add("write", self._on_type)

        btn(row, "🎨", self._pick, bg=C["bg3"], padx=6, pady=3
            ).pack(side="left", padx=3)
        btn(row, "📋", self._copy_hex, bg=C["bg3"], padx=6, pady=3
            ).pack(side="left")

    def _pick(self, *_):
        c = colorchooser.askcolor(color=self._val, title="Pick color")[1]
        if c:
            c = c.lower()
            self.set(c); self._cb(c)
            global _recent_colors
            if c not in _recent_colors:
                _recent_colors = ([c] + _recent_colors)[:10]

    def _on_type(self, *_):
        v = self._var.get().strip()
        if re.match(r'^#[0-9a-fA-F]{6}$', v):
            self._val = v
            try: self._swatch.config(bg=v)
            except: pass
            self._cb(v)

    def _copy_hex(self):
        self.clipboard_clear()
        self.clipboard_append(self._val)

    def set(self, color):
        if not color or color == "transparent": color = "#000000"
        self._val = color
        self._var.set(color)
        try: self._swatch.config(bg=color)
        except: pass


# ══════════════════════════════════════════════════════
#  Collapsible Section
# ══════════════════════════════════════════════════════
class Section(tk.Frame):
    def __init__(self, parent, title, icon="", expanded=True):
        super().__init__(parent, bg=C["bg"])
        self._expanded = expanded
        self._icon = icon; self._title = title
        self._build()

    def _build(self):
        self._hdr = tk.Button(self, command=self._toggle,
                               bg=C["bg3"], fg=C["text"],
                               activebackground=C["bg4"],
                               activeforeground=C["accent"],
                               bd=0, pady=7, padx=12, anchor="w",
                               font=("Segoe UI", 9, "bold"),
                               cursor="hand2", relief="flat")
        self._hdr.pack(fill="x")
        self._refresh_hdr()

        self.body = tk.Frame(self, bg=C["bg"],
                              highlightbackground=C["border"],
                              highlightthickness=0)
        if self._expanded:
            self.body.pack(fill="x", padx=0, pady=(0,2))

    def _refresh_hdr(self):
        arrow = "▾" if self._expanded else "▸"
        self._hdr.config(text=f"  {arrow}  {self._icon}  {self._title}")

    def _toggle(self):
        self._expanded = not self._expanded
        self._refresh_hdr()
        if self._expanded: self.body.pack(fill="x", padx=0, pady=(0,2))
        else:               self.body.pack_forget()

    # Layout helpers
    def row(self, label, wfn, pady=3):
        f = tk.Frame(self.body, bg=C["bg"]); f.pack(fill="x", padx=12, pady=pady)
        if label:
            tk.Label(f, text=label, fg=C["label"], bg=C["bg"],
                     font=("Segoe UI",9), width=12, anchor="w").pack(side="left")
        w = wfn(f)
        if w: w.pack(side="left", fill="x", expand=True)
        return f

    def full(self, wfn, pady=3, padx=12):
        f = tk.Frame(self.body, bg=C["bg"]); f.pack(fill="x", padx=padx, pady=pady)
        w = wfn(f)
        if w: w.pack(fill="x")
        return f

    def grid2(self, items, pady=3):
        f = tk.Frame(self.body, bg=C["bg"]); f.pack(fill="x", padx=12, pady=pady)
        for i,(lbl_txt, wfn) in enumerate(items):
            col = tk.Frame(f, bg=C["bg"])
            col.pack(side="left", expand=True, fill="x", padx=(0,4 if i==0 else 0))
            if lbl_txt:
                tk.Label(col, text=lbl_txt, fg=C["label"], bg=C["bg"],
                         font=("Segoe UI",8)).pack(anchor="w")
            w = wfn(col)
            if w: w.pack(fill="x", ipady=4)
        return f


# ══════════════════════════════════════════════════════
#  Main Panel Window
# ══════════════════════════════════════════════════════
class PropsWindow(tk.Toplevel):

    WIDTHS = PANEL_WIDTHS
    MIN_W  = 220
    MAX_W  = 560

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🎨 Visual Editor")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self._panel_w   = self.WIDTHS["Normal"]
        self._suppress  = False
        self._clipboard   = {}    # copied styles
        self._undo        = []    # [(prop, old_val)]
        self._is_bg_img   = False
        self._current_alt = ""
        self._el_outer    = ""
        self._el_tag      = "div"
        self._el_id       = ""
        self._el_cls      = ""
        self._el_index    = 0
        self._el_style    = ""
        self._el_selector = ""
        self._el_index    = 0
        self._el_inline   = ""

        self.geometry(f"{self._panel_w}x{sh-80}+{sw-self._panel_w-12}+30")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.minsize(self.MIN_W, 400)

        # enable left-edge drag resize
        self._resize_start = None
        self.bind("<Configure>", self._on_configure)

        self._build()
        self._poll()

    # ══════════════════════════════════════════════════
    #  BUILD
    # ══════════════════════════════════════════════════
    def _build(self):
        # ── Top bar ─────────────────────────────────
        top = tk.Frame(self, bg="#07070f", pady=0); top.pack(fill="x")

        tk.Label(top, text="🎨", fg=C["accent"], bg="#07070f",
                 font=("Segoe UI",14)).pack(side="left", padx=(12,4), pady=8)
        tk.Label(top, text="Visual Editor", fg=C["text"], bg="#07070f",
                 font=("Segoe UI",11,"bold")).pack(side="left", pady=8)

        # Width presets
        for name, w in self.WIDTHS.items():
            b = btn(top, name, lambda ww=w: self._set_width(ww),
                    fg=C["muted"], bg="#07070f", padx=6, pady=4, size=8)
            b.pack(side="right", padx=2)

        # ── Quick bar (always visible) ──────────────
        qb = tk.Frame(self, bg=C["bg2"], pady=6); qb.pack(fill="x")

        # Element badge
        self.el_badge = tk.Label(qb, text="◯  nothing selected",
                                  fg=C["muted"], bg=C["bg2"],
                                  font=("Consolas",9))
        self.el_badge.pack(side="left", padx=12)

        # Quick action buttons
        for sym, tip, cmd in [
            ("📋", "Copy style",  self._copy_style),
            ("📌", "Paste style", self._paste_style),
            ("↩", "Undo",        self._undo_last),
            ("💾", "Save",        self._save),
        ]:
            b = btn(qb, sym, cmd, bg=C["bg3"], padx=7, pady=3, size=11)
            b.pack(side="right", padx=2)
            self._make_tooltip(b, tip)

        # ── Status strip ────────────────────────────
        self.status = tk.Label(self, text="← click any element in browser",
                                fg=C["muted"], bg=C["bg3"],
                                font=("Segoe UI",8), anchor="w", padx=12, pady=4)
        self.status.pack(fill="x")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        # ── Scrollable canvas ────────────────────────
        outer = tk.Frame(self, bg=C["bg"]); outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=C["bg"], bd=0, highlightthickness=0)
        vsb    = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                               bg=C["bg2"], troughcolor=C["bg2"], width=10)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._sf = tk.Frame(canvas, bg=C["bg"])
        self._wid = canvas.create_window((0,0), window=self._sf, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self._wid, width=e.width))
        self._sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)),"units"))
        self._canvas = canvas

        sf = self._sf

        # ════════ SECTIONS ═══════════════════════════

        # 1 · AI Edit
        ai = Section(sf, "AI EDIT", "✨", expanded=True); ai.pack(fill="x", pady=(0,1))
        self.ai_var = tk.StringVar()
        ai.full(lambda p: entry(p, self.ai_var), pady=4)
        ai.full(lambda p: btn(p, "⚡  Apply AI Change", self._ai_apply,
                               fg=C["accent2"], bg="#1a1a3a", pady=8, bold=True))
        tk.Frame(sf, bg=C["border"], height=1).pack(fill="x", pady=1)

        # 2 · Element
        el = Section(sf, "ELEMENT", "📌", expanded=True); el.pack(fill="x", pady=(0,1))

        self.txt_var = tk.StringVar()
        el.row("Text", lambda p: entry(p, self.txt_var), pady=4)
        self._trace(self.txt_var, "text")

        # Copy text button row
        def _txt_copy_row(p):
            b = btn(p, "📋 Copy text", lambda: self._copy_to_clipboard(self.txt_var.get()),
                    fg=C["muted"], bg=C["bg2"], padx=8, pady=3, size=8)
            return b
        el.full(_txt_copy_row, pady=(0,4))

        self.href_var = tk.StringVar()
        self._href_row = el.row("Link URL", lambda p: entry(p, self.href_var), pady=4)
        self._trace(self.href_var, "href")
        self._href_row.pack_forget()

        self.src_var = tk.StringVar()
        self._img_section = el.row("Img src", lambda p: entry(p, self.src_var), pady=4)
        self._trace(self.src_var, "src")
        self._img_section.pack_forget()

        self.alt_var = tk.StringVar()
        self._alt_row = el.row("Alt text", lambda p: entry(p, self.alt_var), pady=4)
        self._trace(self.alt_var, "alt")
        self._alt_row.pack_forget()

        el.full(lambda p: btn(p, "📤  Upload & Replace Image",
                               self._upload_img, fg=C["text"], bg=C["bg3"], pady=6),
                pady=(0,4))

        tk.Frame(sf, bg=C["border"], height=1).pack(fill="x", pady=1)

        # 3 · Typography
        ty = Section(sf, "TYPOGRAPHY", "🔤", expanded=True); ty.pack(fill="x", pady=(0,1))

        self.fsz_var = tk.StringVar()
        self.lh_var  = tk.StringVar()
        self.ls_var  = tk.StringVar()
        self.ff_var  = tk.StringVar()

        ty.grid2([("Font size px", lambda p: entry(p, self.fsz_var, 6)),
                  ("Line height",  lambda p: entry(p, self.lh_var,  6))])
        ty.grid2([("Letter sp px", lambda p: entry(p, self.ls_var,  6)),
                  ("Font family",  lambda p: entry(p, self.ff_var,  10))])
        self._trace(self.fsz_var, "fontSize")
        self._trace(self.lh_var,  "lineHeight")
        self._trace(self.ls_var,  "letterSpacing")
        self._trace(self.ff_var,  "fontFamily")

        # Style toggles
        tog = tk.Frame(ty.body, bg=C["bg"]); tog.pack(fill="x", padx=12, pady=4)
        tk.Label(tog, text="Style", fg=C["label"], bg=C["bg"],
                 font=("Segoe UI",9), width=12, anchor="w").pack(side="left")
        self._bold_b,   self._bold_s   = self._toggle_btn(tog, "B",  "fontWeight",    "bold",     "normal")
        self._italic_b, self._italic_s = self._toggle_btn(tog, "I",  "fontStyle",     "italic",   "normal")
        self._under_b,  self._under_s  = self._toggle_btn(tog, "U",  "textDecoration","underline","none")
        self._strike_b, self._strike_s = self._toggle_btn(tog, "S̶",  "textDecoration","line-through","none")

        # Text align
        aln = tk.Frame(ty.body, bg=C["bg"]); aln.pack(fill="x", padx=12, pady=4)
        tk.Label(aln, text="Align", fg=C["label"], bg=C["bg"],
                 font=("Segoe UI",9), width=12, anchor="w").pack(side="left")
        for a, sym in [("left","⬅"),("center","⬛"),("right","➡"),("justify","☰")]:
            btn(aln, sym, lambda x=a: self._send("textAlign", x),
                bg=C["bg3"], padx=9, pady=4).pack(side="left", padx=2)

        tk.Frame(sf, bg=C["border"], height=1).pack(fill="x", pady=1)

        # 4 · Colors
        co = Section(sf, "COLORS", "🎨", expanded=True); co.pack(fill="x", pady=(0,1))
        def _color_row(parent_body, label, cb):
            f = tk.Frame(parent_body, bg=C["bg"]); f.pack(fill="x", padx=12, pady=5)
            tk.Label(f, text=label, fg=C["label"], bg=C["bg"],
                     font=("Segoe UI",9), width=12, anchor="w").pack(side="left")
            picker = ColorPicker(f, cb)
            picker.pack(side="left", fill="x", expand=True)
            return picker

        self.col_pick = _color_row(co.body, "Text color", lambda v: self._send("color", v))
        self.bg_pick  = _color_row(co.body, "Background",  lambda v: self._send("background", v))
        self.bd_col   = _color_row(co.body, "Border clr",  lambda v: self._send("borderColor", v))

        # Recent colors strip
        self._recent_frame = tk.Frame(co.body, bg=C["bg"])
        self._recent_frame.pack(fill="x", padx=12, pady=(2,6))
        self._rebuild_recents()

        tk.Frame(sf, bg=C["border"], height=1).pack(fill="x", pady=1)

        # 5 · Spacing
        sp = Section(sf, "SPACING", "📐", expanded=False); sp.pack(fill="x", pady=(0,1))

        self.pt_var=tk.StringVar(); self.pr_var=tk.StringVar()
        self.pb_var=tk.StringVar(); self.pl_var=tk.StringVar()
        self.mt_var=tk.StringVar(); self.mr_var=tk.StringVar()
        self.mb_var=tk.StringVar(); self.ml_var=tk.StringVar()

        # Visual padding box widget
        pad_box = tk.Frame(sp.body, bg=C["bg"]); pad_box.pack(padx=12, pady=6)
        tk.Label(pad_box, text="PADDING", fg=C["muted"], bg=C["bg"],
                 font=("Segoe UI",7)).grid(row=0,column=1,pady=(0,2))
        entry(pad_box, self.pt_var, 5).grid(row=1,column=1,ipady=3)
        entry(pad_box, self.pl_var, 5).grid(row=2,column=0,ipady=3,padx=(0,4))
        tk.Frame(pad_box,bg=C["bg3"],width=50,height=30).grid(row=2,column=1)
        entry(pad_box, self.pr_var, 5).grid(row=2,column=2,ipady=3,padx=(4,0))
        entry(pad_box, self.pb_var, 5).grid(row=3,column=1,ipady=3,pady=(2,0))

        tk.Label(sp.body, text="MARGIN", fg=C["muted"], bg=C["bg"],
                 font=("Segoe UI",7)).pack()
        sp.grid2([("▲ Top",   lambda p: entry(p,self.mt_var,5)),
                  ("▼ Bottom",lambda p: entry(p,self.mb_var,5))])
        sp.grid2([("◀ Left",  lambda p: entry(p,self.ml_var,5)),
                  ("▶ Right", lambda p: entry(p,self.mr_var,5))])

        for var, prop in [(self.pt_var,"paddingTop"),(self.pr_var,"paddingRight"),
                          (self.pb_var,"paddingBottom"),(self.pl_var,"paddingLeft"),
                          (self.mt_var,"marginTop"),(self.mr_var,"marginRight"),
                          (self.mb_var,"marginBottom"),(self.ml_var,"marginLeft")]:
            self._trace(var, prop)

        tk.Frame(sf, bg=C["border"], height=1).pack(fill="x", pady=1)

        # 6 · Border & Shadow
        bd = Section(sf, "BORDER & SHADOW", "🔲", expanded=False); bd.pack(fill="x", pady=(0,1))

        self.bw_var=tk.StringVar(); self.br_var=tk.StringVar()
        self.bs_var=tk.StringVar(); self.shadow_var=tk.StringVar()
        self.transform_var=tk.StringVar()

        bd.grid2([("Width px",  lambda p: entry(p,self.bw_var,5)),
                  ("Radius px", lambda p: entry(p,self.br_var,5))])
        self._trace(self.bw_var, "borderWidth")
        self._trace(self.br_var, "borderRadius")

        bs_f = tk.Frame(bd.body, bg=C["bg"]); bs_f.pack(fill="x", padx=12, pady=3)
        tk.Label(bs_f, text="Style", fg=C["label"], bg=C["bg"],
                 font=("Segoe UI",9), width=12, anchor="w").pack(side="left")
        ttk.Combobox(bs_f, textvariable=self.bs_var, width=11,
                     values=["none","solid","dashed","dotted","double","groove","ridge"],
                     state="readonly", font=("Segoe UI",9)).pack(side="left")
        self.bs_var.trace_add("write", lambda *_: self._send("borderStyle", self.bs_var.get()))

        bd.row("Box shadow",  lambda p: entry(p, self.shadow_var))
        bd.row("Transform",   lambda p: entry(p, self.transform_var))
        self._trace(self.shadow_var, "boxShadow")
        self._trace(self.transform_var, "transform")

        # Shadow presets
        shadow_f = tk.Frame(bd.body, bg=C["bg"]); shadow_f.pack(fill="x", padx=12, pady=(0,6))
        tk.Label(shadow_f, text="Presets:", fg=C["muted"], bg=C["bg"],
                 font=("Segoe UI",8)).pack(side="left", padx=(0,4))
        for name, val in [("sm","0 1px 3px rgba(0,0,0,.3)"),
                           ("md","0 4px 12px rgba(0,0,0,.4)"),
                           ("lg","0 8px 30px rgba(0,0,0,.5)"),
                           ("none","none")]:
            btn(shadow_f, name, lambda v=val: (self.shadow_var.set(v), self._send("boxShadow",v)),
                bg=C["bg3"], padx=6, pady=2, size=8).pack(side="left", padx=2)

        tk.Frame(sf, bg=C["border"], height=1).pack(fill="x", pady=1)

        # 7 · Size & Layout
        sz = Section(sf, "SIZE & LAYOUT", "📏", expanded=False); sz.pack(fill="x", pady=(0,1))

        self.w_var=tk.StringVar(); self.h_var=tk.StringVar()
        self.op_var=tk.StringVar(); self.disp_var=tk.StringVar()

        sz.grid2([("Width",  lambda p: entry(p,self.w_var,8)),
                  ("Height", lambda p: entry(p,self.h_var,8))])
        self._trace(self.w_var, "width"); self._trace(self.h_var, "height")

        sz.row("Opacity 0-1", lambda p: entry(p, self.op_var, 6))
        self._trace(self.op_var, "opacity")

        df = tk.Frame(sz.body, bg=C["bg"]); df.pack(fill="x", padx=12, pady=3)
        tk.Label(df, text="Display", fg=C["label"], bg=C["bg"],
                 font=("Segoe UI",9), width=12, anchor="w").pack(side="left")
        ttk.Combobox(df, textvariable=self.disp_var, width=13,
                     values=["block","inline","inline-block","flex","grid","none","contents"],
                     state="readonly", font=("Segoe UI",9)).pack(side="left")
        self.disp_var.trace_add("write", lambda *_: self._send("display", self.disp_var.get()))

        # Opacity slider
        op_f = tk.Frame(sz.body, bg=C["bg"]); op_f.pack(fill="x", padx=12, pady=(2,8))
        tk.Label(op_f, text="Opacity", fg=C["label"], bg=C["bg"],
                 font=("Segoe UI",9), width=12, anchor="w").pack(side="left")
        sl = tk.Scale(op_f, from_=0, to=1, resolution=0.05, orient="horizontal",
                      bg=C["bg"], fg=C["text"], troughcolor=C["bg3"],
                      highlightthickness=0, bd=0, showvalue=True,
                      command=lambda v: self._send("opacity", v))
        sl.pack(side="left", fill="x", expand=True)
        self._opacity_slider = sl

        tk.Frame(sf, bg=C["border"], height=1).pack(fill="x", pady=1)

        # 8 · Actions
        ac = Section(sf, "ACTIONS", "⚡", expanded=True); ac.pack(fill="x", pady=(0,1))

        ac.full(lambda p: btn(p, "💾  Save Changes to File", self._save,
                               fg=C["accent"], bg=C["green"], pady=10, bold=True, size=10))

        act_row = tk.Frame(ac.body, bg=C["bg"]); act_row.pack(fill="x", padx=12, pady=4)
        btn(act_row, "📋 Copy Style",  self._copy_style,  bg=C["bg3"], padx=8, pady=5
            ).pack(side="left", padx=(0,4))
        btn(act_row, "📌 Paste Style", self._paste_style, bg=C["bg3"], padx=8, pady=5
            ).pack(side="left", padx=(0,4))
        btn(act_row, "↩ Undo",         self._undo_last,   bg=C["bg3"], padx=8, pady=5
            ).pack(side="left")

        ac.full(lambda p: btn(p, "🔄  Reload Browser",
                               lambda: self._send("__reload__", ""),
                               fg=C["muted"], bg=C["bg2"], pady=6), pady=(2,6))

        tk.Frame(sf, bg=C["border"], height=1).pack(fill="x", pady=1)

        # 9 · AI Chat
        ai_sec = Section(sf, "AI CHAT", "🤖", expanded=True); ai_sec.pack(fill="x", pady=(0,1))

        # Chat log
        chat_frame = tk.Frame(ai_sec.body, bg=C["bg"]); chat_frame.pack(fill="x", padx=8, pady=(4,0))
        self._chat_log = tk.Text(chat_frame, height=7, bg=C["bg2"], fg=C["text"],
                                  font=("Segoe UI", 9), wrap="word", relief="flat",
                                  state="disabled", bd=0,
                                  highlightthickness=1, highlightbackground=C["border"])
        self._chat_log.pack(fill="x")
        self._chat_log.tag_config("user", foreground=C["accent2"], font=("Segoe UI",9,"bold"))
        self._chat_log.tag_config("ai",   foreground=C["text"])
        self._chat_log.tag_config("err",  foreground=C["red"])
        self._chat_log.tag_config("info", foreground=C["muted"], font=("Segoe UI",8))

        # Input row
        ai_input_f = tk.Frame(ai_sec.body, bg=C["bg"]); ai_input_f.pack(fill="x", padx=8, pady=4)
        self.ai_var = tk.StringVar()
        ai_entry = tk.Entry(ai_input_f, textvariable=self.ai_var,
                            bg=C["bg2"], fg=C["text"], insertbackground=C["text"],
                            relief="flat", font=("Segoe UI",9), bd=0,
                            highlightthickness=1, highlightcolor=C["accent2"],
                            highlightbackground=C["border"])
        ai_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0,4))
        ai_entry.bind("<Return>", lambda e: self._ai_apply())
        btn(ai_input_f, "⚡ إرسال", self._ai_apply,
            fg="white", bg=C["accent2"], padx=8, pady=5, bold=True
            ).pack(side="left")

        # URL label
        url_lbl = tk.Label(sf, text=f"🌐  http://127.0.0.1:{_port}/",
                            fg=C["muted"], bg=C["bg"],
                            font=("Consolas",8), cursor="hand2", pady=4)
        url_lbl.pack()
        url_lbl.bind("<Button-1>",
                     lambda e: webbrowser.open(f"http://127.0.0.1:{_port}/"))
        btn(sf, "📋", lambda: self._copy_to_clipboard(f"http://127.0.0.1:{_port}/"),
            bg=C["bg"], fg=C["muted"], padx=4, pady=2, size=8).pack(pady=(0,16))

    # ══════════════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════════════
    def _toggle_btn(self, parent, label, prop, val_on, val_off):
        state = [False]
        b = tk.Button(parent, text=label, bg=C["bg3"], fg=C["muted"],
                       activebackground=C["bg4"], bd=0, padx=9, pady=4,
                       font=("Segoe UI",9,"bold"), cursor="hand2", relief="flat")
        def _tog():
            state[0] = not state[0]
            b.config(bg=C["accent2"] if state[0] else C["bg3"],
                     fg="white"       if state[0] else C["muted"])
            self._send(prop, val_on if state[0] else val_off)
        b.config(command=_tog); b.pack(side="left", padx=2)
        return b, state

    def _make_tooltip(self, widget, text):
        tip = None
        def show(e):
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{e.x_root+12}+{e.y_root+12}")
            tk.Label(tip, text=text, fg="white", bg="#333350",
                     font=("Segoe UI",8), padx=6, pady=3,
                     relief="flat").pack()
        def hide(e):
            nonlocal tip
            if tip: tip.destroy(); tip=None
        widget.bind("<Enter>", show); widget.bind("<Leave>", hide)

    def _rebuild_recents(self):
        for w in self._recent_frame.winfo_children():
            w.destroy()
        if not _recent_colors:
            tk.Label(self._recent_frame, text="recent colors appear here",
                     fg=C["muted"], bg=C["bg"], font=("Segoe UI",7)).pack(anchor="w")
            return
        tk.Label(self._recent_frame, text="Recent:", fg=C["muted"], bg=C["bg"],
                 font=("Segoe UI",7)).pack(side="left", padx=(0,4))
        for col in _recent_colors:
            b = tk.Label(self._recent_frame, bg=col, width=2, cursor="hand2",
                          relief="flat", bd=1)
            b.pack(side="left", padx=2, ipady=6)
            b.bind("<Button-1>", lambda e, c=col: (
                self.col_pick.set(c), self._send("color", c)))

    def _trace(self, var, prop):
        var.trace_add("write", lambda *_: self._on_var(prop, var))

    def _on_var(self, prop, var):
        if self._suppress: return
        self._send(prop, var.get())

    def _send(self, prop, val):
        with _lock:
            _pending_cmds.append({"p": prop, "v": val})

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._flash_status(f"📋 copied: {text[:40]}")

    def _set_width(self, w):
        self._panel_w = w
        sw = self.winfo_screenwidth()
        h  = self.winfo_height()
        y  = self.winfo_y()
        self.geometry(f"{w}x{h}+{sw-w-12}+{y}")

    def _on_configure(self, e):
        pass

    def _flash_status(self, msg, color=None, ms=2000):
        self.status.config(text=msg, fg=color or C["accent"])
        self.after(ms, lambda: self.status.config(
            text="← click any element in browser", fg=C["muted"]))

    # ══════════════════════════════════════════════════
    #  Copy / Paste style
    # ══════════════════════════════════════════════════
    def _copy_style(self):
        with _lock:
            _pending_cmds.append({"p": "__get_style__", "v": ""})
        self.after(400, self._finish_copy)

    def _finish_copy(self):
        global _style_reply
        with _lock:
            reply = dict(_style_reply)
            _style_reply.clear()
        if reply.get("style"):
            self._clipboard = reply["style"]
            self._flash_status("📋 Style copied!")
        else:
            self._flash_status("⚠ Select an element first", C["yellow"])

    def _paste_style(self):
        if not self._clipboard:
            self._flash_status("⚠ Nothing copied yet", C["yellow"]); return
        self._send("__paste_style__", self._clipboard)
        self._flash_status("📌 Style pasted!")

    def _undo_last(self):
        if not self._undo:
            self._flash_status("⚠ Nothing to undo", C["yellow"]); return
        prop, val = self._undo.pop()
        self._send(prop, val)
        self._flash_status(f"↩ Undone: {prop}")

    # ══════════════════════════════════════════════════
    #  Poll for click events
    # ══════════════════════════════════════════════════
    def _poll(self):
        if not self.winfo_exists(): return
        with _lock: info = dict(_last_click)
        if info:
            self._suppress = True
            try:
                tag = info.get("tag","?"); eid = info.get("id","")
                cls = info.get("cls","")
                self.el_badge.config(
                    text=f"◉  <{tag}>" + (f"#{eid}" if eid else "") +
                         (f" .{cls[:20]}" if cls else ""),
                    fg=C["accent"])
                self._flash_status(f"✓  <{tag}>  selected", C["accent"], ms=3000)

                # Text
                self.txt_var.set(info.get("text","")[:200])

                # Show/hide link / img rows
                if info.get("isLink"):
                    self._href_row.pack(fill="x", padx=12, pady=4)
                    self.href_var.set(info.get("href",""))
                else:
                    self._href_row.pack_forget()

                if info.get("isImg"):
                    self._img_section.pack(fill="x", padx=12, pady=4)
                    self._alt_row.pack(fill="x", padx=12, pady=4)
                    self.src_var.set(info.get("src",""))
                    self.alt_var.set(info.get("alt",""))
                    self._is_bg_img   = False
                    self._current_alt = info.get("alt","")
                    self._el_tag      = info.get("tag","div")
                    self._el_id       = info.get("id","")
                    self._el_cls      = info.get("cls","")
                    self._el_index    = info.get("elIndex", 0)
                    self._el_style    = info.get("cleanStyle","")
                elif info.get("isBgImg"):
                    self._img_section.pack(fill="x", padx=12, pady=4)
                    self._alt_row.pack_forget()
                    self.src_var.set(info.get("bgImage",""))
                    self._is_bg_img   = True
                    self._current_alt = ""
                    self._el_tag      = info.get("tag","div")
                    self._el_id       = info.get("id","")
                    self._el_cls      = info.get("cls","")
                    self._el_index    = info.get("elIndex", 0)
                    self._el_style    = info.get("cleanStyle","")
                else:
                    self._img_section.pack(fill="x", padx=12, pady=4)
                    self._alt_row.pack_forget()
                    self.src_var.set("")
                    self._is_bg_img   = False
                    self._current_alt = ""
                    self._el_tag      = info.get("tag","div")
                    self._el_id       = info.get("id","")
                    self._el_cls      = info.get("cls","")
                    self._el_index    = info.get("elIndex", 0)
                    self._el_style    = info.get("cleanStyle","")
                self.fsz_var.set(str(int(float(info.get("fontSize",16)))))
                lh = info.get("lineHeight","")
                self.lh_var.set("" if lh == "normal" else str(lh))
                ls = info.get("letterSpacing","")
                try: self.ls_var.set(str(int(float(str(ls).replace("px","") or "0"))))
                except: self.ls_var.set("0")
                self.ff_var.set(info.get("fontFamily",""))

                # Toggle states
                fw = info.get("fontWeight","normal")
                is_bold = fw in ("bold","700","800","900")
                self._bold_b.config(bg=C["accent2"] if is_bold else C["bg3"],
                                     fg="white" if is_bold else C["muted"])
                self._bold_s[0] = is_bold

                fi = info.get("fontStyle","normal")
                self._italic_b.config(bg=C["accent2"] if fi=="italic" else C["bg3"],
                                       fg="white" if fi=="italic" else C["muted"])

                # Colors
                self.col_pick.set(info.get("color","#000000"))
                self.bg_pick.set(info.get("background","#000000"))
                self.bd_col.set(info.get("borderColor","#000000"))
                self._rebuild_recents()

                # Spacing
                for var, key in [
                    (self.pt_var,"paddingTop"),(self.pr_var,"paddingRight"),
                    (self.pb_var,"paddingBottom"),(self.pl_var,"paddingLeft"),
                    (self.mt_var,"marginTop"),(self.mr_var,"marginRight"),
                    (self.mb_var,"marginBottom"),(self.ml_var,"marginLeft")]:
                    try: var.set(str(int(float(info.get(key,0)))))
                    except: var.set("0")

                # Border
                self.bw_var.set(str(int(float(info.get("borderWidth",0)))))
                self.br_var.set(str(int(float(info.get("borderRadius",0)))))
                bs = info.get("borderStyle","none")
                if bs in ["none","solid","dashed","dotted","double","groove","ridge"]:
                    self.bs_var.set(bs)
                self.shadow_var.set(info.get("boxShadow",""))
                self.transform_var.set(info.get("transform",""))

                # Size
                self.w_var.set(info.get("width",""))
                self.h_var.set(info.get("height",""))
                try:
                    op = float(info.get("opacity",1))
                    self.op_var.set(str(op))
                    self._opacity_slider.set(op)
                except: pass
                dv = info.get("display","block")
                if dv in ["block","inline","inline-block","flex","grid","none","contents"]:
                    self.disp_var.set(dv)

            except Exception as e:
                self._flash_status(f"✗ {e}", C["red"])
            finally:
                self._suppress = False
            with _lock: _last_click.clear()

        self.after(150, self._poll)

    # ══════════════════════════════════════════════════
    #  Actions
    # ══════════════════════════════════════════════════
    def _upload_img(self):
        global _html_path
        # Read state frozen at last click — before filedialog opens
        old_src   = self.src_var.get().strip()
        is_bg_img = getattr(self, "_is_bg_img", False)
        alt_key   = getattr(self, "_current_alt", "").strip()
        el_tag    = getattr(self, "_el_tag",   "div")
        el_id     = getattr(self, "_el_id",    "")
        el_cls    = getattr(self, "_el_cls",   "")
        el_index  = getattr(self, "_el_index", 0)
        el_style  = getattr(self, "_el_style", "")   # clean style from HTML (no outline)

        live_path = _get_current_file_fn() if _get_current_file_fn else _html_path
        if live_path:
            live_path = os.path.abspath(live_path)  # always absolute path
        print(f"[VE UPLOAD] src={repr(old_src)} bg={is_bg_img} alt={repr(alt_key)} "
              f"tag={el_tag} cls={repr(el_cls[:40])} idx={el_index} style={repr(el_style[:40])} "
              f"path={live_path}")

        if not live_path or not live_path.lower().endswith(".html"):
            self._flash_status("⚠ افتح ملف HTML أولاً", C["yellow"]); return
        project_folder = os.path.dirname(live_path)

        p = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.svg")])
        if not p: return

        name = os.path.basename(p)
        dest = os.path.join(project_folder, name)
        try:
            if os.path.abspath(p) != os.path.abspath(dest):
                shutil.copy2(p, dest)
        except Exception as e:
            self._flash_status(f"✗ نسخ الصورة فشل: {e}", C["red"]); return

        try:
            with open(live_path, "r", encoding="utf-8") as f:
                html = f.read()
        except Exception as e:
            self._flash_status(f"✗ فشل قراءة الملف: {e}", C["red"]); return

        # ── Remove old broken __ve_bg__ style tags that used background:none ──
        html = re.sub(
            r'<style id="__ve_bg_[^"]*">(?:(?!</style>).)*background\s*:\s*none[^<]*</style>\n?',
            '', html, flags=re.DOTALL)
        # Also remove the empty <style></style> artifact
        html = html.replace('<style></style>', '')

        # ── Pre-clean: fix any corrupted div tags before processing ──
        def _fix_corrupted_divs(src):
            def nuke_tag(m):
                tag = m.group(0)
                sm = re.search(r'(style=")([^"]*?)(")', tag, re.DOTALL)
                if not sm:
                    sm = re.search(r"(style=')([^']*?)(')", tag, re.DOTALL)
                if not sm:
                    return tag
                style_val = sm.group(2)
                # Keep only valid CSS prop:value pairs
                clean_props = [p.strip() for p in style_val.split(';')
                               if p.strip() and re.match(r'^[\w-]+\s*:', p.strip())]
                clean_style = ';'.join(clean_props)
                # Collect all image URLs from style and any dangling filenames after style
                img_in_style = re.findall(r"url\s*\(\s*['\"]?([^)'\"]+\.(?:png|jpg|jpeg|gif|webp))['\"]?\s*\)", clean_style, re.IGNORECASE)
                dangling_after = re.findall(r'["\']([^"\']+\.(?:png|jpg|jpeg|gif|webp))["\']', tag[sm.end():], re.IGNORECASE)
                all_imgs = [u for u in img_in_style + dangling_after
                            if not u.startswith('data:') and 'svg' not in u.lower()]
                if all_imgs or dangling_after:
                    final_img = all_imgs[-1] if all_imgs else None
                    if final_img:
                        ns = (f"background-image:url('{final_img}')!important;"
                              f"background-size:cover!important;"
                              f"background-position:center!important;"
                              f"background-repeat:no-repeat!important;")
                        # Rebuild tag cleanly — strip everything after style to >
                        pre = tag[:sm.start()]
                        # Get remaining attributes before style
                        return pre + f'style="{ns}">'
                if clean_style != style_val:
                    return tag[:sm.start(2)] + clean_style + tag[sm.end(2):]
                return tag
            return re.sub(r'<div\b[^>]*>', nuke_tag, src)

        html = _fix_corrupted_divs(html)

        new_html = html
        new_src  = name

        # Normalize old_src: strip server origin and URL-decode
        import urllib.parse
        server_origin = "http://127.0.0.1:" + str(_port)
        if old_src.startswith(server_origin):
            old_src = old_src[len(server_origin):]
        if old_src.startswith("/"):
            old_src = old_src[1:]
        try: old_src = urllib.parse.unquote(old_src)
        except: pass

        # ── Case A: <img src="existing"> ──────────────────────────────────
        if old_src and not is_bg_img:
            new_html = re.sub(
                r'(src=["\'])' + re.escape(old_src) + r'(["\'])',
                lambda m: m.group(1) + new_src + m.group(2), html)

        # ── Case B: background-image:url(existing) ────────────────────────
        elif old_src and is_bg_img:
            esc = re.escape(old_src)
            # Match url() with plain quotes, HTML-entity quotes (&quot;), or no quotes
            q = r'(?:["\']|&quot;)?'
            # Replace the entire style attr with a clean one
            def replace_bg_style(m):
                # m is the full tag; find and replace its style
                tag = m.group(0)
                sm2 = re.search(r'(style=["\'])([^"\']*?)(["\'])', tag, re.DOTALL)
                if not sm2:
                    return tag
                new_style = (f"background-image:url('{new_src}')!important;"
                             f"background-size:cover!important;"
                             f"background-position:center!important;"
                             f"background-repeat:no-repeat!important;")
                return tag[:sm2.start(2)] + new_style + tag[sm2.end(2):]

            # Find the tag containing old_src in its style
            tag_pat = r'<[^>]+style=["\'][^"\']*' + q + re.escape(old_src) + q + r'[^"\']*["\'][^>]*>'
            new_html = re.sub(tag_pat, replace_bg_style, html, flags=re.DOTALL)
            if new_html == html:
                # Fallback: just replace the url() reference
                new_html = re.sub(
                    r'(url\(' + q + r')' + esc + r'(' + q + r'\))',
                    lambda m2: m2.group(1) + new_src + m2.group(2), html)

        # ── Case C: <img src="" alt="text"> ───────────────────────────────
        elif alt_key:
            ea = re.escape(alt_key)
            new_html = re.sub(
                r'(<img\b[^>]*?alt=["\'])' + ea + r'(["\'][^>]*?)src=["\'][^"\']*["\']',
                lambda m: m.group(1) + alt_key + m.group(2) + 'src="' + new_src + '"',
                html, flags=re.DOTALL)
            if new_html == html:
                new_html = re.sub(
                    r'(<img\b[^>]*?)src=["\'][^"\']*["\']([^>]*?alt=["\'])' + ea + r'(["\'])',
                    lambda m: m.group(1) + 'src="' + new_src + '"' + m.group(2) + alt_key + m.group(3),
                    html, flags=re.DOTALL)

        # ── Case D: div/span/etc — find by tag+class+index ────────────────
        else:
            best = None
            if el_id:
                pat  = r'(<' + re.escape(el_tag) + r'\b[^>]*?id=["\']' + re.escape(el_id) + r'["\'][^>]*?)(\/?>)'
                best = re.search(pat, html, re.DOTALL)
            elif el_cls:
                first_cls = el_cls.split()[0]
                pat = (r'(<' + re.escape(el_tag) + r'\b[^>]*?'
                       r'class=["\'][^"\']*\b' + re.escape(first_cls) + r'\b[^"\']*["\']'
                       r'[^>]*?)(\/?>)')
                candidates = list(re.finditer(pat, html, re.DOTALL))
                print(f"[VE UPLOAD] Case D: found {len(candidates)} candidates for .{first_cls}, picking idx={el_index}")
                if candidates:
                    best = candidates[el_index] if el_index < len(candidates) else candidates[0]

            if best:
                bg = ("background-image:url('" + new_src + "')!important;"
                      "background-size:cover!important;"
                      "background-position:center!important;"
                      "background-repeat:no-repeat!important;")
                tag_str = best.group(0)
                def clean_style(tag):
                    tag = re.sub(r';?\s*color\s*:\s*rgb\s*\([^)]*\)', '', tag)
                    tag = re.sub(r';?\s*background(?:-color)?\s*:\s*rgb\s*\([^)]*\)', '', tag)
                    tag = re.sub(r';?\s*border-color\s*:\s*rgb\s*\([^)]*\)', '', tag)
                    tag = re.sub(r';?\s*outline\s*:[^;"\']*', '', tag)
                    tag = re.sub(r';?\s*border-style\s*:\s*\w+', '', tag)
                    tag = re.sub(r';?\s*display\s*:\s*(block|inline-block|flex|grid|inline)', '', tag)
                    # Remove any existing background:url() so we replace it cleanly
                    tag = re.sub(r';?\s*background\s*:[^;"\']*url\([^)]*\)[^;"\']*', '', tag)
                    tag = re.sub(r';?\s*background-image\s*:[^;"\']*', '', tag)
                    tag = re.sub(r';?\s*background-size\s*:[^;"\']*', '', tag)
                    tag = re.sub(r';?\s*background-position\s*:[^;"\']*', '', tag)
                    tag = re.sub(r';?\s*background-repeat\s*:[^;"\']*', '', tag)
                    # Remove dangling filename fragments like 'foo.png')!important;
                    tag = re.sub(r"['\"][^'\"]*\.(png|jpg|jpeg|gif|webp|svg)['\"][^;]*;?", '', tag, flags=re.IGNORECASE)
                    # Remove broken remnants
                    tag = re.sub(r'[\w-]+\s*-\s*;', '', tag)
                    tag = re.sub(r'style=["\'];', lambda m2: m2.group(0)[:-1], tag)
                    return tag

                tag_str = clean_style(tag_str)
                # Replace entire style attr with clean bg, or add new one
                if 'style=' in tag_str:
                    tag_new = re.sub(
                        r'(style=["\'])[^"\']*(["\'])',
                        lambda sm: sm.group(1) + bg + sm.group(2),
                        tag_str, count=1)
                else:
                    tag_new = best.group(1) + ' style="' + bg + '"' + best.group(2)
                new_html = html[:best.start()] + tag_new + html[best.end():]
                print(f"[VE UPLOAD] Case D: patched → {tag_new[:80]}")

        print(f"[VE UPLOAD] HTML changed: {new_html != html}")
        if new_html == html:
            self._flash_status("⚠ لم يتم تحديد عنصر — اضغط على الصورة أو div مباشرة", C["yellow"])
            return

        # ── Inject CSS override for every class that has a background-image in inline style ──
        # Collect all classes that now have background-image in inline style
        classes_with_bg = set(re.findall(
            r'class=["\'][^"\']*?([\w-]+)[^"\']*?["\'][^>]*?style=["\'][^"\']*?background-image',
            new_html))
        # Also get from style=... class=... order
        classes_with_bg |= set(re.findall(
            r'style=["\'][^"\']*?background-image[^"\']*?["\'][^>]*?class=["\'][^"\']*?([\w-]+)',
            new_html))
        # Add current el_cls
        if el_cls:
            classes_with_bg.add(el_cls.split()[0])

        print(f"[VE UPLOAD] CSS override for classes: {classes_with_bg}")

        for cls in classes_with_bg:
            override_id = f"__ve_bg_{cls}__"
            # Inline style with !important always beats any stylesheet rule.
            # We just need to ensure the stylesheet's `background` shorthand
            # doesn't accidentally win via cascade. Adding a higher-specificity
            # rule that only sets background-color (not background-image) is enough.
            css_rule = (f'<style id="{override_id}">'
                        f'.{cls}[style]{{background-color:transparent!important;}}'
                        f'</style>')
            new_html = re.sub(
                r'<style id="' + re.escape(override_id) + r'">[^<]*</style>\n?', '', new_html)
            head_end = new_html.lower().find('</head>')
            if head_end >= 0:
                new_html = new_html[:head_end] + css_rule + '\n' + new_html[head_end:]
            else:
                new_html = css_rule + '\n' + new_html

        try:
            with open(live_path, "w", encoding="utf-8") as f:
                f.write(new_html)
            # Verify write succeeded
            with open(live_path, "r", encoding="utf-8") as f:
                verify = f.read()
            if verify == new_html:
                # ── Save undo snapshot (keep last 20) ──
                _undo_stack.append((live_path, html))
                if len(_undo_stack) > 20:
                    _undo_stack.pop(0)
                print(f"[VE UPLOAD] ✅ File written OK: {live_path}")
            else:
                print(f"[VE UPLOAD] ❌ File verify FAILED — content mismatch!")
        except Exception as e:
            self._flash_status(f"✗ فشل حفظ الملف: {e}", C["red"]); return

        _html_path = live_path
        # Update code editor — use after(10) so tkinter <<Modified>> event settles before we clear flag
        if _code_editor:
            try:
                _code_editor.delete("1.0", tk.END)
                _code_editor.insert(tk.END, new_html)
                # Delay flag clear so tkinter's internal Modified event fires first
                _code_editor.after(10, lambda: _code_editor.edit_modified(False))
                print(f"[VE UPLOAD] ✅ Editor updated (modified will clear in 10ms)")
            except Exception as ex:
                print(f"[VE UPLOAD] ⚠ Editor update failed: {ex}")

        self.src_var.set(new_src)
        self._flash_status(f"✓ تم الاستبدال والحفظ: {name}", C["accent"])
        self.after(200, lambda: self._send("__reload__", ""))


    def _patch_css_for_class(self, project_folder, cls_name):
        """Remove any broken [style] override rules from CSS files that were
        added by previous versions of this tool and cause images to not show."""
        import glob
        css_files = glob.glob(os.path.join(project_folder, "*.css"))
        for css_path in css_files:
            try:
                with open(css_path, "r", encoding="utf-8") as f:
                    css = f.read()
                # Remove any .cls[style]{...} rule we may have added previously
                cleaned = re.sub(
                    r'\s*\.' + re.escape(cls_name) + r'\[style\][^{]*\{[^}]*\}',
                    '', css)
                if cleaned != css:
                    with open(css_path, "w", encoding="utf-8") as f:
                        f.write(cleaned)
                    print(f"[VE CSS] Removed broken override for .{cls_name} in {os.path.basename(css_path)}")
            except Exception as e:
                print(f"[VE CSS] Error patching {css_path}: {e}")

    def _save_after_img_replace(self):
        """Called after a short delay to save the HTML after image src was updated in browser."""
        with _lock:
            _pending_cmds.append({"p": "__save__", "v": ""})
        self.after(800, lambda: self._flash_status("✓ image replaced & saved!", C["accent"]))

    def _undo_last(self):
        global _undo_stack
        if not _undo_stack:
            self._flash_status("⚠ لا يوجد شيء للتراجع عنه", C["yellow"]); return
        path, old_html = _undo_stack.pop()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(old_html)
            if _code_editor:
                _code_editor.delete("1.0", tk.END)
                _code_editor.insert(tk.END, old_html)
                _code_editor.after(10, lambda: _code_editor.edit_modified(False))
            self._flash_status(f"↩ تم التراجع ({len(_undo_stack)} متبقية)", C["accent"])
            self.after(200, lambda: self._send("__reload__", ""))
        except Exception as e:
            self._flash_status(f"✗ فشل التراجع: {e}", C["red"])

    def _save(self):
        with _lock: _pending_cmds.append({"p":"__save__","v":""})
        self._flash_status("⏳ saving…", C["muted"], ms=1200)
        self.after(1200, lambda: self._flash_status("✓ saved!", C["accent"]))

    def _chat_append(self, text, tag="ai"):
        """Append text to chat log (thread-safe via after)."""
        def _do():
            self._chat_log.config(state="normal")
            self._chat_log.insert("end", text + "\n", tag)
            self._chat_log.see("end")
            self._chat_log.config(state="disabled")
        self.after(0, _do)

    def _ai_apply(self):
        req = self.ai_var.get().strip()
        if not req: return
        self.ai_var.set("")
        self._chat_append(f"👤 {req}", "user")
        self._chat_append("⏳ AI يعمل…", "info")
        self._flash_status("⏳ AI working…", C["muted"], ms=30000)
        threading.Thread(target=self._ai_worker, args=(req,), daemon=True).start()

    def _ai_worker(self, req):
        try:
            html = open(_html_path, encoding="utf-8").read()
            from core.ai_engine import _call_ai
            prompt = (f"You are a senior frontend engineer.\nUser request: {req}\n"
                      f"Current HTML:\n{html}\nReturn ONLY the complete updated HTML. No markdown.")
            new_html = _call_ai(prompt, _model_fn(), _provider_fn())
            new_html = re.sub(r'^```[a-z]*\n?', '', new_html.strip())
            new_html = re.sub(r'\n?```$', '', new_html.strip())

            # Save undo snapshot before AI change
            _undo_stack.append((_html_path, html))
            if len(_undo_stack) > 20: _undo_stack.pop(0)

            with open(_html_path, "w", encoding="utf-8") as f: f.write(new_html)
            if _code_editor:
                def _u():
                    _code_editor.delete("1.0", tk.END)
                    _code_editor.insert(tk.END, new_html)
                    _code_editor.after(10, lambda: _code_editor.edit_modified(False))
                _code_editor.after(0, _u)

            # Show summary in chat
            changed = sum(1 for a, b in zip(html.splitlines(), new_html.splitlines()) if a != b)
            self._chat_append(f"🤖 تم التطبيق — {changed} سطر تغيّر", "ai")
            self.after(0, lambda: self._flash_status("✓ AI applied", C["accent"], ms=4000))
            self.after(300, lambda: self._send("__reload__", ""))
        except Exception as e:
            self._chat_append(f"✗ خطأ: {e}", "err")
            self.after(0, lambda: self._flash_status(f"✗ {e}", C["red"], ms=5000))


# ══════════════════════════════════════════════════════
#  Public entry point
# ══════════════════════════════════════════════════════
def open_visual_editor(parent, get_current_file, code_editor,
                       ai_modify_fn=None, provider_fn=None, model_fn=None):
    global _html_path, _code_editor, _provider_fn, _model_fn, _get_current_file_fn

    path = get_current_file()
    if not path:
        messagebox.showinfo("Visual Editor", "Load a project first."); return
    if not path.lower().endswith(".html"):
        messagebox.showinfo("Visual Editor", "Select an HTML file first."); return

    _html_path          = os.path.abspath(path)
    # Wrap to always return absolute path
    _get_current_file_fn = lambda: (os.path.abspath(get_current_file()) if get_current_file() else None)
    _code_editor        = code_editor
    _provider_fn        = provider_fn or (lambda: "OpenAI")
    _model_fn           = model_fn    or (lambda: "gpt-4o-mini")

    _start_server()
    webbrowser.open(f"http://127.0.0.1:{_port}/")
    PropsWindow(parent)