"""Build docs/index.html and docs/th/index.html from build/data.json.

  python3 tools/build.py
"""
import html, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.load(open(ROOT / "build/data.json"))
SITE = "https://nanobotco.github.io/nitpick/"
e = html.escape

# old sheet readers vs nitpick on these 12 frames, from the transcripts (per frame)
# old: the 23 Sep reader of sheets s063-s083 (these frames sit on s073), 105 frames, 138 turns
# new: the nitpick reader of work/np batch b01, 12 frames, 9 turns
COST = {"old_fresh": 14903, "old_cache": 241251, "new_fresh": 9030, "new_cache": 54208}

T = {
 "en": {
  "title": "Nitpick", "sub": "Reading every sign in a 360 photo",
  "desc": "A 360 camera sees every sign on the street at once. Nitpick has the Mac read first and hands a model only the pieces it could not settle, at full size. A demo on 12 photos of Mahidol Road, Chiang Mai.",
  "nav": [("look", "Look"), ("dust", "Dust"), ("steps", "Steps"), ("finds", "Finds"), ("cost", "Cost"), ("try", "Try it")],
  "kicker": "A demo: 12 photos, one road",
  "lede": "A 360 camera sees every sign on the street at once. Show a computer the whole picture and it sees none of them: the photo gets shrunk until the letters are dust. Nitpick has the Mac read first, and hands the model only the pieces it could not settle, at full size.",
  "nan": "I ride. The camera shoots every two seconds.", "beer": "The Mac reads first. The model only squints where it has to.",
  "look_h": "Look around", "look_p": "Drag the picture. This is one of the 12 frames, 23 Sep 2026, Mahidol Road near the airport, straightened and with faces pixelated. The rider is NaN.",
  "dust_h": "Shrunk to dust",
  "dust_p": "The camera makes a sphere 7,680 pixels around: about 21 pixels for every degree. A model reads a picture about 1,568 pixels across, so a whole sphere reaches it at 4.4 pixels a degree. Here is one sign both ways.",
  "dust_a": "What a model sees when handed the whole sphere", "dust_b": "The same sign at camera size",
  "steps_h": "Six steps, five on the Mac",
  "s1h": "Level", "s1p": "A camera on a motorbike leans. The Mac finds the straight edges (poles, walls, window frames), works out which way is up, and turns the sphere upright, so every later cut stands straight. The camera leaned {tilt}° in this frame.",
  "s1a": "As shot", "s1b": "Levelled",
  "s2h": "Tiles", "s2p": "Each sphere is cut into 24 views: eight directions, three heights, each 50° wide and 30° tall at full camera size. Small signs stay the size they were shot.",
  "s3h": "The Mac reads", "s3p": "Apple Vision, on the Mac itself, reads Thai and English on every tile, finds faces (pixelated before any picture leaves the machine) and names the scene: mural, lantern, parked motorbikes. {tiles} tiles, {boxes} pieces of text on this set. Green = sure, orange = likely, red = a guess.",
  "s3l": "Scene labels on this tile",
  "s4h": "Settled, or cut out", "s4p": "A read that names a Mot Dang listing within 60 metres, with every other line read sure, is settled: no picture needed. Everything else becomes a crop, enlarged until each line of text is 26 pixels tall, and packed onto a sheet. This set: {settled} settled, {signs} sign crops, {labels} scene crops.",
  "s4d": "The start of the digest the model reads first",
  "s5h": "Sweep", "s5p": "Each spot also goes out as one low-resolution 360 strip. It shows where to look, not what a sign says, so the model can catch what no detector flagged: spirit houses, murals, wrapped transformer boxes, bikes parked in a row.",
  "s6h": "Zoom", "s6p": "When a crop leaves a doubt, the model asks for that exact direction at camera size, and can ask for the frames either side to pick the sharper one. The reader took {zooms} zooms on this set.",
  "s7h": "One reader, few turns", "s7p": "A model re-reads everything in its context on every turn, so turns cost more than pictures. The reader gets one batch: the digest, then every page at once, then every zoom at once, then one write. This run took 9 turns; the old reader of these frames took 138.",
  "finds_h": "What it found", "finds_p": "{n} things written by the reader on these 12 frames. Pictures re-cut from the sphere where the reader pointed.",
  "vs_h": "Against the old way", "vs_p": "The same 12 frames were read on 23 Sep by the old method: contact sheets of four flat views per frame, opened whole. {old} named places then; {new} now. Both lists:",
  "vs_both": "Both", "vs_old": "Old only", "vs_new": "Nitpick only",
  "cost_h": "Cost per frame", "cost_p": "Tokens are the pieces a model reads; a picture costs about one token per 750 pixels. Counted from the readers' own records.",
  "fresh": "New input", "cache": "Context re-read", "old": "Old way", "new": "Nitpick",
  "try_h": "Try it", "try_p": "Needs a Mac (Apple Vision), Python with OpenCV, and ffmpeg. The code is in this repository under tool/.",
  "foot": "Photographs NaN Peacock, CC BY 4.0. Text CC BY 4.0, NaNoBotCo. Code MIT.",
  "lang": "ไทย", "lang_href": "th/", "here": "EN",
 },
 "th": {
  "title": "Nitpick · จับทุกป้าย", "sub": "อ่านทุกป้ายในภาพ 360 องศา",
  "desc": "กล้อง 360 เห็นทุกป้ายริมถนนในครั้งเดียว Nitpick ให้เครื่อง Mac อ่านก่อน แล้วส่งให้โมเดลดูเฉพาะชิ้นที่ยังอ่านไม่ออก ในขนาดเต็ม ตัวอย่างจากภาพ 12 ภาพบนถนนมหิดล เชียงใหม่",
  "nav": [("look", "ดูรอบตัว"), ("dust", "ฝุ่น"), ("steps", "ขั้นตอน"), ("finds", "ที่เจอ"), ("cost", "ต้นทุน"), ("try", "ลองใช้")],
  "kicker": "ตัวอย่าง: 12 ภาพ ถนนเส้นเดียว",
  "lede": "กล้อง 360 เห็นทุกป้ายริมถนนในครั้งเดียว แต่ถ้ายื่นทั้งภาพให้คอมพิวเตอร์ดู มันจะไม่เห็นสักป้าย เพราะภาพถูกย่อจนตัวหนังสือเหลือแต่ฝุ่น Nitpick ให้เครื่อง Mac อ่านก่อน แล้วส่งให้โมเดลดูเฉพาะชิ้นที่ยังอ่านไม่ออก ในขนาดเต็ม",
  "nan": "ฉันขี่รถ กล้องถ่ายทุกสองวินาที", "beer": "Mac อ่านก่อน โมเดลค่อยเพ่งเฉพาะตรงที่จำเป็น",
  "look_h": "ดูรอบตัว", "look_p": "ลากภาพเพื่อหมุนดู นี่คือหนึ่งใน 12 ภาพ วันที่ 23 ก.ย. 2569 ถนนมหิดลใกล้สนามบิน ปรับให้ตรงแล้ว และเบลอใบหน้าแล้ว คนขี่คือแนน",
  "dust_h": "ย่อจนเป็นฝุ่น",
  "dust_p": "กล้องสร้างภาพทรงกลมกว้างรอบตัว 7,680 พิกเซล หรือราว 21 พิกเซลต่อองศา โมเดลอ่านภาพได้กว้างราว 1,568 พิกเซล ถ้าส่งไปทั้งลูก จะเหลือแค่ 4.4 พิกเซลต่อองศา ดูป้ายเดียวกันทั้งสองแบบ",
  "dust_a": "สิ่งที่โมเดลเห็นเมื่อได้ภาพทั้งลูก", "dust_b": "ป้ายเดียวกันในขนาดที่กล้องถ่าย",
  "steps_h": "หกขั้น ห้าขั้นทำบน Mac",
  "s1h": "ปรับระดับ", "s1p": "กล้องบนมอเตอร์ไซค์มักเอียง Mac หาเส้นตรง (เสา ผนัง กรอบหน้าต่าง) เพื่อหาทิศขึ้น แล้วหมุนภาพทรงกลมให้ตั้งตรง ทุกภาพที่ตัดต่อจากนี้จึงไม่เอียง ภาพนี้กล้องเอียง {tilt}°",
  "s1a": "ตอนถ่าย", "s1b": "ปรับแล้ว",
  "s2h": "ตัดเป็นช่อง", "s2p": "ภาพทรงกลมแต่ละภาพถูกตัดเป็น 24 มุม: แปดทิศ สามระดับ แต่ละมุมกว้าง 50° สูง 30° ในความละเอียดเต็มของกล้อง ป้ายเล็กยังคงขนาดเดิม",
  "s3h": "Mac อ่าน", "s3p": "Apple Vision ที่อยู่ในเครื่อง Mac เอง อ่านภาษาไทยและอังกฤษทุกช่อง หาใบหน้า (เบลอก่อนภาพใดออกจากเครื่อง) และบอกว่าเป็นฉากอะไร เช่น ภาพวาดฝาผนัง โคมไฟ มอเตอร์ไซค์จอดเรียง ชุดนี้มี {tiles} ช่อง ตัวหนังสือ {boxes} ชิ้น สีเขียว = แน่ใจ สีส้ม = น่าจะใช่ สีแดง = เดา",
  "s3l": "ฉากที่ Mac บอกในช่องนี้",
  "s4h": "จบ หรือ ตัดส่ง", "s4p": "ป้ายที่อ่านได้ตรงกับชื่อร้านใน Mot Dang ภายใน 60 เมตร และบรรทัดอื่นอ่านได้แน่ใจ ถือว่าจบ ไม่ต้องส่งภาพ ที่เหลือถูกตัดเป็นชิ้น ขยายจนตัวหนังสือแต่ละบรรทัดสูง 26 พิกเซล แล้ววางรวมเป็นแผ่น ชุดนี้: จบ {settled} ป้าย ตัดป้าย {signs} ชิ้น ตัดฉาก {labels} ชิ้น",
  "s4d": "ต้นของบันทึกสรุปที่โมเดลอ่านเป็นอย่างแรก",
  "s5h": "กวาดรอบ", "s5p": "แต่ละจุดยังส่งภาพ 360 ความละเอียดต่ำหนึ่งแถบ แถบนี้บอกว่าควรดูตรงไหน ไม่ได้บอกว่าป้ายเขียนอะไร โมเดลจึงจับสิ่งที่เครื่องตรวจไม่เจอได้ เช่น ศาลพระภูมิ ภาพวาดฝาผนัง ตู้หม้อแปลงที่หุ้มลาย มอเตอร์ไซค์จอดเรียง",  # stylecheck: allow — says where the strip points the model, not advice to the reader
  "s6h": "ซูม", "s6p": "ถ้าชิ้นไหนยังไม่ชัด โมเดลขอดูทิศนั้นในขนาดเต็ม และขอภาพก่อนหลังเพื่อเลือกภาพที่คมกว่าได้ ชุดนี้ซูม {zooms} ครั้ง",
  "s7h": "ผู้อ่านหนึ่งตัว ไม่กี่รอบ", "s7p": "ทุกรอบโมเดลต้องอ่านทุกอย่างในหัวซ้ำ จำนวนรอบจึงแพงกว่าจำนวนภาพ ผู้อ่านได้หนึ่งชุด: อ่านบันทึกสรุป เปิดทุกแผ่นพร้อมกัน ซูมทั้งหมดพร้อมกัน แล้วเขียนผลครั้งเดียว รอบนี้ใช้ 9 รอบ ผู้อ่านแบบเก่าของภาพชุดนี้ใช้ 138 รอบ",
  "finds_h": "ที่เจอ", "finds_p": "ผู้อ่านเขียนไว้ {n} รายการจาก 12 ภาพนี้ ภาพตัดใหม่จากภาพทรงกลมตรงทิศที่ผู้อ่านชี้",
  "vs_h": "เทียบกับวิธีเก่า", "vs_p": "12 ภาพนี้เคยอ่านด้วยวิธีเก่าเมื่อ 23 ก.ย.: แผ่นรวมภาพแบนสี่มุมต่อภาพ เปิดดูทั้งแผ่น ตอนนั้นได้ชื่อสถานที่ {old} ชื่อ ครั้งนี้ {new} ชื่อ รายชื่อทั้งสองฝั่ง:",
  "vs_both": "เจอทั้งคู่", "vs_old": "เฉพาะวิธีเก่า", "vs_new": "เฉพาะ Nitpick",
  "cost_h": "ต้นทุนต่อภาพ", "cost_p": "โทเคนคือชิ้นที่โมเดลอ่าน ภาพหนึ่งภาพใช้ราวหนึ่งโทเคนต่อ 750 พิกเซล นับจากบันทึกของผู้อ่านเอง",
  "fresh": "ข้อมูลใหม่", "cache": "อ่านซ้ำในหัว", "old": "วิธีเก่า", "new": "Nitpick",
  "try_h": "ลองใช้", "try_p": "ต้องใช้ Mac (Apple Vision), Python กับ OpenCV และ ffmpeg โค้ดอยู่ในคลังนี้ที่ tool/",
  "foot": "ภาพถ่าย NaN Peacock, CC BY 4.0 ข้อความ CC BY 4.0, NaNoBotCo โค้ด MIT",
  "lang": "EN", "lang_href": "../", "here": "ไทย",
 },
}

CSS = """
:root{--bg:#F4F1EA;--panel:#fff;--ink:#1D2129;--mute:#5E6470;--line:#DDD6C8;--accent:#0F7B6C;--warm:#D9822B;
--display:"Avenir Next",Avenir,"Segoe UI",system-ui,-apple-system,Helvetica,Arial,sans-serif;
--thai:"Sukhumvit Set","Noto Sans Thai","Leelawadee UI",Thonburi,Tahoma,sans-serif;--mono:ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15181D;--panel:#1E2229;--ink:#ECEAE4;--mute:#A4A9B3;--line:#343944;--accent:#3FC1AC;--warm:#F0A45A}}
:root[data-theme=dark]{--bg:#15181D;--panel:#1E2229;--ink:#ECEAE4;--mute:#A4A9B3;--line:#343944;--accent:#3FC1AC;--warm:#F0A45A}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.6 var(--display)}
body.th{font-family:var(--thai)}
.in{max-width:980px;margin:0 auto;padding:0 16px}
header.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
header.top .in{display:flex;gap:14px;align-items:center;min-height:52px;flex-wrap:wrap}
.brand{font-weight:800;color:var(--ink);text-decoration:none;font-size:20px}
nav{display:flex;gap:12px;flex-wrap:wrap;font-size:15px;flex:1}
nav a,.langsw a{color:var(--mute);text-decoration:none}nav a:hover{color:var(--accent)}
.langsw a[aria-current]{color:var(--ink);font-weight:700}
h1{font-size:clamp(40px,8vw,76px);line-height:1;margin:.2em 0 .1em;letter-spacing:-.02em}
h2{font-size:clamp(26px,4.5vw,38px);margin:0 0 .3em;line-height:1.15}
h3{font-size:22px;margin:0 0 .2em}
.kicker{color:var(--accent);font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-size:14px}
.sub{font-size:clamp(20px,3vw,26px);color:var(--mute);margin:0}
.lede{font-size:20px;max-width:720px}
section{padding:40px 0;border-bottom:1px solid var(--line)}
figure{margin:18px 0}figure img{display:block;width:100%;height:auto;border-radius:8px;border:1px solid var(--line)}
figcaption{font-size:15px;color:var(--mute);margin-top:6px}
.pano{position:relative;height:min(58vh,480px);border-radius:10px;overflow:hidden;cursor:grab;background:#000 center/auto 100% repeat-x;touch-action:pan-y;border:1px solid var(--line)}
.pano:active{cursor:grabbing}.pano span{position:absolute;right:10px;bottom:10px;background:rgba(0,0,0,.6);color:#fff;font-size:14px;padding:3px 10px;border-radius:12px}
.cast{display:flex;gap:14px;flex-wrap:wrap;margin-top:18px}
.say{display:flex;gap:10px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:8px 14px 8px 8px;max-width:440px}
.say img{width:56px;height:56px;border-radius:50%}.say b{display:block;font-size:14px;color:var(--accent)}.say p{margin:0;font-size:16px;line-height:1.35}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.two img{image-rendering:pixelated}
@media (max-width:640px){.two{grid-template-columns:1fr}}
.step{display:grid;grid-template-columns:64px 1fr;gap:12px;margin:34px 0}
.step>div{min-width:0}
.num{font-size:44px;font-weight:800;color:var(--accent);line-height:1}
.grid24{display:grid;grid-template-columns:repeat(8,1fr);gap:3px}.grid24 img{width:100%;display:block;border-radius:2px}
@media (max-width:640px){.grid24{grid-template-columns:repeat(4,1fr)}}
ol.reads{columns:2;font-size:15px;padding-left:22px}ol.reads li{break-inside:avoid}
@media (max-width:640px){ol.reads{columns:1}}
.c1{color:#2E9B45}.c5{color:var(--warm)}.c3{color:#D0443C}
pre{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto;font:13px/1.5 var(--mono);white-space:pre}
.scroll{overflow-x:auto;border-radius:8px;border:1px solid var(--line)}.scroll img{max-width:none;width:1100px;border:0;border-radius:0}
.finds{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.find{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.find img{width:100%;aspect-ratio:3/2;object-fit:cover;display:block}.find div{padding:8px 12px 12px;font-size:15px;line-height:1.4}
.find b{font-size:17px;display:block}.find i{color:var(--mute);font-style:normal;display:block}.find small{color:var(--mute)}
.tag{display:inline-block;font-size:12px;padding:1px 8px;border-radius:9px;background:var(--accent);color:#fff;margin-right:4px}
.vs{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.vs ul{padding-left:18px;font-size:15px;margin:.3em 0}
@media (max-width:640px){.vs{grid-template-columns:1fr}}
.bars{display:grid;gap:10px;margin-top:10px}.bar{display:grid;grid-template-columns:130px 1fr;gap:10px;align-items:center;font-size:15px}
.bar div{height:26px;border-radius:5px;background:var(--mute);color:#fff;font-size:13px;padding:3px 8px;white-space:nowrap}
.bar div.n{background:var(--accent)}
.bar-h{font-weight:700;margin-top:14px}
footer{padding:30px 0 60px;color:var(--mute);font-size:14px}footer a{color:var(--mute)}
a{color:var(--accent)}
"""

JS = """
(function(){var p=document.querySelector('.pano');if(!p)return;var x=0,d=null,w=0;
var img=new Image();img.onload=function(){w=img.width*(p.clientHeight/img.height);};img.src=p.dataset.src;
function set(){p.style.backgroundPosition=x+'px 0';}
p.addEventListener('pointerdown',function(e){d=e.clientX;p.setPointerCapture(e.pointerId);});
p.addEventListener('pointermove',function(e){if(d===null)return;x+=e.clientX-d;d=e.clientX;set();});
p.addEventListener('pointerup',function(){d=null;});p.addEventListener('keydown',function(e){if(e.key=='ArrowLeft'){x+=40;set();}if(e.key=='ArrowRight'){x-=40;set();}});
var t=0,auto=setInterval(function(){if(d===null&&t<600){x-=.6;t++;set();}},30);})();
"""


def norm(s):
    import re
    return re.sub(r"[^0-9a-z฀-๿]", "", (s or "").lower().replace("บริษัท", "").replace("จำกัด", ""))


def names_compare():
    """Places as sets of names (a sign's Thai and Latin both count); two places match on any name pair."""
    import difflib, glob
    P = Path.home() / "Developer/claude code projects/mot-dang/_incoming/gopro-2026-09-23/pass2/reads"
    fr = {f"GSAB2131_{i}" for i in range(145, 157)}

    def add(bag, *names):
        ks = {norm(n) for n in names if n and len(norm(n)) >= 3}
        if not ks:
            return
        for b in bag:
            if any(same(k, x) for k in ks for x in b["k"]):
                b["k"] |= ks; return
        bag.append({"k": ks, "label": names[0].strip()})

    def same(a, b):
        return a == b or (min(len(a), len(b)) >= 4 and (a in b or b in a)) or difflib.SequenceMatcher(None, a, b).ratio() >= .8
    old, new = [], []
    for p in glob.glob(str(P / "*.jsonl")):
        for l in open(p):
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if d.get("frame") in fr:
                for pl in d.get("places", []):
                    if pl.get("name"):
                        add(old, pl["name"], pl.get("name_other"))
    for r in D["reads"]:
        if r.get("name") and r.get("kind") != "rider":
            add(new, r["name"], r.get("name_other"))
    for name in D.get("settled_names", []):  # settled on the Mac; the reader never saw these
        add(new, name)
    hit = lambda a, bag: any(same(k, x) for b in bag for k in a["k"] for x in b["k"])
    both = sorted(b["label"] for b in new if hit(b, old))
    only_old = sorted(b["label"] for b in old if not hit(b, new))
    only_new = sorted(b["label"] for b in new if not hit(b, old))
    return len(old), len(new), both, only_old, only_new


def page(lang):
    t = T[lang]; th = lang == "th"; up = "../" if th else ""
    n_old, n_new, both, only_old, only_new = names_compare()
    f = lambda k, **kw: e(t[k].format(**kw))
    finds = []
    for r in D["finds"]:
        what = r.get("what_th") if th else r.get("what_en")
        bits = [x for x in (r.get("phone"), r.get("hours"), r.get("prices"), r.get("line_id"), r.get("web")) if x]
        rec = f'<small>motdang: {e(r["record_id"])}</small>' if r.get("record_id") else ""
        finds.append(f'<div class="find"><img src="{up}img/{r["img"]}" alt="{e(r.get("name") or what or "")}" loading="lazy">'
                     f'<div><span class="tag">{e(r.get("kind", "place"))}</span><b lang="th">{e(r.get("name") or "·")}</b>'
                     f'{"<i>" + e(r["name_other"]) + "</i>" if r.get("name_other") else ""}<i>{e(what or "")}</i>'
                     f'{"<small>" + e(" · ".join(bits)) + "</small><br>" if bits else ""}{rec}</div></div>')
    ocr = "".join(f'<li class="c{1 if l["conf"] >= 1 else 5 if l["conf"] >= .5 else 3}" lang="th">{e(l["s"])} <small>({l["conf"]})</small></li>'
                  for l in D["ocr"]["lines"])
    labels = ", ".join(f'{e(a)} {b:.2f}' for a, b in D["ocr"]["labels"])
    tiles = "".join(f'<img src="{up}img/tile_y{y}_p{p}.jpg" alt="" loading="lazy">' for p in (28, 3, -22) for y in range(-180, 180, 45))
    mx = max(COST["old_cache"], 1)
    bar = lambda v, cls: f'<div class="{cls}" style="width:{max(4, 100 * v / mx):.1f}%">{v:,}</div>'
    ul = lambda xs: "<ul>" + "".join(f'<li lang="th">{e(x)}</li>' for x in xs) + "</ul>"
    nav = "".join(f'<a href="#{a}">{e(b)}</a>' for a, b in t["nav"])
    dig = e("\n".join(D["digest"]))
    zooms = "".join(f'<figure><img src="{up}img/zoom{i}.jpg" alt="" loading="lazy"><figcaption>{e(z)}</figcaption></figure>'
                    for i, z in enumerate(D["zoom_names"], 1))
    return f"""<!doctype html><html lang="{lang}" translate="no" class="notranslate"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="google" content="notranslate">
<title>{e(t["title"])}</title>
<meta name="description" content="{e(t["desc"])}">
<link rel="canonical" href="{SITE}{"th/" if th else ""}">
<link rel="alternate" hreflang="en" href="{SITE}"><link rel="alternate" hreflang="th" href="{SITE}th/">
<meta property="og:type" content="website"><meta property="og:site_name" content="NaNoBotCo">
<meta property="og:title" content="{e(t["title"])}: {e(t["sub"])}"><meta property="og:description" content="{e(t["desc"])}">
<meta property="og:url" content="{SITE}{"th/" if th else ""}"><meta property="og:image" content="{SITE}card.jpg">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{SITE}card.jpg">
<link rel="icon" href="{up}icon.svg" type="image/svg+xml">
<style>{CSS}</style></head>
<body{' class="th"' if th else ""}>
<header class="top"><div class="in"><a class="brand" href="{up}">Nitpick</a><nav aria-label="Sections">{nav}</nav>
<span class="langsw"><a aria-current="page">{t["here"]}</a> · <a href="{t["lang_href"]}">{t["lang"]}</a></span></div></header>
<main class="in">
<section id="top"><span class="kicker">{f("kicker")}</span><h1>{e(t["title"])}</h1><p class="sub">{f("sub")}</p>
<p class="lede">{f("lede")}</p>
<div class="cast"><div class="say"><img src="{up}img/nan.svg" alt=""><p><b>NaN</b>{f("nan")}</p></div>
<div class="say"><img src="{up}img/beer.svg" alt=""><p><b>Beer</b>{f("beer")}</p></div></div></section>

<section id="look"><h2>{f("look_h")}</h2><p>{f("look_p")}</p>
<div class="pano" tabindex="0" role="img" aria-label="{f("look_h")}" data-src="{up}img/hero.jpg" style="background-image:url({up}img/hero.jpg)"><span>⟷</span></div></section>

<section id="dust"><h2>{f("dust_h")}</h2><p>{f("dust_p")}</p>
<div class="two"><figure><img src="{up}img/dust-model.jpg" alt=""><figcaption>{f("dust_a")}</figcaption></figure>
<figure><img src="{up}img/dust-native.jpg" alt="{e(D["dust"]["name"])}"><figcaption>{f("dust_b")}: <span lang="th">{e(D["dust"]["name"])}</span></figcaption></figure></div></section>

<section id="steps"><h2>{f("steps_h")}</h2>
<div class="step"><div class="num">1</div><div><h3>{f("s1h")}</h3><p>{f("s1p", tilt=D["tilt"])}</p>
<figure><img src="{up}img/level-before.jpg" alt=""><figcaption>{f("s1a")}</figcaption></figure>
<figure><img src="{up}img/level-after.jpg" alt=""><figcaption>{f("s1b")}</figcaption></figure></div></div>
<div class="step"><div class="num">2</div><div><h3>{f("s2h")}</h3><p>{f("s2p")}</p><div class="grid24">{tiles}</div></div></div>
<div class="step"><div class="num">3</div><div><h3>{f("s3h")}</h3><p>{f("s3p", tiles=D["tiles_read"], boxes=D["text_boxes"])}</p>
<figure><img src="{up}img/ocr.jpg" alt=""></figure><ol class="reads">{ocr}</ol><p><small>{f("s3l")}: {labels}</small></p></div></div>
<div class="step"><div class="num">4</div><div><h3>{f("s4h")}</h3><p>{f("s4p", settled=D["crops"]["settled"], signs=D["crops"]["sign"], labels=D["crops"]["label"])}</p>
<figure><img src="{up}img/sheet.jpg" alt="" loading="lazy"></figure><p><small>{f("s4d")}</small></p><pre lang="th">{dig}</pre></div></div>
<div class="step"><div class="num">5</div><div><h3>{f("s5h")}</h3><p>{f("s5p")}</p><div class="scroll"><img src="{up}img/sweep.jpg" alt="" loading="lazy"></div></div></div>
<div class="step"><div class="num">6</div><div><h3>{f("s6h")}</h3><p>{f("s6p", zooms=D["zooms"])}</p>{zooms}</div></div>
<div class="step"><div class="num">✓</div><div><h3>{f("s7h")}</h3><p>{f("s7p")}</p></div></div></section>

<section id="finds"><h2>{f("finds_h")}</h2><p>{f("finds_p", n=len(D["finds"]))}</p><div class="finds">{"".join(finds)}</div>
<h3 style="margin-top:34px">{f("vs_h")}</h3><p>{f("vs_p", old=n_old, new=n_new)}</p>
<div class="vs"><div><b>{f("vs_both")} · {len(both)}</b>{ul(both)}</div><div><b>{f("vs_old")} · {len(only_old)}</b>{ul(only_old)}</div><div><b>{f("vs_new")} · {len(only_new)}</b>{ul(only_new)}</div></div></section>

<section id="cost"><h2>{f("cost_h")}</h2><p>{f("cost_p")}</p><div class="bars">
<div class="bar-h">{f("fresh")}</div><div class="bar"><span>{f("old")}</span>{bar(COST["old_fresh"], "o")}</div><div class="bar"><span>{f("new")}</span>{bar(COST["new_fresh"], "n")}</div>
<div class="bar-h">{f("cache")}</div><div class="bar"><span>{f("old")}</span>{bar(COST["old_cache"], "o")}</div><div class="bar"><span>{f("new")}</span>{bar(COST["new_cache"], "n")}</div></div></section>

<section id="try"><h2>{f("try_h")}</h2><p>{f("try_p")}</p>
<pre>python3 tool/nitpick.py prep out/ photos/ --prov cm
python3 tool/nitpick.py cost out/
python3 tool/nitpick.py zoom out/ GSAB2131_147 -162 19 --fov 20 --n 1</pre>
<p><a href="https://github.com/NaNoBotCo/nitpick">github.com/NaNoBotCo/nitpick</a></p></section>
</main>
<footer><div class="in">{f("foot")} · <a href="https://nanobotco.github.io/indras-net/">Indra's Net, Drawn</a> · <a href="https://nanobotco.github.io/chemtrails/">Chemtrails? It's ice.</a> · <a href="https://motdang.net/">Mot Dang</a></div></footer>
<script>{JS}</script></body></html>"""


(ROOT / "docs/index.html").write_text(page("en"), encoding="utf-8")
(ROOT / "docs/th").mkdir(exist_ok=True)
(ROOT / "docs/th/index.html").write_text(page("th"), encoding="utf-8")
print("built")
