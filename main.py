import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from woocommerce import API
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WC_URL = os.getenv("WC_URL")
WC_KEY = os.getenv("WC_KEY")
WC_SECRET = os.getenv("WC_SECRET")

# تنظیم ووکامرس
wcapi = API(
    url=WC_URL,
    consumer_key=WC_KEY,
    consumer_secret=WC_SECRET,
    version="wc/v3"
)

# مراحل گفتگو
(NAME, PRICE, SHORT_DESC, CATEGORY, PHOTO) = range(5)

# فعال‌سازی لاگ‌ها
logging.basicConfig(level=logging.INFO)

# شروع ساخت محصول
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! نام محصول را وارد کنید:")
    return NAME

async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("قیمت محصول را وارد کنید (فقط عدد):")
    return PRICE

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price"] = update.message.text
    await update.message.reply_text("توضیح کوتاه محصول را وارد کنید:")
    return SHORT_DESC

async def short_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["short_desc"] = update.message.text
    await update.message.reply_text("نام دسته‌بندی محصول را وارد کنید:")
    return CATEGORY

async def category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category_name = update.message.text
    context.user_data["category"] = category_name

    # بررسی اینکه آیا دسته‌بندی وجود دارد
    categories = wcapi.get("products/categories").json()
    category_id = None
    for cat in categories:
        if cat["name"] == category_name:
            category_id = cat["id"]
            break

    # اگر وجود نداشت، ایجاد کن
    if not category_id:
        data = {"name": category_name}
        response = wcapi.post("products/categories", data).json()
        category_id = response.get("id")

    context.user_data["category_id"] = category_id
    await update.message.reply_text("لطفاً عکس محصول را ارسال کنید:")
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()

    # آپلود عکس به ووکامرس از طریق REST API
    import base64
    import requests

    # ابتدا عکس را در سایت آپلود می‌کنیم
    media_url = f"{WC_URL}/wp-json/wp/v2/media"
    headers = {
        "Content-Disposition": "attachment; filename=product.jpg",
        "Authorization": f"Basic {base64.b64encode(f'{WC_KEY}:{WC_SECRET}'.encode()).decode()}",
        "Content-Type": "image/jpeg"
    }
    res = requests.post(media_url, headers=headers, data=photo_bytes)
    image_data = res.json()
    image_id = image_data.get("id")

    # ساخت محصول نهایی
    product_data = {
        "name": context.user_data["name"],
        "type": "simple",
        "regular_price": context.user_data["price"],
        "short_description": context.user_data["short_desc"],
        "categories": [{"id": context.user_data["category_id"]}],
        "images": [{"id": image_id}]
    }

    wcapi.post("products", product_data)

    await update.message.reply_text("✅ محصول با موفقیت ساخته شد!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⛔ عملیات لغو شد.")
    return ConversationHandler.END

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price)],
            SHORT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, short_desc)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category)],
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)

    print("ربات در حال اجراست...")
    app.run_polling()

