import os
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# فعال‌سازی لاگ برای خطایابی
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# متغیرهای API ووکامرس
WC_URL = "https://menupich.ir/cafeuka/wp-json/wc/v3"
WC_KEY = os.environ.get("WC_KEY")
WC_SECRET = os.environ.get("WC_SECRET")

# مراحل گفتگو
(NAME, DESCRIPTION, CHOOSE_CATEGORY, NEW_CATEGORY, PRODUCT_IMAGE) = range(5)

# شروع گفتگو
def start(update: Update, context: CallbackContext):
    update.message.reply_text("لطفاً نام محصول را وارد کنید:")
    return NAME

def get_categories():
    url = f"{WC_URL}/products/categories"
    response = requests.get(url, auth=(WC_KEY, WC_SECRET))
    if response.status_code == 200:
        return response.json()
    return []

def ask_category(update: Update, context: CallbackContext):
    categories = get_categories()
    category_names = [cat["name"] for cat in categories]
    keyboard = [[name] for name in category_names]
    keyboard.append(["➕ ساخت دسته‌بندی جدید"])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text("یکی از دسته‌بندی‌های زیر را انتخاب کنید یا گزینه ساخت را بزنید:", reply_markup=reply_markup)
    return CHOOSE_CATEGORY

def handle_name(update: Update, context: CallbackContext):
    context.user_data['name'] = update.message.text
    update.message.reply_text("توضیح کوتاه محصول را وارد کنید:")
    return DESCRIPTION

def handle_description(update: Update, context: CallbackContext):
    context.user_data['description'] = update.message.text
    return ask_category(update, context)

def handle_category_choice(update: Update, context: CallbackContext):
    text = update.message.text
    if text == "➕ ساخت دسته‌بندی جدید":
        update.message.reply_text("نام دسته‌بندی جدید را وارد کنید:")
        return NEW_CATEGORY
    else:
        context.user_data["category_name"] = text
        update.message.reply_text("لطفاً عکس محصول را ارسال کنید:")
        return PRODUCT_IMAGE

def create_new_category(name):
    url = f"{WC_URL}/products/categories"
    data = {"name": name}
    response = requests.post(url, auth=(WC_KEY, WC_SECRET), json=data)
    return response.status_code == 201

def handle_new_category(update: Update, context: CallbackContext):
    category_name = update.message.text
    success = create_new_category(category_name)
    if success:
        context.user_data["category_name"] = category_name
        update.message.reply_text("دسته‌بندی با موفقیت ساخته شد. لطفاً عکس محصول را ارسال کنید:")
        return PRODUCT_IMAGE
    else:
        update.message.reply_text("ساخت دسته‌بندی با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
        return NEW_CATEGORY

def handle_photo(update: Update, context: CallbackContext):
    photo = update.message.photo[-1].get_file()
    photo_path = photo.download()

    # آپلود عکس به سایت
    media = {'file': open(photo_path, 'rb')}
    response = requests.post(f"{WC_URL}/media", auth=(WC_KEY, WC_SECRET), files=media)
    if response.status_code == 201:
        image_url = response.json()["source_url"]
    else:
        update.message.reply_text("ارسال عکس با خطا مواجه شد.")
        return ConversationHandler.END

    # ارسال اطلاعات محصول
    product_data = {
        "name": context.user_data['name'],
        "description": context.user_data['description'],
        "images": [{"src": image_url}],
        "categories": [{"name": context.user_data['category_name']}]
    }

    product_res = requests.post(f"{WC_URL}/products", auth=(WC_KEY, WC_SECRET), json=product_data)
    if product_res.status_code == 201:
        update.message.reply_text("✅ محصول با موفقیت ساخته شد!")
    else:
        update.message.reply_text("❌ خطا در ساخت محصول.")

    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("گفتگو لغو شد.")
    return ConversationHandler.END

def main():
    TOKEN = os.environ.get("BOT_TOKEN")
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, handle_name)],
            DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, handle_description)],
            CHOOSE_CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_category_choice)],
            NEW_CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_new_category)],
            PRODUCT_IMAGE: [MessageHandler(Filters.photo, handle_photo)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
