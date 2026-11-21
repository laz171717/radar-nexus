"""Radar NEXUS - recolector de tendencias.
Junta noticias y búsquedas de fuentes gratis, agrupa la misma noticia,
calcula una puntuación de tendencia y escribe docs/data.json.
Solo usa la biblioteca estándar de Python.
"""
import json, re, math, time, html, os, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(AQUI, "docs")
CACHE_TRAD = os.path.join(AQUI, "cache_traducciones.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
AHORA = datetime.now(timezone.utc)
VENTANA_H = 72

def gn(q, hl="en-US", gl="US", ceid="US:en"):
    return f"https://news.google.com/rss{q}?hl={hl}&gl={gl}&ceid={ceid}"

GN_TOP = "/headlines/section/topic/"
# (nombre, url, región, categoría por defecto, tipo)
FUENTES = [
    ("Google Noticias EE. UU.", gn(""), "EE. UU.", None, "agregador"),
    ("Google Noticias Mundo", gn(GN_TOP + "WORLD"), "Mundo", "Política", "agregador"),
    ("Google Noticias Economía", gn(GN_TOP + "BUSINESS"), "EE. UU.", "Economía", "agregador"),
    ("Google Noticias Tecnología", gn(GN_TOP + "TECHNOLOGY"), "Mundo", "Tecnología", "agregador"),
    ("Google Noticias Ciencia", gn(GN_TOP + "SCIENCE"), "Mundo", "Ciencia", "agregador"),
    ("Google Noticias Salud", gn(GN_TOP + "HEALTH"), "Mundo", "Salud", "agregador"),
    ("Google Noticias Espectáculos", gn(GN_TOP + "ENTERTAINMENT"), "EE. UU.", "Famosos", "agregador"),
    ("Google Noticias Deportes", gn(GN_TOP + "SPORTS"), "EE. UU.", "Deportes", "agregador"),
    ("Google Noticias Reino Unido", gn("", "en-GB", "GB", "GB:en"), "Europa", None, "agregador"),
    ("Google Noticias Latam", gn("", "es-419", "US", "US:es-419"), "Latinoamérica", None, "agregador"),
    ("Google Noticias España", gn("", "es", "ES", "ES:es"), "Europa", None, "agregador"),
    ("Google Noticias Mundo (es)", gn(GN_TOP + "WORLD", "es-419", "US", "US:es-419"), "Mundo", "Política", "agregador"),
    ("BBC", "https://feeds.bbci.co.uk/news/world/rss.xml", "Mundo", None, "medio"),
    ("BBC EE. UU.", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "EE. UU.", None, "medio"),
    ("BBC Mundo", "https://feeds.bbci.co.uk/mundo/rss.xml", "Latinoamérica", None, "medio"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "Mundo", None, "medio"),
    ("The Guardian", "https://www.theguardian.com/world/rss", "Mundo", None, "medio"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml", "EE. UU.", None, "medio"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "EE. UU.", "Economía", "medio"),
    ("CBS News", "https://www.cbsnews.com/latest/rss/main", "EE. UU.", None, "medio"),
    ("DW Español", "https://rss.dw.com/xml/rss-sp-all", "Mundo", None, "medio"),
    ("France 24 Español", "https://www.france24.com/es/rss", "Mundo", None, "medio"),
    ("CNN en Español", "https://cnnespanol.cnn.com/feed/", "Latinoamérica", None, "medio"),
    ("El País", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada", "Europa", None, "medio"),
    ("Infobae", "https://www.infobae.com/arc/outboundfeeds/rss/", "Latinoamérica", None, "medio"),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "EE. UU.", None, "medio"),
    ("NYT Mundo", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "Mundo", None, "medio"),
    ("NYT Economía", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "EE. UU.", "Economía", "medio"),
    ("NYT Tecnología", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "EE. UU.", "Tecnología", "medio"),
    ("Wall Street Journal", "https://feeds.content.dowjones.io/public/rss/RSSWorldNews", "Mundo", None, "medio"),
    ("WSJ Mercados", "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain", "EE. UU.", "Economía", "medio"),
    ("Washington Post", "https://feeds.washingtonpost.com/rss/world", "Mundo", None, "medio"),
    ("Fox News", "https://moxie.foxnews.com/google-publisher/latest.xml", "EE. UU.", None, "medio"),
    ("ABC News", "https://abcnews.go.com/abcnews/topstories", "EE. UU.", None, "medio"),
    ("Sky News", "https://feeds.skynews.com/feeds/rss/world.xml", "Europa", None, "medio"),
    ("Euronews", "https://www.euronews.com/rss", "Europa", None, "medio"),
    ("The Hill", "https://thehill.com/news/feed/", "EE. UU.", "Política", "medio"),
    ("Politico", "https://rss.politico.com/politics-news.xml", "EE. UU.", "Política", "medio"),
    ("Axios", "https://api.axios.com/feed/", "EE. UU.", None, "medio"),
    ("Yahoo Noticias", "https://news.yahoo.com/rss/", "EE. UU.", None, "medio"),
    ("The Verge", "https://www.theverge.com/rss/index.xml", "Mundo", "Tecnología", "medio"),
    ("TechCrunch", "https://techcrunch.com/feed/", "Mundo", "Tecnología", "medio"),
    ("Hacker News", "https://hnrss.org/frontpage?points=250", "Mundo", "Tecnología", "comunidad"),
    ("Reddit r/worldnews", "https://www.reddit.com/r/worldnews/top.rss?t=day", "Mundo", None, "comunidad"),
    ("Reddit r/news", "https://www.reddit.com/r/news/top.rss?t=day", "EE. UU.", None, "comunidad"),
]

PAISES_TRENDS = [("US", "EE. UU."), ("GB", "Reino Unido"), ("CA", "Canadá"), ("AU", "Australia"),
                 ("IN", "India"), ("ES", "España"), ("MX", "México"), ("AR", "Argentina"),
                 ("CO", "Colombia"), ("CL", "Chile")]
REGION_PAIS = {"US": "EE. UU.", "CA": "EE. UU.", "GB": "Europa", "ES": "Europa", "DE": "Europa", "FR": "Europa",
               "MX": "Latinoamérica", "AR": "Latinoamérica", "CO": "Latinoamérica", "CL": "Latinoamérica",
               "PE": "Latinoamérica", "BR": "Latinoamérica", "IN": "Mundo", "AU": "Mundo"}

STOP = set("""a an the of to in on for and or but at by with from as is are was were be been it its this that these those
after before over into about amid says said say new news live update updates video photos report reports how why what who
when where will would could can may not no his her their they he she we you i us more than up out off just first last one two
de la el los las y o en un una unos unas del al por para con sin que se su sus es son fue lo como más tras ante sobre entre
hasta desde este esta estos estas ese esa le les ya muy pero según dice dijo nuevo nueva hoy vivo directo así qué cómo
quién cuándo dónde ha han hay ser era""".split())

ROJO = ["cartel", "cártel", "narco", "drug lord", "beheaded", "decapit", "massacre", "masacre", "shooting", "tiroteo",
        "balacera", "gunman", "pistolero", "terror attack", "atentado", "suicide", "suicidio", "child abuse", "abuso infantil",
        "rape", "violación", "isis", "hamas", "hezbollah", "hezbolá", "murdered", "asesinad", "found dead", "hallados muertos",
        "sicario", "porn", "overdose", "sobredosis"]
AMARILLO = ["war", "guerra", "missile", "misil", "strike", "ataque", "bomb", "bomba", "military", "militar", "army",
            "ejército", "killed", "muertos", "dead", "arrest", "detenido", "arrested", "police", "policía", "weapon", "arma",
            "election", "elecciones", "vaccine", "vacuna", "protest", "protesta", "crash", "accidente", "explosion",
            "explosión", "nuclear", "invasion", "invasión", "hostage", "rehén", "prison", "cárcel", "court", "tribunal",
            "trump", "abortion", "aborto", "migrant", "migrante", "immigration", "inmigración"]

CATS = {
    "Economía": ["stock", "bolsa", "market", "mercado", "economy", "economía", "inflation", "inflación", "fed", "tariff",
                 "arancel", "price", "precio", "oil", "petróleo", "dollar", "dólar", "bank", "banco", "jobs", "empleo",
                 "recession", "recesión", "tax", "impuesto", "crypto", "bitcoin", "earnings", "ventas", "sales", "deal",
                 "acuerdo comercial", "gdp", "pib", "billion", "millones", "layoffs", "despidos"],
    "Tecnología": ["ai ", "inteligencia artificial", "openai", "nvidia", "apple", "google", "microsoft", "meta", "tesla",
                   "chip", "iphone", "android", "app", "software", "robot", "spacex", "cyber", "hack", "data center",
                   "tiktok", "x.com", "musk", "gta", "playstation", "xbox", "nintendo", "videojuego"],
    "Ciencia": ["nasa", "space", "espacio", "scientists", "científicos", "study", "estudio", "planet", "planeta", "climate",
                "clima", "earthquake", "sismo", "terremoto", "volcano", "volcán", "asteroid", "asteroide", "ufo", "ovni",
                "hurricane", "huracán", "storm", "tormenta", "flood", "inundación", "fossil", "fósil"],
    "Salud": ["health", "salud", "virus", "outbreak", "brote", "cancer", "cáncer", "hospital", "disease", "enfermedad",
              "vaccine", "vacuna", "fármaco", "covid", "flu", "gripe", "medic"],
    "Deportes": ["nfl", "nba", "mlb", "fifa", "uefa", "world cup", "mundial", "champions", "liga", "goal", "gol", "coach",
                 "entrenador", "messi", "ronaldo", "match", "partido", "playoff", "super bowl", "olymp", "olímp", "f1",
                 "tennis", "tenis", "boxing", "boxeo", "ufc", " vs ", " vs. ", "premier league", "serie a", "bundesliga", "ligue 1", "la liga", "laliga", "torneo", "derbi", "derby", "lineups", "alineaciones", "minuto a minuto", "en vivo:", "sudamericana", "libertadores", "eredivisie", "psg", "football", "fútbol", "futbol", "soccer", "touchdown", "quarterback", "huskers", "ncaa", "mls", "usl"],
    "Famosos": ["singer", "cantante", "actor", "actress", "actriz", "movie", "película", "film", "netflix", "album", "álbum",
                "concert", "concierto", "taylor swift", "grammy", "oscar", "celebrity", "famoso", "series", "rapper",
                "kardashian", "dies at", "muere a los", "tour", "gira"],
    "Política": ["president", "presidente", "election", "elecciones", "senate", "senado", "congress", "congreso",
                 "minister", "ministro", "government", "gobierno", "trump", "putin", "xi ", "zelensky", "war", "guerra",
                 "nato", "otan", "un ", "onu", "sanction", "sanción", "summit", "cumbre", "vote", "voto", "law", "ley"],
}

def bajar(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def limpiar(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or ""))
    return re.sub(r"\s+", " ", t).strip()

def fecha(txt):
    if not txt:
        return None
    try:
        d = parsedate_to_datetime(txt)
    except Exception:
        try:
            d = datetime.fromisoformat(txt.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def leer_feed(fuente):
    nombre, url, region, cat, tipo = fuente
    try:
        raiz = ET.fromstring(bajar(url))
    except Exception as e:
        return nombre, [], str(e)[:80]
    items = []
    ns_atom = "{http://www.w3.org/2005/Atom}"
    nodos = raiz.findall(".//item") or raiz.findall(f".//{ns_atom}entry")
    for n in nodos[:60]:
        def g(tag):
            x = n.find(tag)
            if x is None:
                x = n.find(ns_atom + tag)
            return x
        titulo = limpiar((g("title").text if g("title") is not None else ""))
        link_el = g("link")
        link = ""
        if link_el is not None:
            link = link_el.text or link_el.get("href") or ""
        f = None
        for t in ("pubDate", "published", "updated", "{http://purl.org/dc/elements/1.1/}date"):
            el = n.find(t) if t.startswith("{") else g(t)
            if el is not None and el.text:
                f = fecha(el.text)
                if f:
                    break
        medio = nombre
        src = n.find("source")
        if src is not None and src.text:  # Google Noticias trae el medio original
            medio = src.text.strip()
            titulo = re.sub(r"\s+-\s+" + re.escape(medio) + r"$", "", titulo)
        if not titulo or f is None:
            continue
        if (AHORA - f) > timedelta(hours=VENTANA_H):
            continue
        items.append({"titulo": titulo, "link": link.strip(), "fecha": f, "medio": medio,
                      "via": nombre, "region": region, "cat": cat, "tipo": tipo})
    return nombre, items, None

def leer_trends(pais):
    codigo, nombre = pais
    url = f"https://trends.google.com/trending/rss?geo={codigo}"
    try:
        raiz = ET.fromstring(bajar(url))
    except Exception as e:
        return codigo, [], str(e)[:80]
    ht = "{https://trends.google.com/trending/rss}"
    out = []
    for n in raiz.findall(".//item"):
        termino = limpiar(n.findtext("title"))
        trafico = (n.findtext(ht + "approx_traffic") or "0").replace(",", "").replace("+", "").strip()
        mult = 1
        if trafico.upper().endswith("K"):
            mult, trafico = 1000, trafico[:-1]
        elif trafico.upper().endswith("M"):
            mult, trafico = 1000000, trafico[:-1]
        try:
            num = int(float(trafico) * mult)
        except ValueError:
            num = 0
        f = fecha(n.findtext("pubDate")) or AHORA
        noticias = []
        for ni in n.findall(ht + "news_item"):
            noticias.append({"titulo": limpiar(ni.findtext(ht + "news_item_title")),
                             "link": (ni.findtext(ht + "news_item_url") or "").strip(),
                             "medio": limpiar(ni.findtext(ht + "news_item_source"))})
        out.append({"termino": termino, "busquedas": num, "pais": codigo, "pais_nombre": nombre,
                    "fecha": f, "noticias": noticias, "imagen": (n.findtext(ht + "picture") or "").strip()})
    return codigo, out, None

def leer_wikipedia(idioma):
    out = []
    for dias in (1, 2):
        d = AHORA - timedelta(days=dias)
        url = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{idioma}.wikipedia/all-access/"
               f"{d:%Y/%m/%d}")
        try:
            datos = json.loads(bajar(url))
            break
        except Exception:
            datos = None
    if not datos:
        return idioma, []
    malas = ("Main_Page", "Special:", "Wikipedia:", "Portal:", "Página_principal", "Especial:", "File:", "Archivo:",
             "Help:", "Ayuda:", "XXX", "Pornhub", "Xvideos", "Cleopatra", "Search")
    for a in datos["items"][0]["articles"]:
        t = a["article"]
        if any(t.startswith(m) or m in t for m in malas):
            continue
        out.append({"articulo": t.replace("_", " "), "visitas": a["views"], "idioma": idioma,
                    "link": f"https://{idioma}.wikipedia.org/wiki/{urllib.parse.quote(t)}"})
        if len(out) >= 30:
            break
    return idioma, out

PAISES_X = [("worldwide", "", "Mundo"), ("united-states", "united-states/", "EE. UU."),
            ("united-kingdom", "united-kingdom/", "Reino Unido"), ("spain", "spain/", "España"),
            ("mexico", "mexico/", "México"), ("argentina", "argentina/", "Argentina"),
            ("colombia", "colombia/", "Colombia")]

X_COMUNES = set("""china russia rusia ukraine ucrania trump biden israel iran irán mexico méxico españa spain europe europa
america américa canada canadá india japan japón france francia germany alemania brasil brazil costa time full today
world mundo president presidente united states unidos police policía news noticias sunday monday friday saturday
viernes sábado domingo lunes week semana game juego final""".split())

def leer_x(pais):
    """Tendencias de X (Twitter) de la última hora, vía trends24.in."""
    clave, ruta, nombre = pais
    try:
        h = bajar("https://trends24.in/" + ruta).decode("utf-8", "replace")
    except Exception as e:
        return clave, [], str(e)[:80]
    i = h.find("trend-link")
    bloque = h[i:h.find("</ol>", i)] if i >= 0 else ""
    out = []
    for m in re.finditer(r'href="([^"]+)" class=trend-link>(.*?)</a><span class=tweet-count data-count="?(\d*)', bloque):
        out.append({"termino": html.unescape(m.group(2)), "posts": int(m.group(3) or 0),
                    "link": m.group(1).replace("twitter.com", "x.com"), "pais": nombre})
    return clave, out[:30], None if out else "sin datos"

def leer_bluesky():
    try:
        d = json.loads(bajar("https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrends?limit=25"))
    except Exception as e:
        return [], str(e)[:80]
    out = []
    for t in d.get("trends", []):
        out.append({"tema": t.get("displayName", ""), "descripcion": t.get("description", ""),
                    "posts": t.get("postCount", 0), "categoria": t.get("category", ""),
                    "estado": t.get("status", ""), "desde": t.get("startedAt", ""),
                    "link": "https://bsky.app" + t.get("link", "")})
    return out, None

def leer_mastodon():
    out, error = [], None
    for inst in ("mastodon.social", "mstdn.social"):
        try:
            d = json.loads(bajar(f"https://{inst}/api/v1/trends/links?limit=20"))
        except Exception as e:
            error = str(e)[:80]
            continue
        for l in d:
            usos = sum(int(x.get("uses", 0)) for x in (l.get("history") or [])[:2])
            out.append({"titulo": limpiar(l.get("title")), "link": l.get("url", ""),
                        "medio": l.get("provider_name") or inst, "compartido": usos,
                        "fecha": l.get("published_at") or ""})
    vistos, unicos = set(), []
    for l in sorted(out, key=lambda x: -x["compartido"]):
        if l["link"] not in vistos and l["titulo"]:
            vistos.add(l["link"]); unicos.append(l)
    return unicos[:30], (None if unicos else error)

def palabras(t):
    t = t.lower()
    t = re.sub(r"[^\wáéíóúñü ]+", " ", t)
    return {w for w in t.split() if len(w) > 2 and w not in STOP and not w.isdigit()}

def nombres_propios(t):
    return {w.lower() for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]{2,}", t)} - STOP

def agrupar(items):
    grupos = []
    for it in sorted(items, key=lambda x: x["fecha"], reverse=True):
        p = palabras(it["titulo"])
        np_ = nombres_propios(it["titulo"])
        it["_p"], it["_np"] = p, np_
        mejor, mejor_sim = None, 0
        for g in grupos:
            inter = len(p & g["_p"])
            if not inter:
                continue
            jac = inter / max(1, len(p | g["_p"]))
            fuertes = len(np_ & g["_np"])
            sim = jac + 0.12 * fuertes
            if (jac >= 0.25 or (fuertes >= 2 and inter >= 2) or (fuertes >= 3)) and sim > mejor_sim:
                mejor, mejor_sim = g, sim
        if mejor:
            mejor["items"].append(it)
            mejor["_p"] |= p
            mejor["_np"] |= np_
        else:
            grupos.append({"items": [it], "_p": set(p), "_np": set(np_)})
    return grupos

def categoria(texto, por_defecto):
    tl = " " + texto.lower() + " "
    votos = {c: sum(1 for k in ks if k in tl) for c, ks in CATS.items()}
    if votos["Deportes"] >= 2:
        return "Deportes"
    mejor = max(votos, key=votos.get)
    if votos[mejor] > 0:
        return mejor
    return por_defecto or "General"

def semaforo(texto):
    tl = texto.lower()
    r = [k for k in ROJO if k in tl]
    if r:
        return "rojo", r[:3]
    a = [k for k in AMARILLO if re.search(r"\b" + re.escape(k), tl)]
    if a:
        return "amarillo", a[:3]
    return "verde", []

def es_espanol(t):
    tl = " " + t.lower() + " "
    es = sum(tl.count(w) for w in (" el ", " la ", " de ", " los ", " las ", " y ", " en ", " del ", " por ", " que ", " con ", " una "))
    otros = sum(tl.count(w) for w in (" the ", " of ", " and ", " to ", " for ", " with ", " le ", " les ", " et ", " des ", " du ", " och ", " und ", " der ", " die ", " met ", " het ", " van ", " não ", " ao ", " com ", " um ", " uma ", "'s "))
    return es > otros and es >= 1

def es_ingles(t):
    return not es_espanol(t)

def _viejo_es_ingles(t):
    tl = " " + t.lower() + " "
    en = sum(tl.count(w) for w in (" the ", " of ", " and ", " to ", " in ", " for ", " with ", " after ", " is ", "'s "))
    es = sum(tl.count(w) for w in (" el ", " la ", " de ", " los ", " las ", " y ", " en ", " del ", " por ", " que "))
    return en > es

def cargar_cache():
    try:
        with open(CACHE_TRAD, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def traducir(textos, cache):
    pendientes = [t for t in textos if t not in cache]
    def uno(t):
        for intento in range(2):
            for host in ("translate.googleapis.com", "clients5.google.com"):
                url = (f"https://{host}/translate_a/single?client=gtx&sl=auto&tl=es&dt=t&q=" + urllib.parse.quote(t))
                try:
                    d = json.loads(bajar(url, 10))
                    return t, "".join(p[0] for p in d[0] if p and p[0])
                except Exception:
                    pass
            time.sleep(1.5 * (intento + 1))
        return t, None
    fallos = 0
    if pendientes:
        # Si el traductor está bloqueado (pasa en GitHub), no perder minutos: lo traduce el navegador
        prueba, tr = uno(pendientes[0])
        if not tr:
            print("Traductor no disponible aquí; se traducirá en el navegador")
            return cache
        cache[prueba] = tr
        pendientes = pendientes[1:]
    with ThreadPoolExecutor(4) as ex:
        for t, tr in ex.map(uno, pendientes[:300]):
            if tr:
                cache[t] = tr
            else:
                fallos += 1
    print(f"Traducciones nuevas: {len(pendientes) - fallos}, fallidas: {fallos}")
    return cache

def main():
    os.makedirs(DOCS, exist_ok=True)
    estado = {}
    with ThreadPoolExecutor(12) as ex:
        res_feeds = list(ex.map(leer_feed, FUENTES))
        res_trends = list(ex.map(leer_trends, PAISES_TRENDS))
        res_wiki = list(ex.map(leer_wikipedia, ["en", "es"]))
        res_x = list(ex.map(leer_x, PAISES_X))
        bsky, err_b = ex.submit(leer_bluesky).result()
        masto, err_m = ex.submit(leer_mastodon).result()
    items = []
    for nombre, its, err in res_feeds:
        estado[nombre] = {"ok": err is None, "n": len(its), "error": err}
        items += its
    trends = []
    for codigo, ts, err in res_trends:
        estado["Google Trends " + codigo] = {"ok": err is None, "n": len(ts), "error": err}
        trends += ts
    wiki = {i: arts for i, arts in res_wiki}
    estado["Wikipedia"] = {"ok": bool(wiki.get("en")), "n": sum(len(v) for v in wiki.values()), "error": None}
    x_trends = {}
    for clave, ts, err in res_x:
        estado["X (Twitter) " + clave] = {"ok": err is None, "n": len(ts), "error": err}
        x_trends[clave] = ts
    estado["Bluesky"] = {"ok": err_b is None, "n": len(bsky), "error": err_b}
    estado["Mastodon"] = {"ok": err_m is None, "n": len(masto), "error": err_m}
    # Lo que se comparte en Bluesky y Mastodon también cuenta como señal social
    for b in bsky:
        if b["tema"]:
            items.append({"titulo": b["tema"] + ". " + b["descripcion"], "link": b["link"], "fecha": fecha(b["desde"]) or AHORA,
                          "medio": "Bluesky", "via": "Bluesky", "region": "Mundo", "cat": None, "tipo": "comunidad"})
    for m in masto:
        f = fecha(m["fecha"]) or AHORA
        if (AHORA - f) <= timedelta(hours=VENTANA_H):
            items.append({"titulo": m["titulo"], "link": m["link"], "fecha": f, "medio": m["medio"],
                          "via": "Mastodon", "region": "Mundo", "cat": None, "tipo": "comunidad"})

    # Las noticias que Google Trends asocia a cada búsqueda también cuentan como señal
    for t in trends:
        for ni in t["noticias"][:2]:
            if ni["titulo"]:
                items.append({"titulo": ni["titulo"], "link": ni["link"], "fecha": t["fecha"], "medio": ni["medio"] or "Google Trends",
                              "via": "Google Trends " + t["pais"], "region": REGION_PAIS.get(t["pais"], "Mundo"),
                              "cat": None, "tipo": "trends"})

    grupos = agrupar(items)
    wiki_tok = []
    for idioma, arts in wiki.items():
        for i, a in enumerate(arts):
            wiki_tok.append((palabras(a["articulo"]), a, i))

    temas = []
    for g in grupos:
        its = g["items"]
        medios = {}
        for it in its:
            medios.setdefault(it["medio"].lower(), it)
        n_medios = len(medios)
        if n_medios < 2 and not any(i["tipo"] == "trends" for i in its):
            continue
        texto = " ".join(i["titulo"] for i in its)
        tok = g["_p"]
        # búsquedas en Google Trends que coinciden con el tema
        tr_match = []
        for t in trends:
            tp = palabras(t["termino"])
            if tp and (tp <= tok or len(tp & tok) >= 2):
                tr_match.append(t)
        busquedas = sum(t["busquedas"] for t in tr_match)
        paises = sorted({t["pais"] for t in tr_match})
        w_match = [a for (wp, a, i) in wiki_tok if wp and len(wp) <= 4 and wp <= tok]
        comunidad = sum(1 for i in its if i["tipo"] == "comunidad")
        x_match = []
        for ts in x_trends.values():
            for xt in ts:
                xp = palabras(xt["termino"].lstrip("#"))
                if not xp or not xp <= tok or xp <= X_COMUNES:
                    continue
                if len(xp) == 1:
                    w = next(iter(xp))
                    if len(w) < 5 or w in X_COMUNES:
                        continue
                    if sum(1 for i in its if w in i["_p"]) < 2:
                        continue
                if True:
                    x_match.append({"termino": xt["termino"], "posts": xt["posts"], "pais": xt["pais"], "link": xt["link"]})
        redes = (["X"] if x_match else []) + sorted({i["via"].split(" r/")[0] for i in its
                                                    if i["via"] in ("Bluesky", "Mastodon", "Hacker News") or i["via"].startswith("Reddit")})
        mas_nueva = max(i["fecha"] for i in its)
        mas_vieja = min(i["fecha"] for i in its)
        edad_h = (AHORA - mas_vieja).total_seconds() / 3600
        recientes = sum(1 for i in its if (AHORA - i["fecha"]) <= timedelta(hours=6))
        # puntuación 0-100
        editoriales = len({i["medio"].lower() for i in its if i["tipo"] in ("medio", "agregador")})
        s = 0.0
        s += min(55, 14 * math.log2(1 + editoriales))
        if busquedas:
            s += min(15 if editoriales >= 2 else 8, 3 * math.log10(1 + busquedas))
        s += min(6, 3 * len(paises))
        s += min(6, 3 * len(w_match))
        s += min(6, 3 * comunidad)
        s += min(8, 3 * len({x["pais"] for x in x_match}))
        s += 12 * max(0.0, 1 - ((AHORA - mas_nueva).total_seconds() / 3600) / 24)
        s = round(min(100, s))
        if recientes >= max(2, 0.5 * len(its)):
            tendencia = "subiendo"
        elif (AHORA - mas_nueva) > timedelta(hours=12):
            tendencia = "enfriando"
        else:
            tendencia = "estable"
        # titular principal: el de la fuente de más peso (medio > agregador)
        orden = sorted(its, key=lambda i: ({"medio": 0, "agregador": 1, "trends": 2, "comunidad": 3}[i["tipo"]], -i["fecha"].timestamp()))
        principal = orden[0]["titulo"]
        cat_def = next((i["cat"] for i in its if i["cat"]), None)
        regiones = sorted({i["region"] for i in its} | {REGION_PAIS.get(p, "Mundo") for p in paises})
        sem, motivos = semaforo(texto)
        temas.append({
            "titulo": principal,
            "puntos": s,
            "tendencia": tendencia,
            "n_medios": n_medios,
            "busquedas": busquedas,
            "paises_trends": paises,
            "terminos_trends": sorted({t["termino"] for t in tr_match})[:6],
            "wikipedia": [{"articulo": a["articulo"], "visitas": a["visitas"], "link": a["link"]} for a in w_match[:3]],
            "categoria": categoria(texto, cat_def),
            "regiones": regiones,
            "semaforo": sem,
            "motivos": motivos,
            "primera": mas_vieja.isoformat(),
            "ultima": mas_nueva.isoformat(),
            "edad_h": round(edad_h, 1),
            "fuentes": [{"medio": i["medio"], "titulo": i["titulo"], "link": i["link"],
                         "fecha": i["fecha"].isoformat()} for i in list(medios.values())[:14]],
            "palabras": sorted(g["_np"])[:12],
            "redes": redes,
            "x": x_match[:5],
        })
    temas.sort(key=lambda t: t["puntos"], reverse=True)
    temas = temas[:250]

    # Traducción al español
    cache = cargar_cache()
    por_traducir = [t["titulo"] for t in temas if es_ingles(t["titulo"])]
    cache = traducir(por_traducir, cache)
    for t in temas:
        t["titulo_es"] = cache.get(t["titulo"], t["titulo"]) if es_ingles(t["titulo"]) else t["titulo"]
    # recortar caché a lo usado ahora para que no crezca sin fin
    usados = set(por_traducir)
    cache = {k: v for k, v in cache.items() if k in usados}
    with open(CACHE_TRAD, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    trends_out = []
    for t in sorted(trends, key=lambda x: x["busquedas"], reverse=True):
        trends_out.append({"termino": t["termino"], "termino_es": cache.get(t["termino"], t["termino"]),
                           "busquedas": t["busquedas"], "pais": t["pais"], "pais_nombre": t["pais_nombre"],
                           "fecha": t["fecha"].isoformat(), "noticias": t["noticias"][:3], "imagen": t["imagen"]})

    datos = {
        "actualizado": AHORA.isoformat(),
        "temas": temas,
        "trends": trends_out,
        "wikipedia": wiki,
        "redes": {"x": x_trends, "bluesky": bsky, "mastodon": masto},
        "estado_fuentes": estado,
    }
    with open(os.path.join(DOCS, "data.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    ok = sum(1 for v in estado.values() if v["ok"])
    print(f"Listo: {len(temas)} temas, {len(trends_out)} búsquedas, fuentes ok {ok}/{len(estado)}")

if __name__ == "__main__":
    main()
