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
            '<b>My options:</b>\n\n'
            '🎵 | <b>Tiktok & Likee: videos & photos</b>\n'
            '📸 | <b>Pinterest & Instagram: reels, photos & stories</b>\n'
            '▶️ | <b>YouTube: videos & music (Full & Shorts)</b>\n'
            '✖️ | <b>Twitter (X): videos & voice</b>\n'
            '📘 | <b>Facebook, Reddit, Twitch, Vimeo & Others</b>\n'
            '📹 <b>Video to Audio Converter</b>'
        ),
        "price": '💰 12 Hours: በስምምነት | 24 Hours: 500 ETB | 48 Hours: 700 ETB',
        "order": '📢 @mame_posts ቻናል ላይ ማስታወቂያ ለማሰራት',
        "payment": '💳 CBE: <code>1000528274394</code> | Telebirr: <code>+251963266849</code>',
        "support": '💬 Support and Help'
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
        "size_limit": "⚠️ <b>File exceeds Telegram 50MB limit!</b>",
        "fail_download": "💔 <b>Could not download the file! Please check if link is public.</b>",
        "photo_download": '📸 <b>Downloaded Thumbnail/Photo</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
        "welcome": 'Hello 🚨\n\n<b>Download video, photo, and audio from all Social Media!</b>',
        "price": '💰 24 Hours — 500 ETB | 48 Hours — 700 ETB',
        "order": '📢 To Advertise on @mame_posts Channel',
        "payment": '💳 CBE: <code>1000528274394</code> | Telebirr: <code>+251963266849</code>',
        "support": '💬 Support and Help'
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
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>الصوت المستخرج</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحويل بواسطة</b> @{bot_username}',
        "video_downloaded": '<tg-emoji emoji-id="530762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username}',
        "size_limit": "⚠️ <b>حجم الملف أكبر من 50 ميغابايت!</b>",
        "fail_download": "💔 <b>تعذر تحميل الملف!</b>",
        "photo_download": '📸 <b>الصورة المصغرة المحملة</b>',
        "welcome": 'مرحباً بك! قم بتحميل مقاطع الفيديو والموسيقى بسهولة.',
        "price": '💰 24 ساعة: 500 ETB',
        "order": '📢 للإعلان على @mame_posts',
        "payment": '💳 CBE: <code>1000528274394</code>',
        "support": '💬 الدعم والمساعدة'
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
        text = '🔒 <b>You must join the channel below to use the bot!</b>'
        btn_join_text = "Join Channel"
        btn_joined_text = "I've Joined"
    elif lang == "ar":
        text = '🔒 <b>يجب عليك الاشتراك في القناة أدناه لاستخدام البوت!</b>'
        btn_join_text = "انضمام للقناة"
        btn_joined_text = "تم الانضمام"
    else:
        text = '🔒 <b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!</b>'
        btn_join_text = "Join Channel"
        btn_joined_text = "I've Joined"

    keyboard_custom = [
        [InlineKeyboardButton(text=btn_join_text, icon_custom_emoji_id="5767358836134382747", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton(text=btn_joined_text, icon_custom_emoji_id="5895288332581082241", callback_data="check_join")]
    ]
    try:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard_custom), parse_mode="HTML")
    except Exception:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text=btn_join_text, url=FORCE_CHANNEL_LINK)]]), parse_mode="HTML")

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

    await status_msg.edit_text(f"✅ Broadcast completed.\n\nSuccessful: {success_count}\nFailed: {fail_count}")

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
# SAFE URL CLEANER
# ============================================================

def clean_url(raw_url: str) -> str:
    url = raw_url.strip()

    shorts_match = re.search(r'(?:youtube\.com|youtu\.be)/shorts/([a-zA-Z0-9_-]+)', url)
    if shorts_match:
        return f"https://www.youtube.com/watch?v={shorts_match.group(1)}"

    youtu_be_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if youtu_be_match:
        return f"https://www.youtube.com/watch?v={youtu_be_match.group(1)}"

    if "youtube.com/watch" in url:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        v = query.get("v")
        if v:
            return f"https://www.youtube.com/watch?v={v[0]}"

    return url

# ============================================================
# OPTIMAL 48MB TARGETED DOWNLOAD ENGINE (STAYS UNDER TELEGRAM LIMIT)
# ============================================================

def get_ytdlp_options(output_template: str):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'concurrent_fragment_downloads': 5,
        'outtmpl': output_template,
        'writethumbnail': True,
        
        # SMART TELEGRAM COMPATIBLE FORMAT:
        # Tries best video under 45M + audio under 5M, or best overall under 48M, or standard 720p/480p/360p fallback
        'format': (
            'bestvideo[filesize<42M]+bestaudio[filesize<6M]/'
            'best[filesize<48M]/'
            'bestvideo[height<=720][filesize<45M]+bestaudio/'
            'best[height<=720][filesize<48M]/'
            'best[height<=480]/'
            'best'
        ),
        'merge_output_format': 'mp4',
        
        # EXACT VERIFIED DENO SETTINGS:
        'js_runtimes': {'deno': {'path': DENO_BIN}},
        'remote_components': ['ejs:github'],
    }

    if os.path.exists(COOKIES_PATH):
        opts['cookiefile'] = COOKIES_PATH

    return opts

def download_media(url: str, output_template: str):
    with yt_dlp.YoutubeDL(get_ytdlp_options(output_template)) as ydl:
        ydl.download([url])

def find_downloaded_file(prefix: str):
    video_file = None
    thumb_file = None
    for f in os.listdir('.'):
        if f.startswith(prefix) and not f.endswith(('.part', '.ytdl', '.temp')):
            # Ignore intermediate unmerged parts
            if re.search(r'\.f\d+\.', f):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                thumb_file = f
            elif ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
                if os.path.getsize(f) > 50 * 1024:
                    video_file = f
    return video_file, thumb_file

async def handle_url_download(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_url: str):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot_username = get_bot_username(context)

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    status_msg = await update.message.reply_text(get_trans(user_id, "loading"), parse_mode="HTML")

    target_url = clean_url(raw_url)
    prefix = f"media_{user_id}_{update.message.message_id}"
    template = f"{prefix}.%(ext)s"

    # Direct Pinterest Image bypass
    if "pinterest.com" in target_url or "pin.it" in target_url:
        try:
            res = requests.get(target_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            img_matches = re.findall(r'https://i\.pinimg\.com/(?:originals|736x)/[^\s"\'\>]+\.(?:jpg|png|jpeg|webp)', res.text)
            if img_matches:
                await update.message.reply_photo(
                    photo=img_matches[0],
                    caption=get_trans(user_id, "photo_download").format(bot_username=bot_username),
                    parse_mode="HTML"
                )
                await status_msg.delete()
                return
        except Exception:
            pass

    sent_any = False

    try:
        # Download media using verified Deno + EJS config
        await asyncio.to_thread(download_media, target_url, template)

        actual_video, actual_thumb = find_downloaded_file(prefix)
        ffmpeg_bin = FFMPEG_PATH or "ffmpeg"

        # 1. SEND THUMBNAIL
        if actual_thumb and os.path.exists(actual_thumb):
            clean_thumb = actual_thumb
            try:
                if actual_thumb.lower().endswith(".webp"):
                    clean_thumb = f"{prefix}_thumb.jpg"
                    await asyncio.to_thread(
                        subprocess.run,
                        [ffmpeg_bin, "-y", "-i", actual_thumb, clean_thumb],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                if os.path.exists(clean_thumb) and os.path.getsize(clean_thumb) > 1000:
                    with open(clean_thumb, 'rb') as tf:
                        await update.message.reply_photo(
                            photo=tf,
                            caption=get_trans(user_id, "photo_download").format(bot_username=bot_username),
                            parse_mode="HTML"
                        )
                    sent_any = True
            except Exception as te:
                print("Thumbnail send failed:", te)

        # 2. COMPRESS IF OVER 49MB TO PREVENT "Request Entity Too Large"
        if actual_video and os.path.exists(actual_video):
            file_size = os.path.getsize(actual_video)
            video_to_send = actual_video

            # If downloaded file is greater than 49 MB, compress it to 45 MB with FFmpeg
            if file_size > 49 * 1024 * 1024:
                print(f"⚠️ File is {file_size/(1024*1024):.2f}MB, compressing to under 48MB for Telegram...")
                compressed_video = f"{prefix}_compressed.mp4"
                compress_cmd = [
                    ffmpeg_bin, "-y",
                    "-i", actual_video,
                    "-vf", "scale=-2:480",
                    "-c:v", "libx264",
                    "-crf", "28",
                    "-preset", "faster",
                    "-c:a", "aac",
                    "-b:a", "96k",
                    "-movflags", "+faststart",
                    compressed_video
                ]
                await asyncio.to_thread(subprocess.run, compress_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(compressed_video) and os.path.getsize(compressed_video) > 1000:
                    video_to_send = compressed_video
                    file_size = os.path.getsize(video_to_send)

            print(f"✅ Sending file: {video_to_send} ({file_size / (1024*1024):.2f} MB)")
            caption_text = f'<tg-emoji emoji-id="530762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>'
            
            # Send as video
            video_sent = False
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
                with open(video_to_send, 'rb') as vf:
                    await update.message.reply_video(
                        video=vf,
                        caption=caption_text,
                        parse_mode="HTML",
                        supports_streaming=True
                    )
                video_sent = True
                sent_any = True
            except Exception as vid_err:
                print("reply_video error:", vid_err)

            # Fallback to document
            if not video_sent:
                try:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                    with open(video_to_send, 'rb') as doc_file:
                        await update.message.reply_document(
                            document=doc_file,
                            caption=caption_text,
                            parse_mode="HTML"
                        )
                    sent_any = True
                except Exception as doc_err:
                    print("Document fallback error:", doc_err)

            # 3. EXTRACT & SEND AUDIO (MP3)
            audio_output = f"audio_{user_id}_{update.message.message_id}.mp3"
            cmd = [ffmpeg_bin, "-y", "-i", actual_video, "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_output]
            await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(audio_output) and os.path.getsize(audio_output) > 1000:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
                with open(audio_output, 'rb') as af:
                    await update.message.reply_audio(
                        audio=af,
                        caption=f'<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Extracted Audio / BGM (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
                        parse_mode="HTML"
                    )
                sent_any = True

    except Exception as e:
        print("Download engine error:", e)

    finally:
        for f in os.listdir('.'):
            if f.startswith(prefix) or f.startswith(f"audio_{user_id}_{update.message.message_id}"):
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
# CALLBACKS & MESSAGES
# ============================================================

async def button_callback(update, context):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    bot_username = get_bot_username(context)

    if data.startswith("lang_"):
        set_user_language(user_id, data.split("_", 1)[1])
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=get_trans(user_id, "done_msg"),
            reply_markup=ReplyKeyboardMarkup([["🏠 Menu"]], resize_keyboard=True),
            parse_mode="HTML"
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=get_trans(user_id, "welcome"),
            reply_markup=get_main_menu_keyboard(bot_username, user_id),
            parse_mode="HTML"
        )
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
        await query.edit_message_text(
            get_trans(user_id, "welcome"),
            reply_markup=get_main_menu_keyboard(bot_username, user_id),
            parse_mode="HTML"
        )
        return

    for k in ["price", "order", "payment", "support"]:
        if data == f"cmd_{k}":
            await query.answer()
            await query.edit_message_text(
                get_trans(user_id, k),
                reply_markup=get_back_keyboard(user_id),
                parse_mode="HTML"
            )
            return

    if data == "cmd_status":
        await query.answer()
        total, count = get_user_stats(user_id)
        username_text = f"@{query.from_user.username}" if query.from_user.username else "የለውም"
        msg = (
            f'<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>My Status & Stats</b>\n\n'
            f'👤 <b>Username:</b> {username_text}\n'
            f'🆔 <b>ID:</b> <code>{user_id}</code>\n\n'
            f'💬 <b>Your Messages:</b> {count}\n'
            f'👥 <b>Bot Users:</b> {total}\n\n'
            '🔥 <b>Engagement: Active</b>'
        )
        await query.edit_message_text(msg, reply_markup=get_back_keyboard(user_id), parse_mode="HTML")
        return

async def check_join(update, context):
    query = update.callback_query
    if await is_joined(update, context):
        await query.answer()
        await query.edit_message_text("✅ <b>Joined! Resend your link.</b>", parse_mode="HTML")
    else:
        await query.answer("❌ Join the channel first!", show_alert=True)

SUPPORTED = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com", "twitter.com", "x.com", "facebook.com", "reddit.com", "pinterest.com", "pin.it"]

async def handle_user_messages(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)

    if update.message.video or update.message.video_note or (update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith("video/")):
        await convert_video_to_audio(update, context)
        return

    text = update.message.text or update.message.caption or ""
    if text.strip() == "🏠 Menu":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_trans(user_id, "welcome"),
            reply_markup=get_main_menu_keyboard(get_bot_username(context), user_id),
            parse_mode="HTML"
        )
        return

    if any(d in text.lower() for d in SUPPORTED):
        if not await is_joined(update, context):
            await show_force_join(update, context)
            return
        m = re.search(r"https?://[^\s]+", text)
        target = m.group(0).rstrip(".,!?)]}") if m else text.strip()
        await handle_url_download(update, context, target)
        return

    # Forward to admin
    try:
        header = f"📩 <b>New User Message</b>\n\n👤 <b>Name:</b> {update.effective_user.full_name}\n🆔 <b>ID:</b> <code>{user_id}</code>"
        h_msg = await context.bot.send_message(chat_id=ADMIN_ID, text=header, parse_mode="HTML")
        f_msg = await update.message.forward(chat_id=ADMIN_ID)
        if "user_mapping" not in context.bot_data:
            context.bot_data["user_mapping"] = {}
        context.bot_data["user_mapping"][str(h_msg.message_id)] = user_id
        context.bot_data["user_mapping"][str(f_msg.message_id)] = user_id
        await update.message.reply_text("✅ መልዕክትዎ ተቀብለናል።")
    except Exception:
        pass

async def admin_reply(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    r_msg = update.message.reply_to_message
    if not r_msg:
        return
    mapping = context.bot_data.get("user_mapping", {})
    uid = mapping.get(str(r_msg.message_id))
    if uid:
        try:
            await update.message.copy(chat_id=uid)
            await update.message.reply_text("✅ Sent.")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if "Conflict: terminated by other getUpdates request" not in str(context.error):
        print("❌ ERROR:", context.error)

# ============================================================
# MAIN
# ============================================================

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing!")

    keep_alive()

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .connect_timeout(60.0)
        .read_timeout(300.0)
        .write_timeout(300.0)
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

    type_filter = (filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.Sticker.ALL) & ~filters.COMMAND
    application.add_handler(MessageHandler(type_filter, handle_user_messages))

    application.add_error_handler(error_handler)

    print("🤖 Mame Posts Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
