import os
import re
import json
import asyncio
import subprocess
import requests
import shutil
import static_ffmpeg

# FFmpeg setup
try:
    static_ffmpeg.add_paths()
except Exception as e:
    print("Static FFmpeg setup warning:", e)

FFMPEG_PATH = shutil.which("ffmpeg")
DENO_BIN = shutil.which("deno") or "/root/.deno/bin/deno"

from threading import Thread
from urllib.parse import quote, urlparse, parse_qs
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    BotCommand
)
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

import yt_dlp

# ============================================================
# CREATE & VERIFY COOKIES PATH
# ============================================================

COOKIES_ENV = os.environ.get("YOUTUBE_COOKIES")

if COOKIES_ENV:
    formatted_cookies = COOKIES_ENV.replace("\\n", "\n")
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(formatted_cookies)
    print("✅ cookies.txt file created successfully from Environment Variable!")

COOKIES_PATH = "/root/Tgbot/cookies.txt" if os.path.exists("/root/Tgbot/cookies.txt") else "cookies.txt"

# ============================================================
# FLASK WEB SERVER (KEEP ALIVE)
# ============================================================

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 6753546651))
FORCE_CHANNEL = "@mame_posts"
FORCE_CHANNEL_LINK = "https://t.me/mame_posts"

# ============================================================
# DATABASE MANAGEMENT
# ============================================================

DATA_FILE = "user_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Save Error:", e)

def record_user_activity(user_id):
    data = load_data()
    uid_str = str(user_id)
    if uid_str not in data:
        data[uid_str] = {"msg_count": 0, "started": True, "lang": None}
    data[uid_str]["msg_count"] = data[uid_str].get("msg_count", 0) + 1
    data[uid_str]["started"] = True
    save_data(data)

def set_user_language(user_id, lang_code):
    data = load_data()
    uid_str = str(user_id)
    if uid_str not in data:
        data[uid_str] = {"msg_count": 1, "started": True, "lang": lang_code}
    else:
        data[uid_str]["lang"] = lang_code
    save_data(data)

def get_user_language(user_id):
    data = load_data()
    return data.get(str(user_id), {}).get("lang", None)

def get_user_stats(user_id):
    data = load_data()
    uid_str = str(user_id)
    total_users = len(data)
    user_msg_count = data.get(uid_str, {}).get("msg_count", 0)
    return total_users, user_msg_count

# ============================================================
# TRANSLATIONS (AMHARIC, ENGLISH & ARABIC)
# ============================================================

TRANSLATIONS = {
    "am": {
        "btn_add": "ቦቱን ወደ ቻትዎ ለመጨመር",
        "btn_order": "ማስታወቂያ ለማሰራት",
        "btn_price": "Price | ዋጋ",
        "btn_payment": "Payment Method",
        "btn_status": "My Status & Stats",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "Support | ድጋፍ",
        "btn_back": "Back to Menu",
        "done_msg": "✅ <b>ተጠናቋል! ቋንቋዎ ተስተካክሏል።</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Loading|ይጠብቁ...</b>',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>ከቪዲዮ የተቀየረው (Extracted Audio)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Converted with</b> @{bot_username} & @mame_posts',
        "video_downloaded": '<tg-emoji emoji-id="530762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',
        "size_limit": "⚠️ <b>ቪዲዮው ከ 50MB በላይ ስለሆነ በቴሌግራም መላክ አይቻልም!</b>",
        "fail_download": "💔 <b> የፈለጉትን File ማግኘት አልቻልኩም!</b>\n\nእባክዎ የላኩት ሊንክ private አለመሆኑን አረጋግጠው እንደገና ይሞክሩ።",
        "photo_download": '📸 <b>Downloaded Thumbnail/Photo</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
        "welcome": (
            'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> '
            '<b>My options (ከሁሉም Social Media ላይ video, photo እና audio ማውረድና መቀየር ይችላሉ!) :</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee: videos & photos</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram: reels, photos & stories</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube: videos & music (Full & Shorts)</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X): videos & voice</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch, Vimeo & Others</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video to Audio Converter: ቪዲዮ ወደ ኦዲዮ መቀየር ይችላሉ! </b>\n\n'
            '<b>And others Social Media | ሌሎችንም ሶሻል ሚድያ ማውረድ ይችላሉ!:</b> '
            '<tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>የማስታወቂያ ዋጋዎች</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Hours — <b>በስምምነት ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Hours — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Hours — <b>700 ETB</b>\n\n'
            'የፈለጉትን ምርጫ አሳውቀው የክፍያ አማራጮችን (payment method) ይጎብኙ '
            '<tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b> @mame_posts ቻናል ላይ ማስታወቂያ ለማሰራት</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> '
            'እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post ከስር ልከው የማስታወቂያ ዋጋዎችን ይመልከቱ '
            '<tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Payment Method</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>ንግድ ባንክ (CBE)</b>\n'
            '<code>1000528274394</code>\n\nMohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>ቴሌ ብር (TELE BIRR)</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>ክፍያውን ሲፈጽሙ ስክሪን ሹቱን ከስር ይላኩ!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Support & Downloader Help</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> '
            '<b>ቪዲዮ/ፎቶ ለማውረድ:</b> የ Tiktok, Instagram, Facebook, Reddit, Twitch, Vimeo, SoundCloud, Threads እና ሌሎች ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> '
            '<b>Video to Audio:</b> ማናቸውንም ቪዲዮ ከስልክዎ ይላኩ፣ ወደ MP3 Audio ቀይሮ ይልክልዎታል።\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።'
        )
    },
    "en": {
        "btn_add": "Add a bot to the chat",
        "btn_order": "Promote / Advertise",
        "btn_price": "Price & Rates",
        "btn_payment": "Payment Method",
        "btn_status": "My Status & Stats",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "Support & Help",
        "btn_back": "Back to Menu",
        "done_msg": "✅ <b>Done! Your language has been set.</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Loading|Please wait...</b>',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Extracted Audio</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Converted with</b> @{bot_username} & @mame_posts',
        "video_downloaded": '<tg-emoji emoji-id="530762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',
        "size_limit": "⚠️ <b>File is larger than 50MB! Telegram limit exceeded.</b>",
        "fail_download": "💔 <b>Could not download the file! Please check if link is public.</b>",
        "photo_download": '📸 <b>Downloaded Thumbnail/Photo</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
        "welcome": (
            'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> '
            '<b>My options (You can download video, photo, and audio from all Social Media):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee: videos & photos</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram: reels, photos & stories</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube: videos & music (Full & Shorts)</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X): videos & voice</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch, Vimeo & Others</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video to Audio Converter: Convert video to audio!</b>\n\n'
            '<b>And other Social Media:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Advertising Rates</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Hours — <b>Negotiable ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Hours — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Hours — <b>700 ETB</b>\n\n'
            'Choose your plan and proceed to Payment Method <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>To Advertise on @mame_posts Channel</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Please send your promo post below and view our rates <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Payment Method</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>Commercial Bank of Ethiopia (CBE)</b>\n'
            '<code>1000528274394</code>\n\nMohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Please send receipt screenshot after payment!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Support & Downloader Help</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> '
            '<b>To Download Video/Photo:</b> Send links from Tiktok, Instagram, Facebook, Reddit, Twitch, Vimeo, SoundCloud, Threads, etc.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video to Audio:</b> Send any video to convert it to MP3 audio.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> You can write messages here to reach out to the Admin.'
        )
    },
    "ar": {
        "btn_add": "إضافة البوت إلى المجموعة",
        "btn_order": "طلب إعلان",
        "btn_price": "أسعار الإعلانات",
        "btn_payment": "طرق الدفع",
        "btn_status": "حسابي وإحصائياتي",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "الدعم والتعليمات",
        "btn_back": "العودة للقائمة",
        "done_msg": "✅ <b>تم! تم تعيين لغتك.</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>جاري التحميل...</b>',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>الصوت المستخرج</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحويل بواسطة</b> @{bot_username} & @mame_posts',
        "video_downloaded": '<tg-emoji emoji-id="530762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',
        "size_limit": "⚠️ <b>حجم الملف أكبر من 50 ميغابايت!</b>",
        "fail_download": "💔 <b>تعذر تحميل الملف! يرجى التأكد من أن الرابط عام.</b>",
        "photo_download": '📸 <b>الصورة / الصورة المصغرة المحملة</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحميل بواسطة</b> @{bot_username}',
        "welcome": (
            'مرحباً بك <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> '
            '<b>خياراتي (يمكنك تحميل وتعديل الفيديوهات والصور والصوتيات من جميع منصات التواصل الاجتماعي):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee: مقاطع وصور</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram: ريلズ، صور وستوري</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube: فيديوهات وموسيقى (كامل وShorts)</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X): فيديوهات وتغريدات صوتية</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch, Vimeo وغيرها</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>تحويل الفيديو إلى صوت: يمكنك تحويل أي فيديو إلى ملف صوتي MP3!</b>\n\n'
            '<b>والمزيد من منصات التواصل الاجتماعي:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>أسعار الإعلانات</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 ساعة — <b>حسب الاتفاق ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 ساعة — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 ساعة — <b>700 ETB</b>\n\n'
            'اختر خطتك ثم انتقل إلى طرق الدفع <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>للإعلان على قناة @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> '
            'يرجى إرسال المنشور الذي تريد الإعلان عنه أدناه لعرض الأسعار <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>طرق الدفع</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>البنك التجاري الإثيوبي (CBE)</b>\n'
            '<code>1000528274394</code>\n\nMohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>تلي بر (TELE BIRR)</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>يرجى إرسال صورة إيصال الدفع بعد التحويل!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>الدعم والمساعدة في التحميل</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> '
            '<b>لتحميل الفيديوهات/الصور:</b> أرسل روابط تيك توك، إنستغرام، فيسبوك، ريديت، تويتش وغيرها مباشرة.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>تحويل الفيديو إلى صوت:</b> أرسل أي فيديو لتحويله إلى ملف صوتي MP3.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> يمكنك كتابة رسائلك هنا للتواصل مع المسؤول مباشرة.'
        )
    }
}

def get_trans(user_id, key):
    lang = get_user_language(user_id)
    if not lang or lang not in TRANSLATIONS:
        lang = "am"
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["am"])
    return lang_dict.get(key, TRANSLATIONS["am"].get(key, ""))

def get_bot_username(context):
    return context.bot.username or "mame_posts_bot"

def get_main_menu_keyboard(bot_username, user_id, use_custom_emoji=True):
    def btn(text, callback_data=None, url=None, emoji_id=None):
        kwargs = {"text": text}
        if callback_data:
            kwargs["callback_data"] = callback_data
        if url:
            kwargs["url"] = url
        if use_custom_emoji and emoji_id:
            kwargs["icon_custom_emoji_id"] = emoji_id
        return InlineKeyboardButton(**kwargs)

    keyboard = [
        [btn(get_trans(user_id, "btn_add"), url=f"https://t.me/{bot_username}?startgroup=true", emoji_id="5305545479814161889")],
        [btn(get_trans(user_id, "btn_order"), callback_data="cmd_order", emoji_id="5267442591548320083")],
        [
            btn(get_trans(user_id, "btn_price"), callback_data="cmd_price", emoji_id="5447458260200214425"),
            btn(get_trans(user_id, "btn_payment"), callback_data="cmd_payment", emoji_id="5186349709169525403")
        ],
        [
            btn(get_trans(user_id, "btn_status"), callback_data="cmd_status", emoji_id="5431577498364158238"),
            btn(get_trans(user_id, "btn_lang"), callback_data="cmd_change_lang", emoji_id="5431577498364158238")
        ],
        [btn(get_trans(user_id, "btn_support"), callback_data="cmd_support", emoji_id="5949327894567195412")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_language_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        ],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard(user_id, use_custom_emoji=True):
    kwargs = {"text": get_trans(user_id, "btn_back"), "callback_data": "cmd_back"}
    if use_custom_emoji:
        kwargs["icon_custom_emoji_id"] = "5248948801674159296"
    return InlineKeyboardMarkup([[InlineKeyboardButton(**kwargs)]])

async def post_init(application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("menu", "Main menu"),
        BotCommand("status", "Check status"),
        BotCommand("rate", "Advertising rates"),
        BotCommand("payment", "Payment methods"),
        BotCommand("help", "Help and support")
    ]
    await application.bot.set_my_commands(commands)

async def is_joined(update, context):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print("Force Join Error:", e)
        return True

async def show_force_join(update, context):
    user_id = update.effective_user.id
    lang = get_user_language(user_id)

    if lang == "en":
        text = (
            '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
            '<b>You must join the channel below to use the bot!</b>\n\n'
            '1️⃣ <tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> <b>Click Join Channel:</b>\n'
            '2️⃣ <tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> <b>Click I\'ve Joined and resend your link!</b>'
        )
        btn_join_text = "Join Channel"
        btn_joined_text = "I've Joined"
    elif lang == "ar":
        text = (
            '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
            '<b>يجب عليك الاشتراك في القناة أدناه لاستخدام البوت!</b>\n\n'
            '1️⃣ <tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> <b>اضغط على انضمام للقناة:</b>\n'
            '2️⃣ <tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> <b>اضغط على تم الانضمام وأعد إرسال الرابط!</b>'
        )
        btn_join_text = "انضمام للقناة"
        btn_joined_text = "تم الانضمام"
    else:
        text = (
            '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
            '<b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!</b>\n\n'
            '1️⃣ <tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> <b>Join Channel የሚለውን ይጫኑ:</b>\n'
            '2️⃣ <tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> <b>I\'ve Joined የሚለውን ተጭነው የላኩትን ደግመው ይላኩ!</b>'
        )
        btn_join_text = "Join Channel"
        btn_joined_text = "I've Joined"

    keyboard_custom = [
        [InlineKeyboardButton(text=btn_join_text, icon_custom_emoji_id="5767358836134382747", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton(text=btn_joined_text, icon_custom_emoji_id="5895288332581082241", callback_data="check_join")]
    ]
    keyboard_normal = [
        [InlineKeyboardButton(text=f"📢 {btn_join_text}", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton(text=f"✅ {btn_joined_text}", callback_data="check_join")]
    ]

    try:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard_custom), parse_mode="HTML")
    except Exception:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard_normal), parse_mode="HTML")

async def send_main_menu(chat_id, context, user_id):
    bot_username = get_bot_username(context)
    text = get_trans(user_id, "welcome")

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=get_main_menu_keyboard(bot_username, user_id, use_custom_emoji=True),
            parse_mode="HTML"
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=get_main_menu_keyboard(bot_username, user_id, use_custom_emoji=False),
            parse_mode="HTML"
        )

# ============================================================
# COMMAND HANDLERS
# ============================================================

async def start(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)

    setup_keyboard = ReplyKeyboardMarkup([["🏠 Menu"]], resize_keyboard=True, input_field_placeholder="Send link 🔗")
    user_lang = get_user_language(user_id)

    if not user_lang:
        await update.message.reply_text(
            "<b>Please select your language / እባክዎ ቋንቋ ይምረጡ / اختر لغتك፦</b>",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )
        return

    await update.message.reply_text("🏠", reply_markup=setup_keyboard)
    await send_main_menu(update.effective_chat.id, context, user_id)

async def status_command(update, context):
    if not update.message:
        return
    user = update.effective_user
    record_user_activity(user.id)
    total_users, user_msg_count = get_user_stats(user.id)
    username_text = f"@{user.username}" if user.username else "የለውም"

    msg = (
        '<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>My Status & Stats</b>\n\n'
        f'👤 <b>Username:</b> {username_text}\n'
        f'🆔 <b>ID:</b> <code>{user.id}</code>\n\n'
        f'💬 <b>Your Messages:</b> {user_msg_count}\n'
        f'👥 <b>Bot Users:</b> {total_users}\n\n'
        '🔥 <b>Engagement: Active</b>'
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def rates_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(get_trans(user_id, "price"), parse_mode="HTML")

async def payment_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(get_trans(user_id, "payment"), parse_mode="HTML")

async def help_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(get_trans(user_id, "support"), parse_mode="HTML")

async def broadcast_command(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return

    reply_msg = update.message.reply_to_message
    has_args = bool(context.args)

    if not reply_msg and not has_args:
        await update.message.reply_text("❌ Reply to a message or use:\n/broadcast your message")
        return

    data = load_data()
    success_count = 0
    fail_count = 0
    status_msg = await update.message.reply_text("📢 Broadcasting...")

    for uid_str in data.keys():
        try:
            chat_id = int(uid_str)
            if reply_msg:
                await reply_msg.copy(chat_id=chat_id)
            else:
                text_to_send = " ".join(context.args)
                await context.bot.send_message(chat_id=chat_id, text=text_to_send, parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ Broadcast completed.\n\nSuccessful: {success_count}\nFailed: {fail_count}"
    )

# ============================================================
# VIDEO TO AUDIO CONVERTER
# ============================================================

async def convert_video_to_audio(update, context):
    if not update.message:
        return

    user_id = update.effective_user.id
    record_user_activity(user_id)

    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    video = update.message.video or update.message.video_note
    if not video:
        document = update.message.document
        if document and document.mime_type and document.mime_type.startswith("video/"):
            video = document

    if not video:
        return

    file_id = update.message.message_id
    input_path = f"input_vid_{user_id}_{file_id}.mp4"
    output_path = f"output_aud_{user_id}_{file_id}.mp3"
    status_msg = None

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)
        status_msg = await update.message.reply_text(get_trans(user_id, "loading"), parse_mode="HTML")

        tg_file = await video.get_file()
        await tg_file.download_to_drive(input_path)

        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            raise RuntimeError("Downloaded video is empty")

        ffmpeg_bin = FFMPEG_PATH if FFMPEG_PATH else "ffmpeg"
        cmd = [ffmpeg_bin, "-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output_path]
        result = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=300)

        if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("FFmpeg error")

        bot_username = get_bot_username(context)
        share_url = f"https://t.me/share/url?url={quote(f'https://t.me/{bot_username}?start=share')}&text={quote('Try this awesome Bot!🔥')}"
        keyboard_share = [[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]]

        caption_text = get_trans(user_id, "video_converted").format(bot_username=bot_username)

        with open(output_path, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard_share)
            )

        if status_msg:
            await status_msg.delete()

    except Exception as e:
        print("Video to Audio Error:", e)
        if status_msg:
            await status_msg.edit_text(get_trans(user_id, "fail_download"), parse_mode="HTML")
    finally:
        for path in [input_path, output_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

# ============================================================
# SAFE URL CLEANER (NEVER DESTROYS YOUTUBE LINKS)
# ============================================================

def clean_url(raw_url: str) -> str:
    url = raw_url.strip()

    # YouTube Shorts converter
    shorts_match = re.search(r'(?:youtube\.com|youtu\.be)/shorts/([a-zA-Z0-9_-]+)', url)
    if shorts_match:
        return f"https://www.youtube.com/watch?v={shorts_match.group(1)}"

    # youtu.be short link converter
    youtu_be_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if youtu_be_match:
        return f"https://www.youtube.com/watch?v={youtu_be_match.group(1)}"

    # Standard YouTube watch URL: preserve ?v= clean
    if "youtube.com/watch" in url:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        v = query.get("v")
        if v:
            return f"https://www.youtube.com/watch?v={v[0]}"

    return url

# ============================================================
# MODERN URL DOWNLOAD ENGINE WITH VERIFIED DENO + EJS FIX
# ============================================================

def get_video_options(url: str, output_template: str):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'concurrent_fragment_downloads': 5,
        'outtmpl': output_template,
        'writethumbnail': True,
        'merge_output_format': 'mp4',
        'format': 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<50M]/best[filesize<50M]/best',
        
        # KEY PARAMETERS VERIFIED WORKING ON YOUR VPS:
        'js_runtimes': {'deno': {'path': DENO_BIN}},
        'remote_components': ['ejs:github'],
    }

    if "likee" in url or "likee.video" in url:
        opts['http_headers'] = {'Referer': 'https://likee.video/'}
    elif "vimeo.com" in url:
        opts['http_headers'] = {'Referer': 'https://vimeo.com/'}

    if os.path.exists(COOKIES_PATH):
        opts['cookiefile'] = COOKIES_PATH

    return opts

def download_media_func(url: str, output_template: str):
    with yt_dlp.YoutubeDL(get_video_options(url, output_template)) as ydl:
        ydl.download([url])

def find_downloaded_file(prefix: str):
    video_file = None
    thumb_file = None
    for f in os.listdir('.'):
        if f.startswith(prefix) and not f.endswith(('.part', '.ytdl', '.temp')):
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                thumb_file = f
            elif ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
                video_file = f
    return video_file, thumb_file

async def handle_url_download(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_url: str):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

    status_msg = await update.message.reply_text(
        get_trans(user_id, "loading"),
        parse_mode="HTML"
    )

    bot_username = get_bot_username(context)
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=share&text=Try%20this%20awesome%20Downloader%20Bot!🔥"
    reply_markup_share = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]])

    url = clean_url(raw_url)

    # 1. Direct Pinterest Image
    if "pinterest.com" in url or "pin.it" in url:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            res = requests.get(url, headers=headers, timeout=10)
            img_matches = re.findall(r'https://i\.pinimg\.com/(?:originals|736x)/[^\s"\'\>]+\.(?:jpg|png|jpeg|webp)', res.text)
            if img_matches:
                real_img_url = img_matches[0]
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                await update.message.reply_photo(
                    photo=real_img_url,
                    caption=get_trans(user_id, "photo_download").format(bot_username=bot_username),
                    reply_markup=reply_markup_share,
                    parse_mode="HTML"
                )
                await status_msg.delete()
                return
        except Exception as pe:
            print("Pinterest Fetch Error:", pe)

    media_prefix = f"media_{user_id}_{update.message.message_id}"
    media_template = f"{media_prefix}.%(ext)s"
    sent_any = False

    try:
        # Download media
        await asyncio.to_thread(download_media_func, url, media_template)

        actual_video, actual_thumb = find_downloaded_file(media_prefix)
        ffmpeg_bin = FFMPEG_PATH if FFMPEG_PATH else "ffmpeg"

        # 2. SEND THUMBNAIL (Converted to JPG if WebP)
        if actual_thumb and os.path.exists(actual_thumb):
            clean_thumb = actual_thumb
            try:
                if actual_thumb.lower().endswith(".webp"):
                    clean_thumb = f"{media_prefix}_thumb.jpg"
                    await asyncio.to_thread(
                        subprocess.run,
                        [ffmpeg_bin, "-y", "-i", actual_thumb, clean_thumb],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                if os.path.exists(clean_thumb) and os.path.getsize(clean_thumb) > 0:
                    with open(clean_thumb, 'rb') as tf:
                        await update.message.reply_photo(
                            photo=tf,
                            caption=get_trans(user_id, "photo_download").format(bot_username=bot_username),
                            reply_markup=reply_markup_share,
                            parse_mode="HTML"
                        )
                    sent_any = True
            except Exception as thumb_err:
                print("Thumbnail send error:", thumb_err)

        # 3. SEND VIDEO (BULLETPROOF REMUX TO AVOID Document_invalid)
        if actual_video and os.path.exists(actual_video):
            file_size = os.path.getsize(actual_video)
            if file_size > 1000 and file_size <= 50 * 1024 * 1024:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

                # Direct remux to standard mp4 container with faststart (fixes Telegram desktop/mobile playback)
                final_video_file = f"{media_prefix}_telegram.mp4"
                remux_cmd = [
                    ffmpeg_bin, "-y",
                    "-i", actual_video,
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    final_video_file
                ]
                await asyncio.to_thread(subprocess.run, remux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                video_to_upload = final_video_file if (os.path.exists(final_video_file) and os.path.getsize(final_video_file) > 1000) else actual_video

                video_sent_successfully = False
                try:
                    with open(video_to_upload, 'rb') as vf:
                        await update.message.reply_video(
                            video=vf,
                            caption=f'<tg-emoji emoji-id="530762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',
                            reply_markup=reply_markup_share,
                            parse_mode="HTML",
                            supports_streaming=True
                        )
                    video_sent_successfully = True
                    sent_any = True
                except Exception as vid_err:
                    print("reply_video error:", vid_err)

                # Fallback to Document ONLY if reply_video failed
                if not video_sent_successfully:
                    try:
                        with open(video_to_upload, 'rb') as doc_file:
                            await update.message.reply_document(
                                document=doc_file,
                                filename=f"video_{update.message.message_id}.mp4",
                                caption=f'<tg-emoji emoji-id="530762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts',
                                reply_markup=reply_markup_share,
                                parse_mode="HTML"
                            )
                        sent_any = True
                    except Exception as doc_err:
                        print("Document fallback failed:", doc_err)

                # 4. EXTRACT & SEND AUDIO (MP3)
                audio_output = f"audio_{user_id}_{update.message.message_id}.mp3"
                cmd = [ffmpeg_bin, "-y", "-i", actual_video, "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_output]
                await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if os.path.exists(audio_output) and os.path.getsize(audio_output) > 0:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
                    with open(audio_output, 'rb') as af:
                        await update.message.reply_audio(
                            audio=af,
                            caption=f'<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Extracted Audio / BGM (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
                            reply_markup=reply_markup_share,
                            parse_mode="HTML"
                        )
                    sent_any = True
            elif file_size > 50 * 1024 * 1024:
                await status_msg.edit_text(get_trans(user_id, "size_limit"), parse_mode="HTML")
                return

    except Exception as e:
        print("Media Download Execution Error:", e)

    finally:
        for f in os.listdir('.'):
            if f.startswith(media_prefix) or f.startswith(f"audio_{user_id}_{update.message.message_id}"):
                try:
                    os.remove(f)
                except Exception:
                    pass

    if sent_any:
        try:
            await status_msg.delete()
        except Exception:
            pass
    else:
        try:
            await status_msg.edit_text(get_trans(user_id, "fail_download"), parse_mode="HTML")
        except Exception:
            pass

# ============================================================
# CALLBACK QUERY & USER HANDLERS
# ============================================================

async def button_callback(update, context):
    query = update.callback_query
    data = query.data
    user = query.from_user
    user_id = user.id
    bot_username = get_bot_username(context)

    if data.startswith("lang_"):
        lang_code = data.split("_", 1)[1]
        if lang_code not in TRANSLATIONS:
            await query.answer("Language unavailable.", show_alert=True)
            return

        set_user_language(user_id, lang_code)
        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        setup_keyboard = ReplyKeyboardMarkup([["🏠 Menu"]], resize_keyboard=True, input_field_placeholder="Send link 🔗")
        await context.bot.send_message(
            chat_id=user_id,
            text=get_trans(user_id, "done_msg"),
            reply_markup=setup_keyboard,
            parse_mode="HTML"
        )
        await send_main_menu(user_id, context, user_id)
        return

    if data == "cmd_change_lang":
        await query.answer()
        await query.edit_message_text(
            "<b>Please select your language / እባክዎ ቋንቋ ይምረጡ / اختر لغتك፦</b>",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )
        return

    if data == "cmd_back":
        await query.answer()
        text = get_trans(user_id, "welcome")
        try:
            await query.edit_message_text(text=text, reply_markup=get_main_menu_keyboard(bot_username, user_id, True), parse_mode="HTML")
        except Exception:
            await query.edit_message_text(text=text, reply_markup=get_main_menu_keyboard(bot_username, user_id, False), parse_mode="HTML")
        return

    for key_cmd in ["price", "order", "payment", "support"]:
        if data == f"cmd_{key_cmd}":
            await query.answer()
            text = get_trans(user_id, key_cmd)
            try:
                await query.edit_message_text(text=text, reply_markup=get_back_keyboard(user_id, True), parse_mode="HTML")
            except Exception:
                await query.edit_message_text(text=text, reply_markup=get_back_keyboard(user_id, False), parse_mode="HTML")
            return

    if data == "cmd_status":
        await query.answer()
        total_users, user_msg_count = get_user_stats(user_id)
        username_text = f"@{user.username}" if user.username else "የለውም"
        msg = (
            '<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>My Status & Stats</b>\n\n'
            f'👤 <b>Username:</b> {username_text}\n'
            f'🆔 <b>ID:</b> <code>{user_id}</code>\n\n'
            f'💬 <b>Your Messages:</b> {user_msg_count}\n'
            f'👥 <b>Bot Users:</b> {total_users}\n\n'
            '🔥 <b>Engagement: Active</b>'
        )
        try:
            await query.edit_message_text(text=msg, reply_markup=get_back_keyboard(user_id, True), parse_mode="HTML")
        except Exception:
            await query.edit_message_text(text=msg, reply_markup=get_back_keyboard(user_id, False), parse_mode="HTML")
        return

async def check_join(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            await query.answer()
            try:
                await query.edit_message_text(
                    '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>አሁን ቻናሉን ተቀላቅለዋል።</b>\n\nእባክዎ የላኩትን ሊንክ ደግመው ይላኩ።',
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await query.answer("❌ እባክዎ መጀመሪያ Channel ይቀላቀሉ!", show_alert=True)
    except Exception:
        await query.answer("⚠️ Channel membership could not be verified.", show_alert=True)

SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be", "tiktok.com", "likee.video", "likee.com",
    "pinterest.com", "pin.it", "instagram.com", "twitter.com", "x.com",
    "facebook.com", "fb.watch", "reddit.com", "redd.it", "twitch.tv",
    "vimeo.com", "vk.com", "ok.ru", "tumblr.com", "soundcloud.com", "threads.net"
]

async def handle_user_messages(update, context):
    if not update.message:
        return

    user_id = update.effective_user.id
    record_user_activity(user_id)

    if update.message.video or update.message.video_note:
        await convert_video_to_audio(update, context)
        return

    document = update.message.document
    if document and document.mime_type and document.mime_type.startswith("video/"):
        await convert_video_to_audio(update, context)
        return

    text = update.message.text or update.message.caption or ""

    if text.strip() == "🏠 Menu":
        await send_main_menu(update.effective_chat.id, context, user_id)
        return

    text_lower = text.lower()
    is_supported_link = any(domain in text_lower for domain in SUPPORTED_DOMAINS)

    if is_supported_link:
        if not await is_joined(update, context):
            await show_force_join(update, context)
            return

        url_match = re.search(r"https?://[^\s]+", text)
        target_url = url_match.group(0).rstrip(".,!?)]}") if url_match else text.strip()
        await handle_url_download(update, context, target_url)
        return

    # Forward other messages to Admin
    username = f"@{update.effective_user.username}" if update.effective_user.username else "No username"
    header_text = (
        "📩 <b>New User Message</b>\n\n"
        f"👤 <b>Name:</b> {update.effective_user.full_name}\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>"
    )

    try:
        header_msg = await context.bot.send_message(chat_id=ADMIN_ID, text=header_text, parse_mode="HTML")
        forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)

        if "user_mapping" not in context.bot_data:
            context.bot_data["user_mapping"] = {}

        user_mapping = context.bot_data["user_mapping"]
        user_mapping[str(header_msg.message_id)] = user_id
        user_mapping[str(forwarded_msg.message_id)] = user_id

        await update.message.reply_text("✅ መልዕክትዎ ተቀብለናል። Admin ያነበበውን መልስ ይልክልዎታል።")
    except Exception as e:
        print("Admin forwarding error:", e)

async def admin_reply(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return

    replied_msg = update.message.reply_to_message
    if not replied_msg:
        return

    user_mapping = context.bot_data.get("user_mapping", {})
    target_user_id = None
    replied_id_str = str(replied_msg.message_id)

    if replied_id_str in user_mapping:
        target_user_id = user_mapping[replied_id_str]

    if not target_user_id and replied_msg.forward_from:
        target_user_id = replied_msg.forward_from.id

    if not target_user_id and replied_msg.text and "🆔 ID:" in replied_msg.text:
        match = re.search(r"🆔 ID:\s*<code>(\d+)</code>", replied_msg.text)
        if match:
            target_user_id = int(match.group(1))

    if not target_user_id and replied_msg.caption and "🆔 ID:" in replied_msg.caption:
        match = re.search(r"🆔 ID:\s*<code>(\d+)</code>", replied_msg.caption)
        if match:
            target_user_id = int(match.group(1))

    if target_user_id:
        try:
            await update.message.copy(chat_id=target_user_id)
            await update.message.reply_text("✅ Reply sent to the user.")
        except Exception as e:
            await update.message.reply_text(f"❌ Could not send reply.\n{e}")
    else:
        await update.message.reply_text("❌ User ID could not be found.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if "Conflict: terminated by other getUpdates request" not in str(context.error):
        print("❌ ERROR:", context.error)

# ============================================================
# MAIN
# ============================================================

def main():
    if not TOKEN:
        raise RuntimeError("❌ BOT_TOKEN environment variable is missing!")

    keep_alive()

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("rates", rates_command))
    application.add_handler(CommandHandler("rate", rates_command))
    application.add_handler(CommandHandler("payment", payment_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))

    application.add_handler(CallbackQueryHandler(check_join, pattern=r"^check_join$"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern=r"^(cmd_|lang_)"))

    admin_filter = filters.User(user_id=ADMIN_ID) & filters.REPLY & ~filters.COMMAND
    application.add_handler(MessageHandler(admin_filter, admin_reply))

    application.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, convert_video_to_audio))

    type_filter = (
        filters.TEXT
        | filters.PHOTO
        | filters.Document.ALL
        | filters.VOICE
        | filters.AUDIO
        | filters.Sticker.ALL
    ) & ~filters.COMMAND
    application.add_handler(MessageHandler(type_filter, handle_user_messages))

    application.add_error_handler(error_handler)

    print("🤖 Mame Posts Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
