import configparser
import logging
import random

import feedparser

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
from telegram.ext import CommandHandler

from dictogram import Dictogram

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
conf = configparser.RawConfigParser()

END_OF_SENTENCE_CHARS = '.!?'
PUNCTUATION_MARKS_CHARS = ',;:-—–'
END = '.'
###########################
# режим генерации
USER_ACTION_CHOOSE_CATEGORY = 'choose category'
USER_ACTION_ENTER_TITLE = 'enter title'

ACTION_TYPES = (USER_ACTION_ENTER_TITLE, USER_ACTION_CHOOSE_CATEGORY)
############################
# категории новосте
CATEGORIES = {'Игры': 'https://news.yandex.ru/games.rss',
              'Интернет': 'https://news.yandex.ru/internet.rss',
              'Политика': 'https://news.yandex.ru/politics.rss',
              'Спорт': 'https://news.yandex.ru/sport.rss',
              'Коронавирус': 'https://news.yandex.ru/koronavirus.rss',
              'Кино': 'https://news.yandex.ru/movies.rss',
              'Проишествия': 'https://news.yandex.ru/incident.rss',
              'Главное': 'https://news.yandex.ru/index.rss'}

# stages
ENTER_TITLE_CREATION_OPTION, CHOOSE_CATEGORY, USER_ENTER_TITLE = range(3)


def start(update, context):
    logging.info("receive start command from {}".format(update.message.from_user.id))

    keyboard = [
        [InlineKeyboardButton("Выбрать категорию", callback_data=USER_ACTION_CHOOSE_CATEGORY)],
        [InlineKeyboardButton("Придумать свой заголовок новости", callback_data=USER_ACTION_ENTER_TITLE)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Вы можете получить свою сгенерированную новость из заголовков реальных новостей или '
                              'придумав собственный заголовок',
                              reply_markup=reply_markup)
    return ENTER_TITLE_CREATION_OPTION


def help(update, context):
    logging.info("receive help command from {}".format(update.message.from_user.id))
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="/start to start"
                                  "/help to help"
                                  "/info to get dev info")


def info(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Маскалева Мария 721701")


def resolve_user_enter_title(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Ввведите заголовок для новости которую вы хотите сгенерировать")
    return USER_ENTER_TITLE


def resolve_user_choose_category(update, context):
    query = update.callback_query
    query.answer()
    keyboard = []
    for category in CATEGORIES:
        keyboard.append([InlineKeyboardButton(text=category, callback_data=category)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text="Выберите категорию новостей",
        reply_markup=reply_markup
    )
    return CHOOSE_CATEGORY


def resolve_user_title(update, context):
    title = update.message.text
    return ENTER_TITLE_CREATION_OPTION


def resolve_category(update, context):
    query = update.callback_query
    query.answer()
    category = query.data
    logging.info("user want generate news for " + category + "category")
    titles = get_titles_for_category(category)
    generatedTitle = generate_markov_title(titles)
    query.edit_message_text(text=generatedTitle)
    return ENTER_TITLE_CREATION_OPTION


# TODO загрузка новостей по загрузке бота
def get_titles_for_category(category):
    newsFeed = feedparser.parse(CATEGORIES[category])
    titles = []
    for entry in newsFeed.entries:
        titles.append(entry.title)
    return titles


def generate_markov_title(titles):
    words = []
    for title in titles:
        title_words = title.split(' ')
        words.append(END)
        for word in title_words:
            word = word.strip(PUNCTUATION_MARKS_CHARS)
            if word.endswith('.') or word.endswith('?') or word.endswith('!'):
                word = word.strip(END_OF_SENTENCE_CHARS)
                words.append(word)
                words.append(END)
            else:
                words.append(word)

    markov_model = make_markov_model(words)
    sentence = generate_random_sentence(10, markov_model)
    return sentence


def make_markov_model(data):
    markov_model = dict()
    window_length = int(conf['markov']['window'])
    for i in range(0, len(data) - window_length):
        # Создаем окно
        window = tuple((data[i: i + window_length]))
        # Добавляем в словарь
        if window in markov_model:
            # Присоединяем к уже существующему распределению
            markov_model[window].update([data[i + window_length]])
        else:
            markov_model[window] = Dictogram([data[i + window_length]])
    return markov_model


def generate_random_start(model):
    # Чтобы сгенерировать "правильное" начальное слово, используйте код ниже:
    # Правильные начальные слова - это те, что являлись началом предложений в корпусе
    start_windows = []
    for win in model:
        if win[0] is END:
            win = shiftWindow(win, model[win].return_weighted_random_word())
            start_windows.append(win)
    return random.choice(start_windows)


def generate_random_sentence(length, markov_model):
    current_win = generate_random_start(markov_model)
    sentence = [current_win[0]]
    for i in range(0, length):
        current_dictogram = markov_model[current_win]
        random_weighted_word = current_dictogram.return_weighted_random_word()
        current_win = shiftWindow(current_win, random_weighted_word)
        sentence.append(random_weighted_word)
    sentence[0] = sentence[0].capitalize()
    return ' '.join(sentence) + END


def shiftWindow(window, nextWord):
    list_win = list(window)
    list_win = list_win[1:]
    list_win.append(nextWord)
    tutuple = ('Захарова',)
    current_win = tuple(list_win)
    return current_win


def main():
    conf.read("config.ini")

    token = conf['telegram']['token']
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('help', help))
    dispatcher.add_handler(CommandHandler('info', info))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ENTER_TITLE_CREATION_OPTION: [CallbackQueryHandler(resolve_user_choose_category,
                                                               pattern=USER_ACTION_CHOOSE_CATEGORY),
                                          CallbackQueryHandler(resolve_user_enter_title,
                                                               pattern=USER_ACTION_ENTER_TITLE)],
            CHOOSE_CATEGORY: [CallbackQueryHandler(resolve_category)],
            USER_ENTER_TITLE: [MessageHandler(Filters.text, callback=resolve_user_title)]
        },
        fallbacks=[CommandHandler('start', start)]
    )

    dispatcher.add_handler(conv_handler)
    updater.start_polling()


if __name__ == '__main__':

    main()
