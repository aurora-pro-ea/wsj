from __future__ import annotations

import re
from pathlib import Path


DONATION = [
    "### 打赏信息",
    "支付宝账户信息如下：",
    "",
    "户名：武书剑",
    "",
    "账号：13718398162",
]


def _article(year: int, month: int, day: int, title: str, lines: list[str]) -> dict:
    body_lines = [line.rstrip() for line in lines]
    body_lines.extend(["", "---", *DONATION])
    text = " ".join(line.strip() for line in body_lines if line.strip())
    return {
        "year": year,
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "month": month,
        "title": title,
        "body_lines": body_lines,
        "text": text,
    }


def _clean_fly_chunk(chunk: str, title: str) -> list[str]:
    lines: list[str] = []
    for raw in chunk.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith("![") or "附录" in line or "扫描下方二维码" in line:
            break
        if line == "武书剑" or re.fullmatch(r"2026年\s*7月\s*\d+日", line):
            continue
        if title in line or line.startswith("《#") or line.startswith("# "):
            continue
        section = re.match(r"^[（(]\s*([一二三四五六七八九十\d]+)\s*[）)]\s*(.*)$", line)
        if section:
            suffix = section.group(2).strip()
            lines.append(f"### （{section.group(1)}）{suffix}".rstrip())
        else:
            lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _fly_articles() -> list[dict]:
    # Unicode escapes keep this source file ASCII-safe on Windows consoles.
    path = Path("E:/\u6587\u6863/Obsidian Vault/\u98de\u8d8a\u75af\u4eba\u9662 !.md")
    if not path.exists():
        return []
    chunks = [c for c in re.split(r"(?m)^\s*----\s*$", path.read_text(encoding="utf-8")) if c.strip()]
    titles = [
        "王虹邓煜，双获“菲尔兹奖”，北大数学系引发全网关注",
        "强国之路！",
        "挥刀自宫！",
        "高票当选！",
        "互删好友！",
        "有福了！",
        "我不当好人！",
        "领先者的，魔咒！",
        "真的！",
        "有人脉！",
        "谢娜，爱唱歌！",
    ]
    # The source file omits dates on three adjacent entries; retain their July order.
    days = [29, 28, 28, 27, 23, 27, 27, 26, 27, 27, 26]
    return [_article(2026, 7, days[i], titles[i], _clean_fly_chunk(chunk, titles[i])) for i, chunk in enumerate(chunks)]


def _image_articles() -> list[dict]:
    return [
        _article(
            2026,
            7,
            11,
            "票房大卖！",
            [
                "### （一）免费",
                "某人去英国旅游，夜间突发疾病，紧急拨打999。救护车将其送往最近的一家医院进行紧急救治。某人醒来第一句话就问：“缴多少钱？”救护人员告知：“不需要缴费”。某人解释说：“我不是英国公民，我是来自中国的游客”。医护人员奇怪地说：“游客也是‘人’呀？”",
                "某人去美国旅游，夜间突发疾病被送往急诊救治。某人醒来第一句话说：“我不是美国公民，我是来自中国的游客，要缴多少钱？”医护人员奇怪地说：外籍游客一样免费！",
                "某非洲黑人来我国旅游，夜间突发疾病，救护车将其送往最好的医院。黑人醒来第一句话就问：“我不是中国公民，是来自非洲的游客，要缴多少医疗费？”医护人员亲切地说：全免费！",
                "三个国家，对外籍游客，全都实施免费急诊救护，背后的逻辑却截然相反：英美的急诊免费，是人道主义精神；我们的急诊免费，却是超过国民待遇！",
                "### （二）美国",
                "7月4日，美国建国250周年。",
                "小粉红说美国建国只有250年，太短了。可是，他们忘记了，我们建国只有76年，比美国更短。",
                "有人说，按照美国“朝代寿命不超三百年”的历史规律，美国很快就要改朝换代了。其实，美国每四年就改朝换代一次，比我国历史上最短的大秦王朝寿命还短！",
                "有人说，美国建国250年，一直在走下坡，是垂死的、腐朽的国家。其实，大量客观证据证明，美国仍然是全球最成功、最具活力、最富有、最自由的国家。",
                "其一，美国仍是全球最适合创业、最适合追梦的国家，拥有世界最庞大、最透明、最公正的经济体。近三年，平均每年诞生550万家新企业！",
                "其二，在美国，个人创业者借助人工智能，凭一台电脑就能完成过去十多人的团队才能完成的工作。近三年，年收入突破100万美元的个人创业者暴涨三倍，显示出AI掀起的一波创业革命。美国，是最适合个人奋斗的地方。",
                "美国的经济规模，超过了中国、德国和日本三国的总和。美国的股市市值，占全球所有股市市值的65%。全球57%的创投资金，流向美国。美国的军事势力，超过了全世界所有国家军事力量总和。",
                "其四，美国在基础科学、原始创新、人才集聚和高端转化上，仍保持最强整体实力，处于断层式领先位置。全球最顶尖的科技人才，40%在美国！",
                "其五，除了经济、科技、军事遥遥领先之外，美国民众公益精神也冠绝全球。2025年，美国普通民众的慈善捐款总额，高达6172亿美元。",
                "祝福星爷电影《功夫女足》，今天上映！口碑炸裂、票房大卖！",
            ],
        ),
        _article(
            2026,
            7,
            16,
            "差评！",
            [
                "### （一）差评",
                "一家饭店，顾客可以给好评，也可以给差评。这，就是一家“饭店”。",
                "一家饭店，顾客只能给好评，绝不能给差评。这，就是一家“黑店”。",
                "一位国家元首，如果只能投赞成票，不能投反对票。那么，这就不是民主，而是披着“民主”外衣的“专制”；这就不是公仆，而是披着“公仆”外衣的“公敌”。",
                "没有反对、没有差评的国家，就是“黑社会”；只有赞同、没有反对的元首，就是“黑老大”！",
                "### （二）奴隶",
                "在奴隶制社会，如果你批评奴隶主，最先攻击你的，不是奴隶王，而是他的奴隶。奴隶，会全心全意维护奴隶主的利益和尊严！",
                "在专制社会，如果你评判专权者，最先攻击你的，不是专权者，而是它的奴才！奴才，要全心全意维护主子的利益和尊严！",
                "任何抹黑“大清”者，皆为我大清子民之公敌，群起而攻，虽远必诛！",
                "### （三）感恩",
                "奴性十足的人会认为，接受捐款的贫穷人家，应该对着镜头感恩涕零；接受资助的贫困学生应该站到台上感恩鞠躬！",
                "这种要求，是对弱势人群的公开侮辱！这种思维，是深植于骨髓的十足奴性！",
                "### （四）尊严",
                "弱势群体的尊严，来自强势群体的“平等”对待。",
                "对于弱势群体，无论表现出过于冷漠，还是过于热情；过于无视，还是过于尊重；实行“一路红灯”，还是实行“一路绿灯”，本质上都是一种区别对待。",
                "区别对待，就是一种“歧视”、一种“不平等”！",
                "同样道理，对于民营企业家，不需要被当作“自己人”、当作“亲人”、当作“主人”、当作“衣食父母”、当作“上帝”！只需要把他们当作平等的市场主体。",
            ],
        ),
    ]


def parse_extra_articles() -> list[dict]:
    return _fly_articles() + _image_articles()
