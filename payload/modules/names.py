# ============================================================
# NAMES.PY
# PROVIDES: translate_name, _display_text, _proto_display_name,
#           _english_display_text, _proto_english_name, _lang_translate,
#           translate_paint, is_junk_skin_name,
#           _clean_catalog_text, _contains_cjk, _is_english_text,
#           PAINT_EN, _NAME_SEGMENTS, _OFFICIAL_* tables, WEAPON_CATS
# REQUIRES: re, json (stdlib), _plog at call time (main.py)
# ============================================================
"""Name localization for catalog rows and HUD text.

Layered resolution (proven order): official exact map -> junk filter ->
segment translation -> paint table -> game lang table -> raw fallback.
All large tables move byte-exact from core.py (see REWRITE_PLAN.md S6).
"""
import re
import json

# v8.18/v8.19: THE AR-PICKER JUNK NAME FILTER
# ============================================================
# The type-1 family still listed non-displayable rows next to the
# real skins - the device examples: 'Yamato(Placeholder)', 'Low-Spec
# Appearance', 'Low Grade Inspect', 'Heavenly Ink Armor LV5 Advanced
# Body'. These are engineering meshes / upgrade bodies the game's own
# picker never offers. Matched on the FINAL (translated) name so both
# the English and the untranslated-CJK shapes are covered.
# v8.19: defined at the TOP of the module - the v8.18 copy sat below
# the catalog machinery, so the FIRST device build attempt ran before
# the def existed (NameError, caught, retry won - fixed anyway).
JUNK_EN = ('placeholder', 'low-spec', 'low grade',
                 'low-poly', 'advanced body')
JUNK_CJK = ('占位', '低配版外观', '低级枪身', '高级枪身',
                  '低级检视')


def is_junk_skin_name(name):
    """True when the resolved skin name marks a non-displayable row."""
    try:
        raw = str(name or '')
        if not raw.strip():
            return False
        low = raw.lower()
        for _t in JUNK_EN:
            if _t in low:
                return True
        for _t in JUNK_CJK:
            if _t in raw:
                return True
    except Exception:
        return False
    return False




# ============================================================
# Messiah taggeddict-safe proto helpers (v2.4)
# Game config entries are taggeddict/CustomMapType objects, not
# plain dict. Never use isinstance(x, dict) or str(proto) for a
# display name: str(proto) is the whole JSON-like record.
# ============================================================
def _clean_catalog_text(value):
    try:
        return ' '.join(str(value).replace('|', ' ').split())
    except Exception:
        return ''

def _contains_cjk(text):
    try:
        for ch in str(text):
            o = ord(ch)
            if ((0x3400 <= o <= 0x4DBF) or (0x4E00 <= o <= 0x9FFF) or
                (0xF900 <= o <= 0xFAFF) or (0x3040 <= o <= 0x30FF) or
                (0xAC00 <= o <= 0xD7AF)):
                return True
    except Exception:
        pass
    return False

def _is_english_text(text):
    try:
        text = _clean_catalog_text(text)
        return bool(text) and not _contains_cjk(text) and any(
            ('A' <= ch <= 'Z') or ('a' <= ch <= 'z') for ch in text)
    except Exception:
        return False

# ============================================================
# RUNTIME NAME TRANSLATOR (v4.7)
# ============================================================
# The client ships NO localized skin names: gun_skin_template_data
# rows carry a hardcoded CJK 'skin_name' literal, gclient.lang has no
# *SKIN*/*GUN* keys at all, and lobby_item_data lookups come back
# empty on vc163. So the only way to show English is to translate
# the strings ourselves at load time.
#
# This is a CLOSED vocabulary: 1,172 distinct name strings in the live
# catalog are built from exactly 545 distinct CJK/ASCII segments, so
# a segment dictionary gives 100%% coverage with no MT at runtime.
# Segment order matters: longest match wins, so compounds such as
# 'HANK指挥战车' beats the shorter pieces inside it.
#
# Overrides: drop nexora_names.json next to the game's files dir
# (or /sdcard/nexora_names.json) as {"CJK or full name": "English"}
# and it is merged over this table at startup - no rebuild needed.
_NAME_SEGMENTS = {
    '占位': 'Placeholder',
    '至臻': 'Zenith',
    '荣耀': 'Glory',
    '墨冰': 'Inkfrost',
    '地狱犬': 'Cerberus',
    '熔岩': 'Lava',
    '嗜血狂徒': 'Bloodthirsty',
    '宿命钟摆': 'Doom Pendulum',
    '毒液': 'Venom',
    '鬼面冥具': 'Ghostface Shroud',
    '暗潮': 'Undertow',
    '失落世界': 'Lost World',
    '占位测试': 'Placeholder Test',
    '末磐': 'Last Bastion',
    '盘盘': 'Panpan',
    '落日余晖': 'Afterglow',
    '黎明': 'Dawn',
    '东万联动占位': 'Tokyo Revengers Crossover Placeholder',
    '至高天': 'Empyrean',
    '绿龙': 'Green Dragon',
    '苍穹': 'Firmament',
    '龙与地下城': 'Dungeons & Dragons',
    '深渊': 'Abyss',
    '复合弓': 'Compound Bow',
    '寂灭': 'Nirvana',
    '血晶': 'Blood Crystal',
    '探索者': 'Explorer',
    '电子凤凰': 'Cyber Phoenix',
    '七大罪占位': 'Seven Deadly Sins Placeholder',
    '太空死灵': 'Space Necron',
    '子弹计数': 'Bullet Counter',
    '幽海梦蓝': 'Abyssal Dream Blue',
    '终末': 'The End',
    '世界杯': 'World Cup',
    '死神占位': 'Reaper Placeholder',
    '虚空龙': 'Void Dragon',
    '蝴蝶刀': 'Butterfly Knife',
    '逐星': 'Star Chaser',
    '量子矩阵': 'Quantum Matrix',
    '黑金': 'Black Gold',
    '低级': 'Low Grade',
    '功勋战士': 'Merited Warrior',
    '噩梦缠绕': 'Nightmare Coil',
    '天锁斩月': 'Heavenly Chain Zangetsu',
    '御灵炽空': 'Spirit Warden Blaze Sky',
    '德鲁伊占位': 'Druid Placeholder',
    '暗夜紫魅': 'Nightshade Violet',
    '毒液4占位': 'Venom 4 Placeholder',
    '深海之触': 'Touch of the Deep',
    '炽岩之心': 'Heart of Molten Rock',
    '电子恶魔': 'Cyber Demon',
    '碧霄龙霆': 'Azure Dragon Thunder',
    '空间宝石': 'Space Gem',
    '赤蝎蚀烬': 'Crimson Scorpion Ember',
    '铱芒': 'Iridium Glow',
    '骸骨南瓜': 'Skeleton Pumpkin',
    'V7驾驶舱占位': 'V7 Cockpit Placeholder',
    '七大罪联动占位': 'Seven Deadly Sins Crossover Placeholder',
    '丛林探险': 'Jungle Expedition',
    '云烟缥缈': 'Drifting Mist',
    '亡灵占位': 'Undead Placeholder',
    '亡灵节': 'Day of the Dead',
    '光夜双生': 'Twin of Light and Night',
    '几何分色': 'Geometric Color Split',
    '双刀': 'Twin Blades',
    '嘻哈死神': 'Hip-Hop Reaper',
    '圣骑': 'Paladin',
    '圣骸遗枪': 'Sacred Relic Lance',
    '基础款': 'Basic',
    '天工墨甲': 'Heavenly Ink Armor',
    '巫妖王占位': 'Lich King Placeholder',
    '幽冥使者': 'Nether Envoy',
    '幽灵船': 'Ghost Ship',
    '斩魄刀': 'Zanpakuto',
    '无尽空刃': 'Endless Void Blade',
    '旧日低语': 'Whispers of the Old Days',
    '普罗米修斯占位': 'Prometheus Placeholder',
    '暗夜凶兽': 'Night Beast',
    '月光之城': 'City of Moonlight',
    '朽木露琪亚': 'Rukia Kuchiki',
    '棱晶': 'Prism',
    '欢乐祝福': 'Joyful Blessing',
    '武士刀': 'Katana',
    '死星占位': 'Death Star Placeholder',
    '毒液3占位': 'Venom 3 Placeholder',
    '水族馆': 'Aquarium',
    '炼狱伤痕': 'Purgatory Scar',
    '电锯枪占位': 'Chainsaw Gun Placeholder',
    '硬质化结晶': 'Hardened Crystal',
    '碎影': 'Shattered Shadow',
    '科技鹰球星占位': 'Tech Eagle Star Placeholder',
    '紫霄神机': 'Violet Sky Divine Engine',
    '繁星': 'Starfield',
    '红龙': 'Red Dragon',
    '蝮蛇': 'Viper',
    '豹纹': 'Leopard',
    '量子镀层': 'Quantum Plating',
    '雕花': 'Engraved',
    '高级枪身': 'Advanced Body',
    'EMT新': 'EMT New',
    '丈八蛇矛占位': 'Zhangba Serpent Spear Placeholder',
    '低级枪身+低级机瞄': 'Low Grade Body + Low Grade Sight',
    '低阶+检视': 'Low Tier + Inspect',
    '堕落之触': 'Touch of Corruption',
    '多边形': 'Polygon',
    '天启之器': 'Instrument of Apocalypse',
    '天堂': 'Paradise',
    '恶灵骑士': 'Ghost Rider',
    '摇滚': 'Rock',
    '星防巨炮': 'Star Defense Cannon',
    '樱花': 'Sakura',
    '橙味风暴': 'Orange Storm',
    '海神占位': 'Poseidon Placeholder',
    '涂鸦': 'Graffiti',
    '潮汐': 'Tide',
    '燃烧军团': 'Burning Legion',
    '神思测算': 'Mind Reading',
    '科技钓鱼': 'Tech Fishing',
    '立体机动占位': 'Omni-Directional Mobility Placeholder',
    '红黑自发光': 'Red-Black Glow',
    '网络骇客': 'Netrunner',
    '至臻款': 'Zenith Edition',
    '萨满占位': 'Shaman Placeholder',
    '虎纹': 'Tiger',
    '警戒线': 'Cordon Line',
    '量子蜂巢': 'Quantum Hive',
    '镰刀': 'Scythe',
    '闪爆': 'Flash Burst',
    '雷霆万钧': 'Thunderclap',
    '霓虹': 'Neon',
    '霸气外露': 'Domineering',
    '青黛': 'Indigo',
    '马头': 'Horsehead',
    '高级机瞄+击杀计数': 'Advanced Sight + Kill Counter',
    '高级检视': 'Advanced Inspect',
    '鬼影迷踪': 'Phantom Trace',
    '鹰翼': 'Eagle Wing',
    '黑客帝国': 'The Matrix',
    '龙卷': 'Tornado',
    'DJ调音占位': 'DJ Tuning Placeholder',
    '世界杯占位': 'World Cup Placeholder',
    '丛林游侠': 'Jungle Ranger',
    '九尾焚天': 'Nine-Tail Skyburn',
    '云境': 'Cloud Realm',
    '亡灵绽放': 'Undead Bloom',
    '伊丽莎白': 'Elizabeth',
    '低配版外观': 'Low-Spec Appearance',
    '低阶': 'Low Tier',
    '僵尸血怒': 'Zombie Blood Rage',
    '光剑': 'Lightsaber',
    '光辉': 'Radiance',
    '兽之巨人': 'Beast Titan',
    '击杀特效': 'Kill Effect',
    '加速门': 'Boost Gate',
    '占位Blast': 'Placeholder Blast',
    '双龙': 'Twin Dragons',
    '周年庆': 'Anniversary',
    '圣裁': 'Divine Verdict',
    '地狱使者': 'Hell Envoy',
    '埃及占位': 'Egypt Placeholder',
    '埼玉': 'Saitama',
    '夜袭': 'Night Raid',
    '天穹神临': 'Divine Descent',
    '奇点': 'Singularity',
    '奇珍异兽': 'Rare Beast',
    '小丑': 'Joker',
    '巨人联动占位': 'Titan Crossover Placeholder',
    '废墟': 'Ruins',
    '怒火': 'Wrath',
    '惊吓盒': 'Jack-in-the-Box',
    '拳刃': 'Fist Blade',
    '放射性': 'Radioactive',
    '斩月红': 'Zangetsu Red',
    '斩月蓝': 'Zangetsu Blue',
    '无敌的mikey': 'Invincible Mikey',
    '无检视': 'No Inspect',
    '日式风情': 'Japanese Style',
    '时蚀棱镜': 'Time-Eaten Prism',
    '明月终裁': 'Moonlight Verdict',
    '春日花语': 'Spring Blossom',
    '暗月契约': 'Dark Moon Pact',
    '暗焰幽魂': 'Dark Flame Wraith',
    '月蚀': 'Eclipse',
    '未来科技': 'Future Tech',
    '杰诺斯': 'Genos',
    '松野千冬': 'Matsuno Chifuyu',
    '松野千冬双生': 'Matsuno Chifuyu Twin',
    '梦幻泡影': 'Illusory Bubble',
    '检视动画': 'Inspect Animation',
    '武士道': 'Bushido',
    '毁灭协议': 'Doom Protocol',
    '毒液2占位': 'Venom 2 Placeholder',
    '毒液占位': 'Venom Placeholder',
    '永昼行者': 'Everday Walker',
    '流炎狐迹': 'Flowing Flame Fox Trace',
    '浮金守护': 'Gilded Guardian',
    '火': 'Fire',
    '灰狂之蛇': 'Grey Mad Serpent',
    '灵狐': 'Spirit Fox',
    '炽焰之心': 'Heart of Blaze',
    '热力冲击': 'Heat Impact',
    '焚心绽放': 'Burning Heart Bloom',
    '爪刀': 'Karambit',
    '特殊机瞄': 'Special Sight',
    '猛兽': 'Beast',
    '猩红古堡': 'Crimson Castle',
    '玄冰青影': 'Dark Ice Azure Shadow',
    '球员联动投影': 'Player Crossover Projection',
    '电弧苦无': 'Arc Kunai',
    '电玩': 'Arcade',
    '白': 'White',
    '白狼': 'White Wolf',
    '终尾巨人': 'Founding Titan',
    '绝域圣剑': 'Forbidden Holy Sword',
    '绝域幻影': 'Forbidden Phantom',
    '绯红风暴': 'Crimson Storm',
    '肉': 'Meat',
    '能源核心': 'Energy Core',
    '腐息': 'Rot Breath',
    '自然之力': 'Force of Nature',
    '致命色彩': 'Lethal Colors',
    '苍炎': 'Pale Flame',
    '苍穹神骥': 'Firmament Steed',
    '荣誉勋章': 'Medal of Honor',
    '蔚蓝潮颂': 'Azure Tide Hymn',
    '螺旋千刃': 'Spiral Thousand Blades',
    '袖白雪': 'Sode no Shirayuki',
    '赏金猎人': 'Bounty Hunter',
    '赤色审判': 'Crimson Judgment',
    '迅疾': 'Swift',
    '邪恶魔神族': 'Evil Demon Clan',
    '银红': 'Silver Red',
    '阿斯加德': 'Asgard',
    '雄狮': 'Lion',
    '雪花': 'Snowflake',
    '雷电核心': 'Lightning Core',
    '霜蝎掠袭': 'Frost Scorpion Raid',
    '青冥': 'Azure Void',
    '骨': 'Bone',
    '骨噬': 'Bone Devour',
    '高级款': 'Advanced Edition',
    '高阶': 'High Tier',
    '鲜血部落': 'Blood Tribe',
    '鲨鱼季': 'Shark Season',
    '黄金': 'Gold',
    '黑': 'Black',
    '3倍镜': '3x Scope',
    'DJ手雷占位': 'DJ Grenade Placeholder',
    'EVA占位8号机': 'EVA Unit-08 Placeholder',
    'EVA占位Mark06': 'EVA Mark.06 Placeholder',
    'EVA占位初号机': 'EVA Unit-01 Placeholder',
    'EVA占位明日香': 'EVA Asuka Placeholder',
    'EVA占位绫波丽': 'EVA Rei Placeholder',
    'EVA占位零号机': 'EVA Unit-00 Placeholder',
    'HANK指挥战车': 'HANK Command Vehicle',
    'P90占位': 'P90 Placeholder',
    'bouncingcat占位': 'Bouncingcat Placeholder',
    'emtmega射线': 'EMT Mega Ray',
    'eva占位初号机v7': 'EVA Unit-01 V7 Placeholder',
    '一拳联动占位': 'One Punch Crossover Placeholder',
    '万象裁断': 'Manifest Severance',
    '丈八蛇矛': 'Zhangba Serpent Spear',
    '丈八蛇矛野牛': 'Zhangba Serpent Spear Bison',
    '九尾天狐': 'Nine-Tail Celestial Fox',
    '低级有BC': 'Low Grade + BC',
    '低级枪身': 'Low Grade Body',
    '低级检视': 'Low Grade Inspect',
    '低配': 'Low Spec',
    '低阶+计数器': 'Low Tier + Counter',
    '低阶模型': 'Low Tier Model',
    '低阶模型+子弹计数': 'Low Tier Model + Bullet Counter',
    '佐野万次郎': 'Sano Manjiro',
    '侵蚀': 'Erosion',
    '信念之战': 'Battle of Faith',
    '修罗': 'Shura',
    '僵尸召唤': 'Zombie Summon',
    '僵尸巨拳': 'Zombie Giant Fist',
    '僵尸污染': 'Zombie Contamination',
    '僵尸蓄力大跳': 'Zombie Charged Leap',
    '僵尸酸雾': 'Zombie Acid Mist',
    '光': 'Light',
    '兔子特工队占位': 'Bunny Task Force Placeholder',
    '兵长': 'Captain',
    '冬日秘境': 'Winter Wonderland',
    '冰': 'Ice',
    '冰晶利刃': 'Ice Crystal Blade',
    '冰火交响曲': 'Symphony of Ice and Fire',
    '冰雪节冰墙': 'Winter Festival Ice Wall',
    '凤羽': 'Phoenix Feather',
    '凤翔天舞': 'Phoenix Soaring Dance',
    '击中效果': 'Hit Effect',
    '击杀技术+高级机瞄': 'Kill Tech + Advanced Sight',
    '击杀播报': 'Kill Feed',
    '击杀计数': 'Kill Counter',
    '分裂炸弹': 'Splinter Bomb',
    '初代副总长': 'First-Gen Deputy Chief',
    '利威尔占位': 'Levi Placeholder',
    '卍解': 'Bankai',
    '单手斧': 'One-Handed Axe',
    '南瓜娃娃占位': 'Pumpkin Doll Placeholder',
    '南瓜恶灵': 'Pumpkin Wraith',
    '南瓜爆破者': 'Pumpkin Bomber',
    '占位Kraken': 'Placeholder Kraken',
    '占位MegaBlast': 'Placeholder MegaBlast',
    '占位MegaEthan': 'Placeholder MegaEthan',
    '占位MegaKainda': 'Placeholder MegaKainda',
    '占位MegaNOVA': 'Placeholder MegaNOVA',
    '占位MegaNacho': 'Placeholder MegaNacho',
    '占位MegaRAN': 'Placeholder MegaRAN',
    '占位MegaVolt': 'Placeholder MegaVolt',
    '占位MegaZERO': 'Placeholder MegaZERO',
    '卡皮巴拉占位': 'Capybara Placeholder',
    '印象迷宫': 'Impression Maze',
    '双生hank占位': 'Twin HANK Placeholder',
    '古堡惊魂': 'Castle Horror',
    '吞金兽占位': 'Gold-Eater Placeholder',
    '哥特图腾复活': 'Gothic Totem Revival',
    '哥特复活图腾': 'Gothic Revival Totem',
    '哥特扫描': 'Gothic Scan',
    '喜庆龙吟': 'Festive Dragon Roar',
    '噬魂利爪': 'Soul-Devouring Claw',
    '土': 'Earth',
    '圣冕': 'Sacred Crown',
    '圣堂': 'Sanctum',
    '圣诞': 'Christmas',
    '圣诞列车': 'Christmas Train',
    '地狱边缘': 'Edge of Hell',
    '塔奇克马': 'Tachikoma',
    '墨西哥占位': 'Mexico Placeholder',
    '夏日逐浪': 'Summer Wavechase',
    '大剑': 'Greatsword',
    '大和': 'Yamato',
    '大头EMMA占位': 'Big-Head EMMA Placeholder',
    '太空战舰': 'Space Battleship',
    '失落灾厄': 'Lost Calamity',
    '夺金狂潮': 'Gold Rush',
    '女巨人': 'Female Titan',
    '妖刀般若': 'Demon Blade Hannya',
    '嫉妒之罪': 'Sin of Envy',
    '封印状态': 'Sealed State',
    '尼泊尔军刀': 'Nepalese Kukri',
    '巨人联动': 'Titan Crossover',
    '巨剑': 'Giant Sword',
    '巴西': 'Brazil',
    '常暗之棺': 'Coffin of Eternal Darkness',
    '幻码獠牙': 'Phantom Code Fang',
    '幻象，传送JOKER': 'Illusion, Teleport JOKER',
    '幻面魅影': 'Phantom Mask',
    '幽冥使者占位': 'Nether Envoy Placeholder',
    '幽冥行者': 'Nether Walker',
    '幽械之喉': 'Throat of the Phantom Gun',
    '弹容量计数': 'Magazine Counter',
    '影武者': 'Shadow Warrior',
    '影面刺客': 'Shadow Assassin',
    '怠惰之罪': 'Sin of Sloth',
    '恩佐联动占位': 'Enzo Crossover Placeholder',
    '悖论逆转': 'Paradox Reversal',
    '战场': 'Battlefield',
    '手里剑': 'Shuriken',
    '执妄空花': 'Delusion Blossom',
    '技能1': 'Skill 1',
    '技能2': 'Skill 2',
    '技能3': 'Skill 3',
    '拖鞋': 'Slipper',
    '拳套': 'Knuckles',
    '指向': 'Pointing',
    '换弹动画': 'Reload Animation',
    '换弹变色': 'Reload Color Shift',
    '摔跤手Psycho占位': 'Wrestler Psycho Placeholder',
    '支援领域': 'Support Field',
    '放射狂潮': 'Radiation Surge',
    '斩月': 'Zangetsu',
    '旋枢启明': 'Pivot Dawn',
    '无子弹计数': 'No Bullet Counter',
    '无尽': 'Endless',
    '无证骑士': 'Unlicensed Rider',
    '无间狱火': 'Ceaseless Hellfire',
    '时间守护者': 'Time Keeper',
    '星云巨像': 'Nebula Colossus',
    '星座': 'Constellation',
    '星河圣歌': 'Galaxy Hymn',
    '星辰陨落': 'Falling Stars',
    '显卡': 'Graphics Card',
    '普攻': 'Normal Attack',
    '普罗米修斯': 'Prometheus',
    '暗夜男爵': 'Night Baron',
    '曳光弹': 'Tracer',
    '月夜男爵': 'Moonlit Baron',
    '月影断罪': 'Moon Shadow Conviction',
    '有子弹计数': 'Bullet Counter',
    '朗基努斯枪': 'Spear of Longinus',
    '木乃伊': 'Mummy',
    '木棍人占位': 'Stickman Placeholder',
    '未元物质': 'Unformed Matter',
    '未来幻影': 'Future Phantom',
    '机甲': 'Mech',
    '极寒之刃': 'Blade of Extreme Cold',
    '枪口火焰': 'Muzzle Flash',
    '核爆': 'Nuclear Blast',
    '核聚变': 'Nuclear Fusion',
    '检视': 'Inspect',
    '棱刃极锋': 'Prism Edge Apex',
    '棱彩幻境': 'Prismatic Illusion',
    '死亡宣告': 'Death Sentence',
    '毁灭阴影': 'Shadow of Ruin',
    '水晶破坏者': 'Crystal Breaker',
    '治疗手雷': 'Healing Grenade',
    '泳池BP': 'Pool BP',
    '浅海轻唱': 'Shallow Sea Serenade',
    '浪人': 'Ronin',
    '浪花朵朵': 'Dancing Waves',
    '浮游炮': 'Drone Cannon',
    '涂鸦手雷': 'Graffiti Grenade',
    '深渊骑士': 'Abyss Knight',
    '渊海裂锋': 'Abyssal Rift Edge',
    '湍流': 'Turbulence',
    '湮灭利爪': 'Annihilation Claw',
    '滞喧': 'Stagnant Roar',
    '激情回响': 'Passion Echo',
    '火箭滑铲': 'Rocket Slide',
    '灾厄收割者': 'Calamity Reaper',
    '炉芯融解': 'Core Meltdown',
    '炫彩': 'Dazzling',
    '炽星猎手': 'Blazing Star Hunter',
    '炽羽涅槃': 'Blazing Wing Rebirth',
    '烈火精神': 'Flame Spirit',
    '热狗枪': 'Hot Dog Gun',
    '焚天之刃': 'Sky-Burning Blade',
    '焰灵蛇舞': 'Flame Spirit Serpent Dance',
    '牛仔': 'Cowboy',
    '狂吼占位': 'Howling Placeholder',
    '狂欢终结者': 'Carnival Terminator',
    '狂沙侵袭': 'Sandstorm Assault',
    '狗占位': 'Dog Placeholder',
    '狮心王': 'Lionheart King',
    '猩红收割者': 'Crimson Reaper',
    '猫猫': 'Kitty',
    '玉面玲珑': 'Jade Elegance',
    '球星卡': 'Star Card',
    '电子恶魔至臻': 'Cyber Demon Zenith',
    '电子恶龙': 'Cyber Wyvern',
    '电玩时代': 'Arcade Era',
    '电锯': 'Chainsaw',
    '白金': 'Platinum',
    '白银': 'Silver',
    '皓月凌空': 'Bright Moon Aloft',
    '相位裂解': 'Phase Fracture',
    '碧海怨灵': 'Emerald Sea Wraith',
    '神圣裁决者': 'Holy Adjudicator',
    '神斧利塔': 'Divine Axe Rita',
    '福瑞': 'Furry',
    '糟糕的未来': 'Terrible Future',
    '紫晶蔷薇': 'Amethyst Rose',
    '紫瑶': 'Violet Jade',
    '紫电波': 'Violet Lightning Wave',
    '红蜘蛛': 'Red Spider',
    '纪元浪潮': 'Epoch Tide',
    '纸板枪AK47': 'Cardboard AK47',
    '织田信长': 'Oda Nobunaga',
    '绝域秘刃': 'Forbidden Secret Blade',
    '绿辉': 'Green Glow',
    '绿铜': 'Green Bronze',
    '胧浪铁潮': 'Hazy Wave Iron Tide',
    '脉冲': 'Pulse',
    '苍穹神骥占位': 'Firmament Steed Placeholder',
    '苍翠尖晶': 'Verdant Spinel',
    '苍雷': 'Pale Thunder',
    '荣光': 'Glory',
    '荣耀迭代占位': 'Glory Iteration Placeholder',
    '荧光机械': 'Fluorescent Machine',
    '荧光机甲': 'Fluorescent Mech',
    '葡萄牙': 'Portugal',
    '蓄力拳': 'Charged Punch',
    '蓝白自发光': 'Blue-White Glow',
    '蕉皮能量': 'Banana Peel Energy',
    '虚空吞噬者': 'Void Devourer',
    '蛇面魍魉': 'Serpent-Faced Demon',
    '蜂女': 'Wasp Woman',
    '血晶占位': 'Blood Crystal Placeholder',
    '血晶大剑': 'Blood Crystal Greatsword',
    '血晶拳刃': 'Blood Crystal Fist Blade',
    '血晶稳定剂': 'Blood Crystal Stabilizer',
    '裁决定论': 'Verdict Determinism',
    '解锁配件': 'Unlock Attachment',
    '贪婪之罪': 'Sin of Greed',
    '赛博': 'Cyber',
    '赠送表情+迷彩': 'Bonus Emote + Camo',
    '赤夜叉': 'Crimson Yaksha',
    '赤晶': 'Crimson Crystal',
    '超大巨人': 'Colossal Titan',
    '超新星': 'Supernova',
    '超硬质刀': 'Ultra-Hard Blade',
    '超载脉冲': 'Overload Pulse',
    '超音速引擎': 'Supersonic Engine',
    '超频': 'Overclock',
    '超频律动': 'Overclock Rhythm',
    '跳舞达人': 'Dance Master',
    '躲猫猫技能': 'Hide and Seek Skill',
    '辉绿秘境': 'Radiant Emerald Realm',
    '进击的巨人': 'Attack on Titan',
    '追猎占位': 'Pursuit Placeholder',
    '重生之道': 'Path of Rebirth',
    '重金属': 'Heavy Metal',
    '量子风暴': 'Quantum Storm',
    '鎏金占位': 'Gilded Placeholder',
    '钞票手枪': 'Money Pistol',
    '钢铁合剂': 'Steel Potion',
    '铁血猎手': 'Iron Blood Hunter',
    '银液': 'Silver Liquid',
    '银蓝': 'Silver Blue',
    '银蛇': 'Silver Serpent',
    '链刃': 'Chain Blade',
    '锦绣龙舞': 'Splendid Dragon Dance',
    '镀罪者': 'Sin Plater',
    '长剑': 'Longsword',
    '长枪': 'Spear',
    '防护领域': 'Protection Field',
    '阿根廷': 'Argentina',
    '雷': 'Thunder',
    '雷枪': 'Lightning Spear',
    '雷霆': 'Thunderous',
    '雷鸣破晓': 'Thunder Dawn',
    '霜烬轮回': 'Frost Ember Cycle',
    '霜雪冰锋': 'Frost Snow Ice Edge',
    '青面獠牙': 'Green Faced Fangs',
    '面具斗士': 'Masked Fighter',
    '饿狼': 'Hungry Wolf',
    '骇面枪客': 'Terror Mask Gunner',
    '骑士精神': 'Chivalry',
    '高级': 'Advanced',
    '高级外观+特殊机瞄': 'Advanced Appearance + Special Sight',
    '高级机瞄': 'Advanced Sight',
    '高级枪身+检视': 'Advanced Body + Inspect',
    '高阶模型': 'High Tier Model',
    '鬼面将军': 'Ghost General',
    '鬼魅缠身': 'Haunted',
    '魔法少女': 'Magical Girl',
    '鲨鱼': 'Shark',
    '鲨鱼玩偶占位': 'Shark Plush Placeholder',
    '黑暗力量': 'Dark Power',
    '黑曜': 'Obsidian',
    '黯然终章': 'Dim Finale',
    '龙宫寺坚': 'Ryuguji Ken',
    '龙怒': 'Dragon Wrath',
    '龙焰南瓜': 'Dragon Flame Pumpkin',
}


# ---- Researched official weapon-skin names (v2.19) -----------------------
# Official Blood Strike releases provide the English display names.  Direct
# bilingual release pairs are preferred; later official-English matches stay
# scoped to their exact weapon/source label.  No skin IDs, ordering, levels,
# ownership, or selection state are changed by this display-only table.
_OFFICIAL_WEAPON_SKIN_NAMES = {('AK47', 'EVA占位明日香'): 'Asuka',
 ('AK47', '宿命钟摆'): 'Pendulum of Fate',
 ('AK47', '恶灵骑士'): 'Hellride',
 ('AK47', '明日香'): 'Asuka',
 ('AK47', '昼夜同辉'): 'Chiaroscuro',
 ('AK47', '未元物质'): 'Dark Matter',
 ('AK47', '硬质化之力'): 'Power of Hardening',
 ('AK47', '神斧利塔'): 'Sacred Axe Rhitta',
 ('AK47', '虚空'): 'Void',
 ('AK47', '超载脉冲'): 'Overload',
 ('AR97', 'EVA Mark06'): 'EVA Mk.06',
 ('AR97', 'EVA占位Mark06'): 'EVA Mk.06',
 ('AR97', '升华'): 'Ascendant',
 ('AR97', '地狱犬'): 'Hellhound',
 ('AR97', '奇珍异兽'): 'Mythical Beast',
 ('AR97', '星河圣歌'): 'Starry Hymn',
 ('AR97', '浮金守护'): 'Gilded',
 ('AR97', '量子矩阵'): 'Quantum Grid',
 ('AUG', 'EVA占位绫波丽'): 'Rei',
 ('AUG', '宿命钟摆'): 'Pendulum of Fate',
 ('AUG', '末磐'): 'Requiem',
 ('AUG', '流炎狐迹'): 'Flame Fox',
 ('AUG', '湍流'): 'Riptide',
 ('AUG', '破晓'): 'Sunburst',
 ('AUG', '绫波丽'): 'Rei',
 ('AUG', '蕉皮能量'): 'Peel Power',
 ('AUG', '金阁雷鸣'): 'Aureate',
 ('AUG', '青黛'): 'Lapis Lazuli',
 ('BIZON', '灰狂之蛇'): 'The Mad Serpent of Ash',
 ('BIZON', '神思测算'): 'Mind Calculation',
 ('BIZON', '铜头蛇'): 'Copperhead',
 ('BUTTERFLY KNIFE', '合成波'): 'Synthwave',
 ('BUTTERFLY KNIFE', '死星'): 'Deathstar',
 ('BUTTERFLY KNIFE', '死星占位'): 'Deathstar',
 ('DAGGER', '永劫'): 'Perdition',
 ('DESERT EAGLE', '福狮'): 'Fortune Lion',
 ('DESERT EAGLE', '网络骇客'): 'Hacker',
 ('DUAL BLADES', '霜烬轮回'): 'Frozen Rebirth',
 ('FAL', '兽之巨人'): 'Beast Titan',
 ('FAL', '功勋战士'): 'warrior',
 ('FAL', '摔跤手'): 'Luchador',
 ('FAL', '暗潮'): 'Undercurrent',
 ('FAL', '荣耀杯'): 'Glory Cup',
 ('FAL', '进化天龙'): 'Evolved Draco',
 ('FAL', '青黛'): 'Lapis Lazuli',
 ('FIST BLADE', '湮灭利爪'): 'Claw of Oblivion',
 ('GALIL', '地狱犬'): 'Hellhound',
 ('GALIL', '暗月契约'): 'Reaper',
 ('GALIL', '枯萎之拥'): "Blight's Embrace",
 ('GALIL', '腐息'): 'Noxdra',
 ('GALIL', '量子矩阵'): 'Quantum Grid',
 ('GALIL', '霜狼啸'): 'Frosthowl',
 ('GALIL', '霜狼嚎'): 'Frosthowl',
 ('GALIL', '骑士'): 'Knight',
 ('GLOCK', '钞票手枪'): 'Money Shot',
 ('INP-9', '暗夜凶兽'): 'Vicious Beast',
 ('INP-9', '炽岩之心'): 'Molten Core',
 ('INP-9', '电玩时代'): 'Arcade Era',
 ('INP-9', '金色挽歌'): 'Golden Elegy',
 ('INP-9', '龙怒'): 'Dragon Wrath',
 ('KAG-6', '兽之巨人'): 'Beast Titan',
 ('KAG-6', '悖论逆转'): 'Matrix',
 ('KAG-6', '指挥官'): 'Comandante',
 ('KAG-6', '科技钓鱼'): 'Tech Angler',
 ('KAG-6', '终尾巨人'): 'Doomsday Titan',
 ('KAG-6', '闪爆'): 'Dynamite',
 ('KAG-6', '鬼面冥具'): 'Specterstrike',
 ('KAR98K', '冰川'): 'Glacier',
 ('KAR98K', '双弓哈里特'): 'Double Bow Harlit',
 ('KAR98K', '地狱犬'): 'Hellhound',
 ('KAR98K', '灵狐'): 'Fox',
 ('KAR98K', '炽星猎手'): 'Star Hunter',
 ('KAR98K', '紫宝石'): 'Amethyst',
 ('KAR98K', '绝域幻影'): 'Netherflame',
 ('KATANA', '地狱战争'): 'Infernal War',
 ('KATANA', '重生之道'): 'The Path of Rebirth',
 ('KUKRI', '棱刃极锋'): 'Levi',
 ('LONGSWORD', '绝域秘刃'): 'Voidedge',
 ('M1887', '地狱犬'): 'Hellhound',
 ('M1887', '恐惧束缚'): 'Dreadbind',
 ('M1887', '毁灭者'): 'Destroyer',
 ('M1887', '碎影'): 'Phantomrift',
 ('M1887', '绝域幻影'): 'Netherflame Phantom',
 ('M1887', '鬼面冥具'): 'Specterstrike',
 ('M4A1', '命运终焉'): 'Tiadraco',
 ('M4A1', '天启之器'): 'Apocalypse',
 ('M4A1', '恶魔'): 'Demon',
 ('M4A1', '暗夜凶兽'): 'Vicious Beast',
 ('M4A1', '暮光'): 'Twilight',
 ('M4A1', '皇家'): 'Royal',
 ('M4A1', '碧海怨灵'): 'Sea Wraith',
 ('M4A1', '超大型巨人'): 'Colossus Titan',
 ('M4A1', '钢铁革命'): 'Ironsurgency',
 ('M4A1', '锦绣龙舞'): 'Dragon Dance',
 ('M4A1', '饿狼'): 'Garou',
 ('M4A1', '龙与地下城'): 'Tiadraco',
 ('M700', '圣裁'): 'Seraph',
 ('M700', '术士'): 'Warlock',
 ('M700', '焰灵蛇舞'): 'Boitatá',
 ('M700', '铜头蛇'): 'Copperhead',
 ('M700', '雷枪'): 'Thunder Gun',
 ('M700', '雷霆万钧'): 'Power Surge',
 ('M82', '初代副总长'): 'The First Generation Vice-President',
 ('M82', '天锁斩月'): 'Tensa Zangetsu',
 ('M82', '放射性'): 'Fallux',
 ('M82', '骸骨南瓜'): 'Pumpknight',
 ('MCX', 'EVA占位零号机'): 'EVA-00',
 ('MCX', 'EVA零号机'): 'EVA-00',
 ('MP5', 'EVA初号机'): 'EVA-01',
 ('MP5', 'EVA占位初号机'): 'EVA-01',
 ('MP5', '嗜血狂徒'): 'Blood Vengeance',
 ('MP5', '埼玉'): 'Saitama Vanguard Edition',
 ('MP5', '奇珍异兽'): 'Mythical Beast',
 ('MP5', '守卫'): 'Guard',
 ('MP5', '毁灭协议'): 'Cataclysm',
 ('MP5', '流畅'): 'Sleek',
 ('MP5', '潮汐'): 'Rising Tide',
 ('MP5', '热浪'): 'Heatwave',
 ('MP5', '白霞罚'): 'Hakka no Togame',
 ('MP5', '血晶裂影'): 'Bloodrift',
 ('MP5', '黯然终章'): 'Dominator',
 ('MP7', '松野千冬双生'): 'Keisuke Baji × Chifuyu Matsuno',
 ('MP7', '碧霄龙霆'): 'JadeTempest',
 ('MP7', '蔚蓝潮颂'): 'Tidesong',
 ('MP7', '鬼面冥具'): 'Specterstrike',
 ('ONE-HANDED AXE', '暴风雪'): 'Snowstorm',
 ('ORIGIN-12', '南瓜爆破者'): 'Jack Blaster',
 ('ORIGIN-12', '放射性'): 'Fallux',
 ('ORIGIN-12', '组织核心'): 'Playmaker',
 ('P90', '大师'): 'Maestro',
 ('P90', '天圣界'): 'Elysian',
 ('P90', '獠牙南瓜'): 'Fang Pumpkin',
 ('P90', '碎影'): 'Phantomrift',
 ('P90', '至高天'): 'Empyrean',
 ('P90', '霓虹碎片'): 'Neon Shard',
 ('PKM', '暗潮'): 'Undercurrent',
 ('PKM', '黑钢'): 'Black Steel',
 ('QBZ95', 'EVA初号机'): 'EVA-01',
 ('QBZ95', 'EVA占位初号机'): 'EVA-01',
 ('QBZ95', '旧日低语'): 'Whisper',
 ('QBZ95', '毒液'): 'Venom',
 ('QBZ95', '白霞罚'): 'Hakka no Togame',
 ('QBZ95', '穿透者'): 'Penetrator',
 ('RPK', '朱红寂静'): 'Vermilion Silence',
 ('RPK', '繁花'): 'Flourish',
 ('SCAR', 'EVA8号机'): 'EVA-08',
 ('SCAR', 'EVA占位8号机'): 'EVA-08',
 ('SCAR', '冰川'): 'Glacier',
 ('SCAR', '星骸悲鸣'): 'Stellar',
 ('SCAR', '朱红烈焰'): 'Scarlet Inferno',
 ('SCAR', '霜冻'): 'Frostbite',
 ('SCAR', '霜雪冰封'): 'Frostbound',
 ('SCAR', '青穹极光'): 'Frostbeam',
 ('SCAR', '魔面剑豪'): 'Demonblade',
 ('SCYTHE', '灾厄收割者'): 'Harvester',
 ('SCYTHE', '狂沙侵袭'): 'Sandstorm',
 ('SHURIKEN', '苍雷'): 'AZURE THUNDER',
 ('SKS', '天堂'): 'Elysium',
 ('SKS', '无证骑士'): 'Mumen Rider',
 ('SKS', '黎明'): 'Sunrise',
 ('SPEAR', '冰川'): 'Glacier',
 ('SPEAR', '冻结'): 'Freeze',
 ('SPEAR', '圣骸遗枪'): 'Relic',
 ('SPEAR', '宿命钟摆'): 'Pendulum of Fate',
 ('SPEAR', '铱芒'): 'Iridian',
 ('SPEAR', '龙卷'): 'Terrible Tornado',
 ('SVD', '功勋战士'): 'Warrior of Merit',
 ('SVD', '地狱犬'): 'Hellhound',
 ('SVD', '宿命钟摆'): 'Pendulum of Fate',
 ('THOMPSON', '不插电'): 'Unplugged',
 ('UMP45', '兔子特工队'): 'Bunny Ops',
 ('UMP45', '兔子特工队占位'): 'Bunny Ops',
 ('UMP45', '宿命钟摆'): 'Pendulum of Fate',
 ('UMP45', '时间守护者'): 'Infinite',
 ('UMP45', '遗弃者'): 'Forsaken',
 ('UMP45', '量子镀层'): 'QuantumShell',
 ('UMP45', '飞升'): 'Ascension',
 ('URB', '修罗'): 'Asura',
 ('URB', '古堡历险'): 'Castle Adventure',
 ('URB', '幻蝰之影'): 'Evolved Viper',
 ('URB', '灵狐'): 'Fox',
 ('URB', '紫宝石'): 'Amethyst',
 ('UZI', '嗜血狂徒'): 'Blood Vengeance',
 ('UZI', '毁灭协议'): 'Cataclysm',
 ('UZI', '赤蝎蚀烬'): 'Scorpius',
 ('UZI', '逐星'): 'Star Chaser',
 ('VAL', '圣诞'): 'Holiday',
 ('VAL', '埃及艳后'): 'Cleopatra',
 ('VAL', '樱粉'): 'Sakura Pink',
 ('VECTOR', '暗夜紫魅'): 'Violet Wraith',
 ('VECTOR', '曲速霓虹'): 'Warp Neon',
 ('VECTOR', '极性'): 'Polarity',
 ('VECTOR', '流炎狐迹'): 'Flame Fox',
 ('VECTOR', '虚空龙影'): 'Shadowdrake',
 ('VECTOR', '邪能侵袭'): 'Demonwrath',
 ('VSS', '宿命钟摆'): 'Pendulum of Fate',
 ('VSS', '影武者'): 'Ghost Blade'}

_OFFICIAL_SKIN_NAMES = {'修罗': 'Asura',
 '兽之巨人': 'Beast Titan',
 '南瓜爆破者': 'Jack Blaster',
 '命运终焉': 'Tiadraco',
 '嗜血狂徒': 'Blood Vengeance',
 '圣裁': 'Seraph',
 '地狱犬': 'Hellhound',
 '天圣界': 'Elysian',
 '奇珍异兽': 'Mythical Beast',
 '宿命钟摆': 'Pendulum of Fate',
 '幻蝰之影': 'Evolved Viper',
 '影武者': 'Ghost Blade',
 '悖论逆转': 'Matrix',
 '放射性': 'Fallux',
 '旧日低语': 'Whisper',
 '时间守护者': 'Infinite',
 '星骸悲鸣': 'Stellar',
 '昼夜同辉': 'Chiaroscuro',
 '暗夜紫魅': 'Violet Wraith',
 '暗月契约': 'Reaper',
 '暗潮': 'Undercurrent',
 '曲速霓虹': 'Warp Neon',
 '末磐': 'Requiem',
 '朱红烈焰': 'Scarlet Inferno',
 '棱刃极锋': 'Levi',
 '樱粉': 'Sakura Pink',
 '毁灭协议': 'Cataclysm',
 '毒液': 'Venom',
 '浮金守护': 'Gilded',
 '湮灭利爪': 'Claw of Oblivion',
 '灾厄收割者': 'Harvester',
 '炽岩之心': 'Molten Core',
 '炽星猎手': 'Star Hunter',
 '狂沙侵袭': 'Sandstorm',
 '电玩时代': 'Arcade Era',
 '破晓': 'Sunburst',
 '硬质化之力': 'Power of Hardening',
 '碎影': 'Phantomrift',
 '紫宝石': 'Amethyst',
 '腐息': 'Noxdra',
 '至高天': 'Empyrean',
 '苍雷': 'AZURE THUNDER',
 '虚空龙影': 'Shadowdrake',
 '血晶裂影': 'Bloodrift',
 '赤蝎蚀烬': 'Scorpius',
 '超大型巨人': 'Colossus Titan',
 '超载脉冲': 'Overload',
 '进化天龙': 'Evolved Draco',
 '逐星': 'Star Chaser',
 '邪能侵袭': 'Demonwrath',
 '量子矩阵': 'Quantum Grid',
 '金阁雷鸣': 'Aureate',
 '钢铁革命': 'Ironsurgency',
 '铱芒': 'Iridian',
 '闪爆': 'Dynamite',
 '雷枪': 'Thunder Gun',
 '雷霆万钧': 'Power Surge',
 '霜烬轮回': 'Frozen Rebirth',
 '霜雪冰封': 'Frostbound',
 '青穹极光': 'Frostbeam',
 '骑士': 'Knight',
 '骸骨南瓜': 'Pumpknight',
 '鬼面冥具': 'Specterstrike',
 '魔面剑豪': 'Demonblade',
 '黑钢': 'Black Steel',
 '黯然终章': 'Dominator',
 '龙与地下城': 'Tiadraco',
 '龙怒': 'Dragon Wrath'}

# Generic values are direct bilingual matches only.  Weapon-specific entries
# remain separate so labels such as 绝域幻影 and 功勋战士 cannot cross-apply.
_NAME_SEGMENTS.update(_OFFICIAL_SKIN_NAMES)


def _official_name_key(value):
    text = str(value or '').strip()
    for dash in ('\u2013', '\u2014', '\u2212', '\uff0d'):
        text = text.replace(dash, '-')
    return re.sub(r'\s+', '', text).casefold()


# Canonical complete labels and aliases for names that an earlier paint/lang
# pass may already have translated literally.  Weapon aliases are always
# scoped; source-only aliases come only from unambiguous direct matches.
_OFFICIAL_EXACT_NAMES = {}
_OFFICIAL_WEAPON_SOURCE_ORDER = []
for (_official_weapon, _official_source), _official_name in sorted(
        _OFFICIAL_WEAPON_SKIN_NAMES.items(),
        key=lambda item: (len(item[0][1]), len(item[0][0])),
        reverse=True):
    _canonical = _official_weapon + ' \u2013 ' + _official_name
    _OFFICIAL_EXACT_NAMES[_official_name_key(
        _official_weapon + '-' + _official_source)] = _canonical
    _literal = _NAME_SEGMENTS.get(_official_source)
    # _NAME_SEGMENTS was updated above, so recover the prior literal only when
    # it differs from the official value through the explicit legacy table
    # installed just below.  The replacement itself is used for partial names.
    _OFFICIAL_WEAPON_SOURCE_ORDER.append(
        (_official_weapon, _official_source, _official_name))

# Preserve the pre-override literals as alias inputs; these are never emitted
# as the final answer when an official match exists.
_OFFICIAL_LEGACY_LITERALS = {
 'EVA占位8号机': 'EVA Unit-08 Placeholder',
 'EVA占位Mark06': 'EVA Mark.06 Placeholder',
 'EVA占位初号机': 'EVA Unit-01 Placeholder',
 'EVA占位明日香': 'EVA Asuka Placeholder',
 'EVA占位绫波丽': 'EVA Rei Placeholder',
 'EVA占位零号机': 'EVA Unit-00 Placeholder',
 '修罗': 'Shura',
 '兔子特工队占位': 'Bunny Task Force Placeholder',
 '初代副总长': 'First-Gen Deputy Chief',
 '功勋战士': 'Merited Warrior',
 '南瓜爆破者': 'Pumpkin Bomber',
 '嗜血狂徒': 'Bloodthirsty',
 '圣裁': 'Divine Verdict',
 '圣诞': 'Christmas',
 '圣骸遗枪': 'Sacred Relic Lance',
 '地狱犬': 'Cerberus',
 '埼玉': 'Saitama',
 '天启之器': 'Instrument of Apocalypse',
 '天堂': 'Paradise',
 '天锁斩月': 'Heavenly Chain Zangetsu',
 '奇珍异兽': 'Rare Beast',
 '宿命钟摆': 'Doom Pendulum',
 '影武者': 'Shadow Warrior',
 '恶灵骑士': 'Ghost Rider',
 '悖论逆转': 'Paradox Reversal',
 '放射性': 'Radioactive',
 '无证骑士': 'Unlicensed Rider',
 '旧日低语': 'Whispers of the Old Days',
 '时间守护者': 'Time Keeper',
 '星河圣歌': 'Galaxy Hymn',
 '暗夜凶兽': 'Night Beast',
 '暗夜紫魅': 'Nightshade Violet',
 '暗月契约': 'Dark Moon Pact',
 '暗潮': 'Undertow',
 '未元物质': 'Unformed Matter',
 '末磐': 'Last Bastion',
 '松野千冬双生': 'Matsuno Chifuyu Twin',
 '棱刃极锋': 'Prism Edge Apex',
 '死星占位': 'Death Star Placeholder',
 '毁灭协议': 'Doom Protocol',
 '流炎狐迹': 'Flowing Flame Fox Trace',
 '浮金守护': 'Gilded Guardian',
 '湍流': 'Turbulence',
 '湮灭利爪': 'Annihilation Claw',
 '潮汐': 'Tide',
 '灰狂之蛇': 'Grey Mad Serpent',
 '灵狐': 'Spirit Fox',
 '灾厄收割者': 'Calamity Reaper',
 '炽岩之心': 'Heart of Molten Rock',
 '炽星猎手': 'Blazing Star Hunter',
 '焰灵蛇舞': 'Flame Spirit Serpent Dance',
 '狂沙侵袭': 'Sandstorm Assault',
 '碎影': 'Shattered Shadow',
 '碧海怨灵': 'Emerald Sea Wraith',
 '碧霄龙霆': 'Azure Dragon Thunder',
 '神思测算': 'Mind Reading',
 '神斧利塔': 'Divine Axe Rita',
 '科技钓鱼': 'Tech Fishing',
 '终尾巨人': 'Founding Titan',
 '绝域幻影': 'Forbidden Phantom',
 '绝域秘刃': 'Forbidden Secret Blade',
 '网络骇客': 'Netrunner',
 '腐息': 'Rot Breath',
 '苍雷': 'Pale Thunder',
 '蔚蓝潮颂': 'Azure Tide Hymn',
 '蕉皮能量': 'Banana Peel Energy',
 '赤蝎蚀烬': 'Crimson Scorpion Ember',
 '超载脉冲': 'Overload Pulse',
 '重生之道': 'Path of Rebirth',
 '量子矩阵': 'Quantum Matrix',
 '量子镀层': 'Quantum Plating',
 '钞票手枪': 'Money Pistol',
 '铱芒': 'Iridium Glow',
 '锦绣龙舞': 'Splendid Dragon Dance',
 '闪爆': 'Flash Burst',
 '雷枪': 'Lightning Spear',
 '雷霆万钧': 'Thunderclap',
 '霜烬轮回': 'Frost Ember Cycle',
 '青黛': 'Indigo',
 '饿狼': 'Hungry Wolf',
 '骸骨南瓜': 'Skeleton Pumpkin',
 '鬼面冥具': 'Ghostface Shroud',
 '黎明': 'Dawn',
 '黯然终章': 'Dim Finale',
 '龙与地下城': 'Dungeons & Dragons',
 '龙卷': 'Tornado'}

for (_official_weapon, _official_source), _official_name in (
        _OFFICIAL_WEAPON_SKIN_NAMES.items()):
    _literal = _OFFICIAL_LEGACY_LITERALS.get(_official_source)
    if _literal and _literal != _official_name:
        _OFFICIAL_EXACT_NAMES[_official_name_key(
            _official_weapon + '-' + _literal)] = (
                _official_weapon + ' \u2013 ' + _official_name)
for _official_source, _official_name in _OFFICIAL_SKIN_NAMES.items():
    _OFFICIAL_EXACT_NAMES.setdefault(
        _official_name_key(_official_source), _official_name)
    _literal = _OFFICIAL_LEGACY_LITERALS.get(_official_source)
    if _literal and _literal != _official_name:
        _OFFICIAL_EXACT_NAMES.setdefault(
            _official_name_key(_literal), _official_name)


def _official_exact_name(raw):
    return _OFFICIAL_EXACT_NAMES.get(_official_name_key(raw), '')


def _official_replace_weapon_source(raw):
    # Partial labels may carry LVn or another authentic suffix.  Replace only
    # the exact source span for the matching weapon, then let the normal layout
    # preserving translator finish the remainder.
    folded = str(raw or '').casefold()
    for weapon, source, official in _OFFICIAL_WEAPON_SOURCE_ORDER:
        if source in raw and weapon.casefold() in folded:
            raw = raw.replace(source, official)
            folded = raw.casefold()
    return raw

_NAME_SEGMENT_MAX = max(len(_k) for _k in _NAME_SEGMENTS)
_NAME_PARTS = re.compile(r'([()\uff08\uff09]|[\s\u3000]+|[-\u2013\u2014])')
_NAME_CJK_CHARS = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]')
_name_translate_stats = [0, 0]          # [translated, untouched]
_name_overrides_loaded = [0]
_name_unresolved_chars = set()


def _name_scan_segments(part):
    """Longest-match over the segment table; only matches spans that
    actually contain CJK so pure-ASCII runs are never eaten."""
    out = []
    i = 0
    n = len(part)
    while i < n:
        hit = None
        upper = min(_NAME_SEGMENT_MAX, n - i)
        for length in range(upper, 0, -1):
            cand = part[i:i + length]
            if cand in _NAME_SEGMENTS and _NAME_CJK_CHARS.search(cand):
                hit = cand
                break
        if hit is not None:
            out.append(_NAME_SEGMENTS[hit])
            i += len(hit)
            continue
        ch = part[i]
        if _NAME_CJK_CHARS.match(ch):
            _name_unresolved_chars.add(ch)
        out.append(ch)
        i += 1
    return ''.join(out)


def _name_translate_part(part):
    if not _NAME_CJK_CHARS.search(part):
        return part
    whole = _NAME_SEGMENTS.get(part.strip())
    if whole is not None:
        return whole
    if '+' in part:
        return ' + '.join(
            _name_scan_segments(sub) if _NAME_CJK_CHARS.search(sub) else sub
            for sub in part.split('+'))
    return _name_scan_segments(part)


def translate_name(text, fallback=None):
    """CJK skin/weapon name -> English, preserving the game's own layout
    ('WEAPON - SKIN (note) LVn'). Returns ASCII-safe text only; never a raw
    numeric id (callers pass fallback for that)."""
    try:
        if text is None:
            return fallback if fallback is not None else ''
        raw = _display_text(text, '')
        if not raw:
            return fallback if fallback is not None else ''
        official = _official_exact_name(raw)
        if official:
            _name_translate_stats[0] += 1
            return official
        raw = _official_replace_weapon_source(raw)
        if not _contains_cjk(raw):
            return raw
        whole = _NAME_SEGMENTS.get(raw.strip())
        if whole is not None:
            _name_translate_stats[0] += 1
            return whole
        pieces = []
        for piece in _NAME_PARTS.split(raw):
            if not piece:
                continue
            pieces.append(piece if not _NAME_CJK_CHARS.search(piece)
                          else _name_translate_part(piece))
        out = ''.join(pieces)
        out = out.replace('\uff08', '(').replace('\uff09', ')').replace('\uff0c', ',')
        out = ' '.join(out.split())
        if _contains_cjk(out):
            # Could not fully resolve: never leak CJK or an id to the menu.
            _name_translate_stats[1] += 1
            return fallback if fallback is not None else ''
        _name_translate_stats[0] += 1
        return out
    except Exception:
        return fallback if fallback is not None else ''


def _name_load_overrides():
    """Merge an optional JSON name table over the built-in segments."""
    global _NAME_SEGMENT_MAX
    loaded = 0
    paths = []
    try:
        paths.append('/sdcard/nexora_names.json')
    except Exception:
        pass
    try:
        import os as _os
        paths.append(_os.path.join(_os.getcwd(), 'nexora_names.json'))
    except Exception:
        pass
    for path in paths:
        try:
            import json as _json
            with open(path, 'r', encoding='utf-8') as fh:
                table = _json.load(fh)
        except Exception:
            continue
        if not isinstance(table, dict):
            continue
        try:
            add = 0
            for key, value in table.items():
                if not key or not isinstance(value, str) or not value.strip():
                    continue
                _NAME_SEGMENTS[str(key)] = value.strip()
                add += 1
            loaded += add
            _plog('[NAME] overrides %s entries=%d' % (path, add))
        except Exception:
            continue
    if loaded:
        _NAME_SEGMENT_MAX = max(len(_k) for _k in _NAME_SEGMENTS)
    return loaded

def _display_text(value, fallback='', _depth=0):
    if value is None or _depth > 3:
        return fallback
    if isinstance(value, bytes):
        try:
            value = value.decode('utf-8', 'replace')
        except Exception:
            return fallback
    if isinstance(value, str):
        text = _clean_catalog_text(value)
        return text if text else fallback
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        first_text = ''
        for item in value:
            text = _display_text(item, '', _depth + 1)
            if text and not _contains_cjk(text):
                return text
            if text and not first_text:
                first_text = text
        return first_text if first_text else fallback
    # Mapping/taggeddict/localization record: extract a real text field;
    # never stringify the whole record.
    for key in ('en', 'en_US', 'en-US', 'English', 'english',
                'name', 'text', 'value', 'zh', 'zh_CN', 'cn'):
        nested = _proto_get(value, key, None)
        if nested is not None:
            text = _display_text(nested, '', _depth + 1)
            if text:
                return text
    first_text = ''
    for _k, nested in _data_items(value)[:80]:
        text = _display_text(nested, '', _depth + 1)
        if text and not _contains_cjk(text):
            return text
        if text and not first_text:
            first_text = text
    return first_text if first_text else fallback

def _proto_display_name(proto, keys, fallback=''):
    for key in keys:
        text = _display_text(_proto_get(proto, key, None), '')
        if text:
            return text
    return fallback


# ---- English catalog names (v2.5) ------------------------------------
# Some gun-template `skin_name` fields are the Chinese design/source
# name. The display name the global client shows normally lives on the
# matching lobby item proto (handled in the catalog builder). As a
# first pass, also ask the game's own gclient.lang / string-message
# tables to translate a plain CJK source string. Every lookup is
# optional and cached; failure leaves the original text untouched.
_lang_module = None
_lang_module_checked = False
_lang_pair_map = None
_lang_text_cache = {}

def _collect_proto_strings(value, out, _depth=0):
    if _depth > 3 or len(out) >= 24:
        return
    if isinstance(value, bytes):
        try:
            value = value.decode('utf-8', 'replace')
        except Exception:
            return
    if isinstance(value, str):
        text = _clean_catalog_text(value)
        if text:
            out.append(text)
        return
    if isinstance(value, (list, tuple)):
        for item in value[:24]:
            _collect_proto_strings(item, out, _depth + 1)
        return
    for _k, nested in _data_items(value)[:32]:
        _collect_proto_strings(nested, out, _depth + 1)


def _build_lang_pair_map():
    global _lang_pair_map
    if _lang_pair_map is not None:
        return _lang_pair_map
    pairs = {}
    for module_name in (
        'gclient.data.string_message_data',
        'gclient.data.text_message_data',
    ):
        try:
            mod = _import_module(module_name)
            # _import_module is defined below this helper; by call time the
            # whole payload has executed, so the global exists. During the
            # first catalog build it also exists because this helper is
            # only invoked from build code further down.
            for _key, record in _data_items(getattr(mod, 'data', None)):
                strings = []
                _collect_proto_strings(record, strings)
                cjk = [x for x in strings if _contains_cjk(x)]
                eng = [x for x in strings if _is_english_text(x)]
                if len(cjk) == 1 and eng:
                    pairs.setdefault(cjk[0], eng[0])
        except Exception:
            pass
    _lang_pair_map = pairs
    return pairs

def _lang_translate(text):
    global _lang_module, _lang_module_checked
    text = _clean_catalog_text(text)
    if not text or not _contains_cjk(text):
        return text
    if text in _lang_text_cache:
        return _lang_text_cache[text]
    result = ''
    try:
        if not _lang_module_checked:
            _lang_module_checked = True
            try:
                _lang_module = _import_module('gclient.lang')
            except Exception:
                _lang_module = None
            if _lang_module is None:
                for _lm_name in ('gclient.data.lang_data',
                                 'gclient.data.text_data',
                                 'gclient.data.i18n_data',
                                 'gclient.lang_data'):
                    try:
                        _lang_module = _import_module(_lm_name)
                        if _lang_module is not None:
                            break
                    except Exception:
                        _lang_module = None
        mod = _lang_module
        if mod is not None:
            for attr in ('data', 'strings', 'string_dict', 'lang_dict',
                         'text_dict', 'translations', 'en', 'en_US', 'english'):
                try:
                    table = getattr(mod, attr, None)
                    val = _proto_get(table, text, None) if table is not None else None
                    val = _display_text(val, '')
                    if _is_english_text(val):
                        result = val
                        break
                except Exception:
                    pass
            if not result:
                for fn_name in ('gettext', 'GetText', 'get_text', 'translate',
                                'Translate', 'GetLangText', 'get_lang_text',
                                'GetString', 'get_string', 'LoadString', '_'):
                    try:
                        fn = getattr(mod, fn_name, None)
                        if not callable(fn):
                            continue
                        val = _display_text(fn(text), '')
                        if _is_english_text(val) and val != text:
                            result = val
                            break
                    except Exception:
                        pass
            if not result:
                try:
                    for _attr, table in list(vars(mod).items())[:200]:
                        try:
                            val = _display_text(_proto_get(table, text, None), '')
                        except Exception:
                            continue
                        if _is_english_text(val):
                            result = val
                            break
                except Exception:
                    pass
    except Exception:
        pass
    if not result:
        try:
            result = _build_lang_pair_map().get(text, '')
        except Exception:
            result = ''
    _lang_text_cache[text] = result
    return result

def _reset_lang_caches_if_empty():
    global _lang_pair_map
    try:
        if _lang_pair_map == {}:
            _lang_pair_map = None
        for _key in [k for k, v in list(_lang_text_cache.items()) if not v]:
            _lang_text_cache.pop(_key, None)
    except Exception:
        pass

def _english_display_text(value, fallback=''):
    text = _display_text(value, fallback)
    if _contains_cjk(text):
        translated = _lang_translate(text)
        if translated:
            return translated
    return text

def _proto_english_name(proto, keys, fallback=''):
    candidates = []
    for key in keys:
        text = _display_text(_proto_get(proto, key, None), '')
        if not text:
            continue
        if not _contains_cjk(text):
            return text
        candidates.append(text)
    for text in candidates:
        translated = _lang_translate(text)
        if translated:
            return translated
    return candidates[0] if candidates else fallback


PAINT_EN = {
    "一触即碎": "One-Touch Shatter",
    "七彩律动": "Rainbow Rhythm",
    "三色堇": "Pansy",
    "三角星尘": "Triangle Stardust",
    "丛林夜色": "Jungle Night",
    "乱序": "Disorder",
    "云洇": "Cloud Bleed",
    "云海泡影": "Cloudsea Mirage",
    "云海长空": "Cloudsea Horizon",
    "云涡": "Cloud Vortex",
    "云绚霞染": "Blushing Clouds",
    "云蔚": "Cloud Glow",
    "仙女座": "Andromeda",
    "仲夏夜之梦": "Midsummer Night's Dream",
    "仲夏梦影": "Midsummer Dream",
    "余晖": "Afterglow",
    "余白": "Negative Space",
    "信号撕裂": "Signal Tear",
    "像素天空": "Pixel Sky",
    "像素斑点": "Pixel Dots",
    "元素逸散": "Element Dissipation",
    "光影幻境": "Light & Shadow Mirage",
    "光澜": "Light Ripples",
    "冰壁": "Ice Wall",
    "冰川": "Glacier",
    "冰晶": "Ice Crystal",
    "冰析": "Crystallization",
    "冰蓝晶脉": "Ice-Blue Veins",
    "冰蓝蜜桃": "Icy Blue Peach",
    "冰镇特调": "On the Rocks",
    "冰镜流银": "Ice Mirror Silver",
    "凤翎华彩": "Phoenix Plume",
    "刀光剑影": "Blade Gleam",
    "初春": "Early Spring",
    "刮白": "Scraped White",
    "剧毒弥漫": "Toxic Haze",
    "勿忘草": "Forget-Me-Not",
    "北极光": "Northern Lights",
    "印象派": "Impressionist",
    "危险地带": "Danger Zone",
    "厚彩颂歌": "Ode to Color",
    "叠阈": "Layered Threshold",
    "叶纹": "Leaf Grain",
    "啸焰吞宙": "Roaring Flames",
    "土黄": "Earth Yellow",
    "圣辉琉璃": "Holy Radiance Glass",
    "坚壁": "Bastion",
    "墨影溅金": "Ink Splash Gold",
    "墨染": "Ink-Dyed",
    "墨染朱砂": "Ink & Cinnabar",
    "墨染金辉": "Ink & Gold",
    "墨玫": "Ink Rose",
    "墨纹": "Ink Grain",
    "复古紫": "Retro Purple",
    "复古花布": "Retro Floral",
    "夏日印象": "Summer Impression",
    "夕照": "Sunset Glow",
    "多彩飞溅": "Color Splash",
    "夜凌": "Night's Edge",
    "夜幕": "Nightfall",
    "夜漩星语": "Starry Night Vortex",
    "夜空星尘": "Night-Sky Stardust",
    "夜蓝": "Night Blue",
    "夜魅": "Night Charm",
    "大洋猎手": "Ocean Hunter",
    "大漠丛云": "Desert Clouds",
    "大理石": "Marble",
    "大马士革": "Damascus",
    "天地涟漪": "World Ripples",
    "天幕奇韵": "Sky Canopy",
    "天蓝": "Sky Blue",
    "天际线": "Skyline",
    "天青": "Azure",
    "天靛": "Indigo Sky",
    "天鹅绒": "Velvet",
    "太阳风暴": "Solar Storm",
    "奶牛": "Cow Print",
    "孤岛": "Lone Island",
    "宇宙": "Cosmos",
    "寂纹": "Silent Grain",
    "寒霜": "Frostbite",
    "寰宇": "Universe",
    "尘埃": "Dust",
    "山染": "Mountain Dye",
    "山水": "Landscape",
    "岩痕": "Rock Traces",
    "帝王黑金": "Imperial Black-Gold",
    "幻变猎手": "Phantom Hunter",
    "幻夜霓虹": "Neon Phantom Night",
    "幻彩云裳": "Iridescent Clouds",
    "幻彩流苏": "Iridescent Tassels",
    "幻彩涟漪": "Iridescent Ripples",
    "幻彩炫舞": "Iridescent Dance",
    "幻影叠浪": "Phantom Surge",
    "幻梦": "Dreamland",
    "幻波": "Dream Waves",
    "幻海": "Sea of Illusion",
    "幻渏": "Dreamy Ripples",
    "幻色": "Phantom Hues",
    "幻谱": "Phantom Spectrum",
    "幻金紫影": "Gold-Purple Phantom",
    "幽叶": "Shadow Leaf",
    "幽域": "Shadow Realm",
    "幽影": "Dark Shadow",
    "幽河星砂": "Shadow River Stardust",
    "幽海冰花": "Abyssal Ice Bloom",
    "幽渊": "Abyss",
    "幽紫": "Deep Violet",
    "幽蓝冰川": "Dark-Blue Glacier",
    "库斯特鸡尾酒": "Kuster Cocktail",
    "异星幽谷": "Alien Valley",
    "彩云": "Spectrum Clouds",
    "彩云间": "Among the Clouds",
    "彩墙": "Painted Wall",
    "彩影梦澜": "Color Dream Ripples",
    "彩瓷": "Porcelain",
    "彩窗": "Stained Glass",
    "彩立方": "Color Cubes",
    "彩笔": "Crayon",
    "彩绸飞扬": "Flying Ribbons",
    "彩辉琉璃": "Radiant Glass",
    "彩霞": "Rosy Dawn",
    "彩霞映辉": "Dawn Radiance",
    "影格": "Shadow Grid",
    "影碎岚光": "Shattered Mountain Light",
    "微风": "Breeze",
    "心怡": "Delight",
    "怒海狂涛": "Raging Seas",
    "怒火中烧": "Burning Rage",
    "恐怖之夜": "Night of Terror",
    "情欲猎手": "Desire Hunter",
    "战": "War",
    "战火": "Warfire",
    "扭曲": "Distortion",
    "折纸幻境": "Origami Wonderland",
    "折纸脉冲": "Origami Pulse",
    "折蓝": "Folded Blue",
    "拼图": "Jigsaw",
    "挤压": "Squeeze",
    "数据堡垒": "Data Fortress",
    "数码灰": "Digital Grey",
    "数码蓝": "Digital Blue",
    "斑斓": "Vivid",
    "斑斓幻境": "Vivid Wonderland",
    "斑虎": "Tiger Stripes",
    "斜虹掠影": "Slanting Rainbow",
    "断锋": "Broken Edge",
    "日冕": "Corona",
    "日出龙舌兰": "Tequila Sunrise",
    "旧香": "Old Perfume",
    "旭日": "Rising Sun",
    "旭日初升": "Daybreak",
    "明暗交织": "Chiaroscuro",
    "星幻": "Starlight Fantasy",
    "星映辰河": "Starlit River",
    "星沙": "Stardust Sand",
    "星河": "Galaxy",
    "星河琉璃": "Glass Galaxy",
    "星脉织空": "Star Veins",
    "星陨涟漪": "Meteor Ripples",
    "春意": "Spring",
    "春绘": "Spring Painting",
    "晚霞晕染": "Dusk Gradient",
    "晨光霞影": "Morning Glow",
    "晨曦": "First Light",
    "晴枝繁雪": "Snowy Branches",
    "晴空": "Clear Sky",
    "晴空流玉": "Clear-Sky Jade",
    "晴霞": "Sunny Dawn",
    "晶体": "Crystal",
    "晶划": "Crystal Streaks",
    "暖冷交织": "Warm & Cold",
    "暖流": "Warm Current",
    "暖锈": "Warm Rust",
    "暗流": "Undercurrent",
    "暗红涌动": "Dark Red Surge",
    "暮海": "Evening Sea",
    "暮色呢喃": "Dusk Whisper",
    "暮霁": "Clear Dusk",
    "月痕星涌": "Moonmark Surge",
    "月色": "Moonlight",
    "木纹": "Wood Grain",
    "朱砂玉脉": "Cinnabar Jade Veins",
    "朱砂金箔": "Cinnabar Gold Foil",
    "朱红": "Vermilion",
    "朱红烈焰": "Vermilion Blaze",
    "朱线": "Red Thread",
    "杏粉": "Apricot Pink",
    "杏雨青岚": "Apricot Rain",
    "松烟": "Pine Smoke",
    "松绿": "Pine Green",
    "板岩": "Slate",
    "极光": "Aurora",
    "极光垂幕": "Aurora Curtain",
    "极地": "Polar",
    "极地猎手": "Polar Hunter",
    "极夜繁星": "Polar Night Stars",
    "极速霓虹": "Speed Neon",
    "林地": "Woodland",
    "林深": "Deep Forest",
    "染迹": "Dye Traces",
    "柠檬": "Lemon",
    "格蓝": "Checkered Blue",
    "桃花": "Peach Blossom",
    "桔梗": "Bellflower",
    "梦境涂鸦": "Dream Graffiti",
    "梦幻彩虹": "Dream Rainbow",
    "梦幻星河": "Dreamy Galaxy",
    "梦樱": "Dream Sakura",
    "梦池": "Dream Pool",
    "梦涂": "Dream Paint",
    "梦漾彩韵": "Dreamy Hues",
    "森影叠棱": "Forest Shadows",
    "棱镜": "Prism",
    "棱镜迷踪": "Prism Maze",
    "楔乱": "Wedge Chaos",
    "模糊信号": "Blurred Signal",
    "橄榄绿": "Olive Green",
    "橘红": "Tangerine",
    "橙光": "Orange Glow",
    "橙瓣": "Orange Zest",
    "橙酒": "Orange Liqueur",
    "毛刺菱阵": "Burr Array",
    "水彩": "Watercolor",
    "水蓝": "Aqua Blue",
    "水蜜桃": "Honey Peach",
    "沁岚": "Refreshing Mist",
    "沙棕色": "Sand Brown",
    "沙砾": "Gravel",
    "沙色": "Sand",
    "沧浪冰焰": "Cold-Wave Fire",
    "沧溟云涛": "Vast Sea Clouds",
    "油彩飞旋": "Swirling Oil Paint",
    "波光粼粼": "Shimmering Waves",
    "波光银影": "Silver Waves",
    "波尔多红": "Bordeaux Red",
    "流云幻境": "Flowing Clouds",
    "流云星河": "Cloudy Galaxy",
    "流光扇韵": "Flowing Fan",
    "流光溢彩": "Radiant Flow",
    "流光溢火": "Flowing Fire",
    "流宴": "Flowing Feast",
    "流火夏日": "Blazing Summer",
    "流胶碧浪": "Jade Surge",
    "流萤蝶语": "Firefly Whispers",
    "流蓝紫光": "Blue-Violet Flow",
    "流行时尚": "Pop Fashion",
    "流金岁月": "Golden Years",
    "流驳": "Mottled Flow",
    "浅梦轻纱": "Sheer Dream",
    "浅海骄阳": "Shallow Sea Sun",
    "测试动态迷彩": "Test Camo (Dynamic)",
    "浓彩涂抹": "Thick Paint",
    "浩瀚": "Vast",
    "浩瀚霓虹": "Vast Neon",
    "浮光掠彩": "Floating Hues",
    "浮纹深蓝": "Deep-Blue Drift",
    "浮阳": "Drifting Sun",
    "海军蓝": "Navy Blue",
    "海底世界": "Underwater World",
    "海渚": "Sea Islets",
    "海草": "Seaweed",
    "海蓝微澜": "Sea-Blue Ripples",
    "海藻": "Kelp",
    "海韵": "Sea Rhyme",
    "涂鸦季": "Graffiti Season",
    "涡影": "Vortex Shadow",
    "淘金时代": "Gold Rush",
    "深海": "Deep Sea",
    "深海凝流": "Deep-Sea Current",
    "深空旅程": "Deep-Space Journey",
    "深蓝": "Deep Blue",
    "混沌交错": "Chaos Interlock",
    "湖底": "Lakebed",
    "湛蓝矩阵": "Azurite Matrix",
    "溅血": "Blood Spatter",
    "溪流": "Creek",
    "漩涡": "Whirlpool",
    "漾彩": "Rippling Hues",
    "潜光": "Submerged Light",
    "潮声幻影": "Tide Phantom",
    "潮汐漫沙": "Tidal Sands",
    "澄夏": "Clear Summer",
    "澄泓": "Clear Waters",
    "灰": "Grey",
    "灰影金辉": "Grey Shadow Gold",
    "灰烬": "Ashes",
    "灰绿幽谷": "Grey-Green Valley",
    "灰色": "Grey Shade",
    "灰韵": "Grey Charm",
    "灵纹": "Spirit Grain",
    "炙热": "Scorching",
    "炫夏": "Dazzling Summer",
    "炫彩幻境": "Dazzling Mirage",
    "炫彩星涡": "Dazzling Star Vortex",
    "炫彩飞舞": "Dazzling Flutter",
    "炫阳": "Blazing Sun",
    "炭黑": "Charcoal Black",
    "点阵": "Dot Matrix",
    "炽热岩魂": "Molten Rock Soul",
    "炽焰金辉": "Blazing Gold",
    "烁彩焕影": "Gleaming Hues",
    "烈火燎原": "Wildfire",
    "烈霞": "Blazing Dawn",
    "烟辞": "Smoke Verse",
    "烬漩": "Ember Vortex",
    "热带风暴": "Tropical Storm",
    "烽火狼烟": "Beacon Smoke",
    "焦糖": "Caramel",
    "焰旋": "Flame Spiral",
    "煌石": "Radiant Stone",
    "熊熊烈火": "Raging Flames",
    "熔核溯光": "Molten Core Light",
    "熔炉": "Furnace",
    "熔珀": "Molten Amber",
    "熔金光轨": "Molten Gold Trails",
    "熔金赤瓷": "Molten Gold Ceramic",
    "牛仔布": "Denim",
    "牡丹": "Peony",
    "狂想": "Rhapsody",
    "猩红": "Crimson",
    "玄纹": "Dark Grain",
    "玫瑰星云": "Rose Nebula",
    "玫瑰金": "Rose Gold",
    "环映": "Ringed Reflections",
    "珠光宝气": "Pearlescent",
    "琉璃幻星": "Glass Fantasy Stars",
    "琉璃星海": "Glass Star Sea",
    "琉璃梦境": "Glass Dreamscape",
    "琉茵": "Glazed Jade",
    "琥珀": "Amber",
    "琥珀金鳞": "Amber Gold Scales",
    "瑰丽夏日": "Magnificent Summer",
    "瑰丽流光": "Magnificent Flow",
    "璞玉蓝韵": "Uncut Jade Blue",
    "璧金": "Jade Gold",
    "甘露": "Sweet Dew",
    "电子恶魔专属": "E-Demon Exclusive",
    "电磁场": "Electromagnetic Field",
    "电群青": "Electric Ultramarine",
    "电路图": "Circuit Diagram",
    "电路板": "Circuit Board",
    "疾电涂鸦": "Lightning Graffiti",
    "白昼": "Daylight",
    "白色": "White",
    "百叶窗": "Venetian Blinds",
    "皇家焰纹": "Royal Flame",
    "皇家蓝": "Royal Blue",
    "盈绿": "Lush Green",
    "睡莲": "Water Lily",
    "瞬流虹轨": "Instant Rainbow Trail",
    "矩阵网络": "Matrix Network",
    "石板灰": "Slate Grey",
    "石纹": "Stone Grain",
    "石纹矩阵": "Stone Matrix",
    "破土": "Breaking Ground",
    "破碎之潮": "Shattered Tide",
    "硫磺地带": "Sulfur Zone",
    "碎层": "Fractured Layers",
    "碎斑": "Broken Spots",
    "碎织": "Woven Scraps",
    "碎金": "Gold Fragments",
    "碎雨斜痕": "Slanting Rain",
    "碧波": "Azure Waves",
    "碧波荡漾": "Rippling Azure",
    "碧海云翔": "Azure Sea Clouds",
    "碧海蓝天": "Azure Seas & Skies",
    "碧琉": "Azure Glass",
    "碧落星砂": "Azure Stardust",
    "碧蓝海域": "Azure Waters",
    "碧蓝涟漪": "Azure Ripples",
    "碾迹": "Roller Traces",
    "秋色": "Autumn Hues",
    "积木": "Building Blocks",
    "空间裂隙": "Spatial Rift",
    "竹影": "Bamboo Shadows",
    "竹绿": "Bamboo Green",
    "笔触流影": "Brushstroke Flow",
    "粉彩": "Pastel",
    "粉砖": "Pink Brick",
    "粉红诱惑": "Pink Temptation",
    "粉色": "Pink",
    "粉蓝": "Powder Blue",
    "粉蔓": "Pink Vines",
    "粉裂晶尘": "Pink Crystal Dust",
    "粉霓": "Pink Neon",
    "粉露": "Pink Dew",
    "粉黛": "Rouge",
    "糖幻星漩": "Sugar Star Swirl",
    "糖果印象": "Candy Impression",
    "紫": "Purple",
    "紫丁香": "Lilac",
    "紫堇": "Deep Violet",
    "紫宝石": "Amethyst",
    "紫斑": "Purple Spots",
    "紫晶夺目": "Dazzling Amethyst",
    "紫暮": "Purple Dusk",
    "紫澜": "Purple Billows",
    "紫绀": "Violet-Blue",
    "紫绒": "Purple Velvet",
    "紫罗兰": "Violet",
    "紫罗兰雾": "Violet Mist",
    "紫色": "Purple Tone",
    "紫色幻梦": "Purple Dream",
    "紫蔓": "Purple Vines",
    "紫金": "Purple-Gold",
    "紫霞仙境": "Purple Fairyland",
    "紫韵流光": "Purple Flow",
    "紫韵流彩": "Purple Hues",
    "紫韵金辉": "Purple Gold Radiance",
    "红宝石": "Ruby",
    "红矮星": "Red Dwarf",
    "红绸魅影": "Red Silk Phantom",
    "红蓝韵律": "Red-Blue Rhythm",
    "红霭": "Red Haze",
    "纯金": "Pure Gold",
    "骑士精神": "Chivalry",
    "虚空吞噬者": "Void Devourer",
    "邪恶魔神族（七大罪占位）": "Demon God Clan (7DS Placeholder)",
    "电子恶魔至臻": "Cyber Demon Ultimate",
    "电子恶魔（高级检视）": "Cyber Demon (Advanced Inspect)",
    "电子恶魔（低配）": "Cyber Demon (Low-Spec)",
    "电子恶魔": "Cyber Demon",
    "纯银": "Pure Silver",
    "纸屑": "Confetti",
    "织彩": "Woven Colors",
    "织火燎原": "Woven Fire",
    "织纹": "Woven Texture",
    "绘梦": "Painted Dreams",
    "绚丽糖圈": "Splendid Candy Rings",
    "绚影": "Splendid Shadows",
    "绚烂华章": "Splendid Chapter",
    "绚蓝金羽": "Blue-Gold Plumes",
    "绣花": "Embroidery",
    "绮梦云海": "Beautiful Cloudsea",
    "绮波流光": "Lovely Waves",
    "绮流": "Lovely Flow",
    "绮花": "Lovely Blossoms",
    "绯云": "Crimson Clouds",
    "绯夜": "Crimson Night",
    "绯斑": "Crimson Spots",
    "绯柔": "Crimson Softness",
    "绯红闪烁": "Crimson Glimmer",
    "绯羽霜痕": "Crimson Frost Plumes",
    "绯色雕卷": "Crimson Scrolls",
    "绯金华章": "Crimson-Gold Chapter",
    "绸海叠云": "Silk Sea Clouds",
    "绸缎浮金": "Floating Silk Gold",
    "绿宝石": "Emerald",
    "绿影游丝": "Green Silk Threads",
    "绿影琉璃": "Green Glass Shadows",
    "绿松石": "Turquoise",
    "绿洲": "Oasis",
    "绿码流光": "Green Code Flow",
    "绿野": "Green Fields",
    "绿野仙踪": "Emerald Wonderland",
    "编织": "Knitted",
    "缭绕": "Lingering Smoke",
    "网格": "Mesh",
    "罗氏鸡尾酒": "Luo's Cocktail",
    "群青": "Ultramarine",
    "羽化": "Feathering",
    "翠瑛": "Jadeite",
    "翠纹锦绣": "Jade Brocade",
    "翠雪": "Jade Snow",
    "翠馨": "Jade Fragrance",
    "翡翠沙歌": "Jade Sandsong",
    "翡翠金砂": "Jade Gold Sand",
    "肆意": "Unrestrained",
    "胭棠": "Rouge Crabapple",
    "胭脂": "Carmine",
    "致命幻觉": "Deadly Illusion",
    "致幻迷蕈": "Psychedelic Mushrooms",
    "花蔓": "Flower Vines",
    "花锦": "Floral Brocade",
    "苍松翠绿": "Pine Verdure",
    "苍蓝蔓影": "Verdant Blue Vines",
    "苏打": "Soda",
    "苔棱": "Moss Ridges",
    "苹果花": "Apple Blossom",
    "荧光冲击": "Fluorescent Impact",
    "荧光绿": "Fluorescent Green",
    "荧潮断层": "Fluorescent Fault",
    "荧绿点阵": "Neon Green Dots",
    "荧绿矩阵": "Neon Green Matrix",
    "萤石": "Fluorite",
    "落日": "Setting Sun",
    "葡萄": "Grape",
    "葡霜": "Grape Frost",
    "蓝": "Blue",
    "蓝叶": "Blue Leaves",
    "蓝宝石": "Sapphire",
    "蓝弦流光": "Blue String Flow",
    "蓝彩华章": "Blue Chapter",
    "蓝影浮丝": "Blue Floating Silk",
    "蓝木": "Blue Wood",
    "蓝柠": "Blue Lemon",
    "蓝洋红": "Blue-Magenta",
    "蓝海星云": "Blue Sea Nebula",
    "蓝海星辰": "Blue Sea Stars",
    "蓝海逐浪": "Chasing Blue Waves",
    "蓝漾星烁": "Blue Ripple Stars",
    "蓝翠": "Blue Jade",
    "蓝色": "Blue Tone",
    "蓝街": "Blue Street",
    "蓝闪": "Blue Flash",
    "蓝霜炽影": "Blue Frost Blaze",
    "蓝黄交响": "Blue-Yellow Symphony",
    "蔓越莓": "Cranberry",
    "蔚蓝沙海": "Azure Sandsea",
    "蔚蓝波光": "Azure Glimmer",
    "蔚霞": "Rosy Azure",
    "薄荷": "Mint",
    "薰衣草": "Lavender",
    "虚海悬星": "Void Sea Hanging Stars",
    "虹彩流光": "Iridescent Flow",
    "虹翎翩飞": "Fluttering Plumes",
    "虹隙": "Rainbow Gap",
    "蚀虹": "Eroded Rainbow",
    "蛇纹": "Serpentine",
    "蛛网": "Cobweb",
    "蜂巢": "Honeycomb",
    "蜜桃绸光": "Peach Silk",
    "蝶斓": "Butterfly Splendor",
    "蝶羽": "Butterfly Wings",
    "血影": "Blood Shadow",
    "血晕": "Blood Halo",
    "血脉琼华": "Blood Jade",
    "血色晶影": "Crimson Crystal Shadows",
    "血色涌动": "Blood Surge",
    "街头艺术": "Street Art",
    "装饰主义": "Art Deco",
    "解构": "Deconstruction",
    "警示橙": "Warning Orange",
    "调查意志": "Investigative Will",
    "调酒师": "Bartender",
    "象牙金曜": "Ivory Gold Sun",
    "赤叶流纹": "Red Leaf Streams",
    "赤晶若梦": "Red Crystal Dream",
    "赤曜": "Crimson Sun",
    "赤橙": "Red-Orange",
    "赤潮云涌": "Red Tide Clouds",
    "赤焰晶格": "Crimson Flame Lattice",
    "赤红": "Scarlet",
    "赤辉": "Scarlet Radiance",
    "赤金龙鳞": "Gold Dragon Scales",
    "赤锈": "Red Rust",
    "赤黑龙鳞": "Black Dragon Scales",
    "超越空间": "Beyond Space",
    "跃迁": "Quantum Leap",
    "运动": "Sport",
    "进化矩阵": "Evolution Matrix",
    "迷城": "Lost City",
    "迷宫": "Labyrinth",
    "迷幻": "Psychedelic",
    "迷雾": "Mist",
    "酸柠": "Sour Lemon",
    "酸橙": "Lime",
    "金日蓝天": "Golden Sun Blue Sky",
    "金晖墨影": "Golden Ink Shadows",
    "金枝玉影": "Golden Branches",
    "金波交辉": "Golden Waves",
    "金涟": "Golden Ripples",
    "金色荒原": "Golden Wasteland",
    "金蓝奇缘": "Gold-Blue Romance",
    "金蓝穹墨": "Gold-Blue Dome",
    "金虎": "Golden Tiger",
    "金钻": "Golden Diamond",
    "金霞紫影": "Golden Dawn Purple",
    "鎏金涡夜": "Gilded Night Vortex",
    "钢铁意志": "Iron Will",
    "钴锋碎晶": "Cobalt Shards",
    "铅笔画": "Pencil Sketch",
    "铜青": "Copper Verdigris",
    "银河绽裂": "Galaxy Split",
    "银波幻影": "Silver Wave Phantom",
    "银线星轨": "Silver Star Trails",
    "银钻": "Silver Diamond",
    "错综": "Intricate",
    "锯影": "Saw Shadows",
    "镍生恶物": "Nickel Fiend",
    "镭射": "Laser",
    "闪金": "Glitter Gold",
    "阳光海岸": "Sunny Coast",
    "阳澜": "Sun Waves",
    "阳蓝": "Sun Blue",
    "阵印": "Formation Seal",
    "雀羽": "Sparrow Plumes",
    "雅革": "Elegant Leather",
    "雨帘": "Rain Curtain",
    "雨露": "Rain & Dew",
    "雪崩": "Avalanche",
    "雷击风暴": "Thunderstorm",
    "雾漪": "Mist Ripples",
    "雾绡叠翠": "Misty Jade Layers",
    "雾色": "Misty Hue",
    "雾蓝": "Misty Blue",
    "霁色": "Clear-Sky Hue",
    "霓菌": "Neon Fungi",
    "霓虹地平线": "Neon Horizon",
    "霓虹梦境": "Neon Dreamscape",
    "霓虹沙暴": "Neon Sandstorm",
    "霓虹黄": "Neon Yellow",
    "霓裳幻彩": "Rainbow Robes",
    "霓锋": "Neon Edge",
    "霜钢蓝焰": "Frost-Steel Blue Flame",
    "霞光": "Dawn Glow",
    "霞光辉映": "Radiant Dawn",
    "霞光霓影": "Dawn Neon",
    "霞浪流金": "Golden Dawn Waves",
    "霞穹": "Dawn Dome",
    "青冥之浪": "Azure Abyss Waves",
    "青墨刃": "Ink-Blue Blade",
    "青墨记忆": "Ink-Blue Memories",
    "青岚雾影": "Verdant Mist",
    "青峰暮霭": "Green Peak Dusk",
    "青幔遮阳": "Verdant Canopy",
    "青影": "Verdant Shadow",
    "青玉": "Celadon",
    "青琉": "Celadon Glass",
    "青碧棱界": "Verdant Prism",
    "青翠波澜": "Verdant Billows",
    "青花碎瓷": "Blue-White Shards",
    "青苔": "Moss",
    "青苹果": "Green Apple",
    "青蓝": "Cyan",
    "青金黑曜": "Cyan-Gold Obsidian",
    "青黄蓝影": "Cyan-Yellow-Blue",
    "静谧深湖": "Tranquil Deep Lake",
    "靛影": "Indigo Shadow",
    "靛瓷": "Indigo Porcelain",
    "靛蓝": "Indigo",
    "音律狂潮": "Rhythm Storm",
    "风化灰蓝": "Weathered Grey-Blue",
    "风沙漫舞": "Dancing Sands",
    "风纹": "Wind Grain",
    "香槟微醺": "Tipsy Champagne",
    "马天尼": "Martini",
    "魔爪": "Monster",
    "鳞甲": "Scale Armor",
    "鸢尾": "Iris",
    "鹅卵石": "Cobblestone",
    "麹尘": "Pale Willow",
    "黄昏": "Dusk",
    "黄铜机甲": "Brass Mech",
    "黑曜鎏金裂": "Obsidian Gold Cracks",
    "黑曜银隙": "Obsidian Silver Gaps",
    "黑纹": "Black Grain",
    "黑金花": "Black Gold Flower",
    "黑钢": "Black Steel",
    "龙羽洒金": "Dragon Plume Gold",
}


def translate_paint(name):
    """v8.16: the 0100-family skins are '<Gun> - <CJK paint>' -
    644 distinct paints shared across every gun (27,684 rows on
    the v8.15 device, the whole CJK report). Translate through the
    embedded table; exact full-name fallback."""
    try:
        text = _display_text(name, '')
        if not text:
            return name
        if ' - ' in text:
            head, tail = text.split(' - ', 1)
            tr = PAINT_EN.get(tail.strip())
            if tr:
                return '%s - %s' % (head.strip(), tr)
        tr = PAINT_EN.get(text.strip())
        if tr:
            return tr
    except Exception:
        pass
    return name


