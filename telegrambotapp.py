import configparser
import logging
import random

import feedparser

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
from telegram.ext import CommandHandler

import gpt_2_simple as gpt2

from dictogram import Dictogram

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
conf = configparser.RawConfigParser()

news = {}
category_models ={}

sess = gpt2.start_tf_sess()
run_name = 'news_s'

END_OF_SENTENCE_CHARS = '.!?'
PUNCTUATION_MARKS_CHARS = ',;:-—–'
END = '.'
###########################
# режим генерации
USER_ACTION_CHOOSE_CATEGORY = 'choose category'
USER_ACTION_ENTER_TITLE = 'enter title'
USER_ACTION_CHOOSE_GEN_TITLE ='gen title'

ACTION_TYPES = (USER_ACTION_ENTER_TITLE, USER_ACTION_CHOOSE_CATEGORY,USER_ACTION_CHOOSE_GEN_TITLE)
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
        [InlineKeyboardButton("Придумать свой заголовок новости", callback_data=USER_ACTION_ENTER_TITLE)],
        [InlineKeyboardButton("Получить рандомный заголовок", callback_data=USER_ACTION_CHOOSE_GEN_TITLE)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Вы можете получить свою сгенерированную новость из заголовков реальных новостей или '
                              'придумав собственный заголовок',
                              reply_markup=reply_markup)
    return ENTER_TITLE_CREATION_OPTION


def help(update, context):
    logging.info("receive help command from {}".format(update.message.from_user.id))
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="/start to start \n"
                                  "/help to help \n"
                                  "/info to get dev info \n")


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

def gen_random_title(update, context):
    category = 'Главное'
    query = update.callback_query
    query.answer()
    generated_title = generate_markov_title_for_category(category)
    query.edit_message_text(
        text=generated_title
    )
    return ENTER_TITLE_CREATION_OPTION

def resolve_user_title(update, context):
    title = update.message.text
    generated_text = generate_text(title)
    msg_text = title + '\n\n' + generated_text
    update.message.reply_text(text=msg_text)
    return ENTER_TITLE_CREATION_OPTION


def resolve_category(update, context):
    query = update.callback_query
    query.answer()
    category = query.data
    logging.info("user wants generate news for " + category + "category")
    generated_title = generate_markov_title_for_category(category)
    generated_text = generate_text(generated_title)
    msg_text = generated_title + '\n\n' + generated_text
    query.edit_message_text(text=msg_text)
    return ENTER_TITLE_CREATION_OPTION


def load_news():
    global news
    for category in CATEGORIES:
        newsFeed = feedparser.parse(CATEGORIES[category])
        category_news = []
        for entry in newsFeed.entries:
            category_news.append(entry.description)
        news[category] = category_news


def parse_words(text_arr):
    words = []
    words.append(END)
    for title in text_arr:
        title_words = title.split(' ')
        for word in title_words:
            word = word.strip(PUNCTUATION_MARKS_CHARS)
            if word.endswith('.') or word.endswith('?') or word.endswith('!'):
                word = word.strip(END_OF_SENTENCE_CHARS)
                words.append(word)
                words.append(END)
            else:
                words.append(word)
    return words


def generate_markov_title_for_category(category):
    markov_model = category_models[category]
    markov_title = generate_random_sentence(20, markov_model)
    dot = markov_title.rfind(".")
    markov_title = markov_title[:dot]
    return markov_title


def generate_markov_title(titles):
    words = parse_words(titles)
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
    # Правильные начальные слова - это те, что являлись началом предложений в корпусе
    start_windows = []
    for win in model:
        if win[0] is END:
            win = shift_window(win, model[win].return_weighted_random_word())
            start_windows.append(win)
    return random.choice(start_windows)


def generate_random_sentence(length, markov_model):
    current_win = generate_random_start(markov_model)
    sentence = [current_win[0]]
    for i in range(0, length):
        current_dictogram = markov_model[current_win]
        random_weighted_word = current_dictogram.return_weighted_random_word()
        current_win = shift_window(current_win, random_weighted_word)
        sentence.append(random_weighted_word)
    sentence[0] = sentence[0].capitalize()
    return ' '.join(sentence) + END


def shift_window(window, next_word):
    list_win = list(window)
    list_win = list_win[1:]
    list_win.append(next_word)
    current_win = tuple(list_win)
    return current_win


def load_gpt():
    global run_name, sess
    run_name = conf['gpt2']['run_name']
    sess = gpt2.start_tf_sess()
    gpt2.load_gpt2(sess, run_name=run_name)


def generate_text(title):
    gpt2.tf.reset_default_graph()
    run_name = conf['gpt2']['run_name']
    sess = gpt2.start_tf_sess()
    gpt2.load_gpt2(sess, run_name=run_name)
    generated_text = gpt2.generate(sess,
                          run_name=run_name,
                          prefix=title,
                          length=300,
                          include_prefix=False,
                          return_as_list=True)[0]
    dot = generated_text.rfind('.');
    return generated_text[:dot]


def generate_markov_models():
    for news_category in news:
        words = parse_words(news[news_category])
        category_markov_model = make_markov_model(words)
        category_models[news_category] = category_markov_model


def main():
    conf.read("config.ini")
    load_news()
    generate_markov_models()
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
                                                               pattern=USER_ACTION_ENTER_TITLE),
                                          CallbackQueryHandler(gen_random_title,
                                                               pattern=USER_ACTION_CHOOSE_GEN_TITLE)
                                          ],
            CHOOSE_CATEGORY: [CallbackQueryHandler(resolve_category)],
            USER_ENTER_TITLE: [MessageHandler(Filters.text, callback=resolve_user_title)]
        },
        fallbacks=[CommandHandler('start', start)]
    )

    dispatcher.add_handler(conv_handler)
    updater.start_polling()


if __name__ == '__main__':
    main()
