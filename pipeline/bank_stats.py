import fitz, re, glob, os

files = sorted(glob.glob("/Users/moizrana/Downloads/archive_extract/*.pdf"))
tot_q = tot_ans = tot_img = 0
print(f'{"file":40} {"pg":>4} {"Qs":>5} {"ans":>5} {"figs":>5}')
for f in files:
    d = fitz.open(f)
    full = "\n".join(d[i].get_text() for i in range(d.page_count))
    nq = len(re.findall(r"(?m)^\s*\d+\)", full))
    na = full.count("\u2705")
    nimg = 0
    for i in range(d.page_count):
        for im in d[i].get_image_info(xrefs=True):
            x = im.get("xref", 0)
            if not x:
                continue
            try:
                px = d.extract_image(x)
            except Exception:
                continue
            if max(px["width"], px["height"]) >= 250:
                nimg += 1
    tot_q += nq
    tot_ans += na
    tot_img += nimg
    print(f"{os.path.basename(f)[:40]:40} {d.page_count:>4} {nq:>5} {na:>5} {nimg:>5}")
print(f'{"TOTAL":40} {"":>4} {tot_q:>5} {tot_ans:>5} {tot_img:>5}')
