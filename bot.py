import asyncio
from telethon import TelegramClient, events
from binance.client import Client as BinanceClient
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

# Настройки Telegram
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

# Настройки Binance
binance_api_key = os.getenv('BINANCE_API_KEY')
binance_api_secret = os.getenv('BINANCE_API_SECRET')

# Инициализация клиентов
client = TelegramClient('bot', api_id, 
api_hash).start(bot_token=bot_token)
binance_client = BinanceClient(binance_api_key, binance_api_secret)

# Список для хранения сигналов
signals = []

# Словарь для хранения каналов, где бот является администратором
admin_channels = {}

# Функция для получения каналов, где бот является администратором
async def get_admin_channels():
    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            try:
                participant = await client.get_permissions(dialog, 
client.get_me())
                if participant.is_admin:
                    admin_channels[dialog.id] = dialog.title
            except Exception as e:
                print(f'Произошла ошибка при проверке прав в канале 
{dialog.title}: {str(e)}')

# Обработка команды /start
@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    await get_admin_channels()
    
    if admin_channels:
        channels_list = "\n".join([f"{title} (ID: {channel_id})" for 
channel_id, title in admin_channels.items()])
        await event.respond(f"Доступные каналы для 
работы:\n{channels_list}\n\nВведите /signal <SYMBOL> <ACTION> <LEVERAGE> 
<RM>, чтобы отправить сигнал.")
    else:
        await event.respond("Бот не является администратором ни в одном 
канале.")

# Обработка команды /signal
@client.on(events.NewMessage(pattern='/signal'))
async def signal(event):
    try:
        # Получение символа криптовалюты и других параметров
        message = event.message.text.split()
        symbol = message[1].upper()
        action = message[2].upper()  # BUY или SELL
        leverage = message[3]  # x20 КРОСС
        rm = message[4]  # 10% от баланса

        # Получение текущей рыночной цены
        current_price = 
float(binance_client.get_symbol_ticker(symbol=symbol)['price'])

        # Расчет входных значений
        entry_min = current_price * 0.995  # -0.5%
        entry_max = current_price * 1.005  # +0.5%
        entry_range = f"{entry_min:.2f} - {entry_max:.2f}"

        # Расчет тейк-профита
        if action == 'BUY':
            take_profit = current_price * 1.025  # +2.5% для лонга
            action_emoji = '⬆️'
        elif action == 'SELL':
            take_profit = current_price * 0.975  # -2.5% для шорта
            action_emoji = '⬇️'
        else:
            await event.respond('Неверный тип действия. Используйте BUY 
или SELL.')
            return

        # Форматирование сообщения
        signal_message = (
            f"{symbol}\n"
            f"{action}{action_emoji}\n\n"
            f"🔑 Входы: {entry_range}\n"
            f"💵 Плечо: {leverage}\n"
            f"❗️ РМ: {rm}\n"
            f"🎯 Тейк-профит: {take_profit:.2f}"
        )

        # Отправка сообщения в каждый канал, где бот является 
администратором
        for channel_id in admin_channels.keys():
            sent_message = await client.send_message(channel_id, 
signal_message)

            # Сохранение сигнала
            signals.append({
                'symbol': symbol,
                'action': action,  # Добавлено для проверки в check_prices
                'take_profit': take_profit,
                'message_id': sent_message.id,
                'channel_id': channel_id
            })

        await event.respond('Сигнал отправлен в каналы и добавлен для 
отслеживания!')
    except Exception as e:
        await event.respond(f'Произошла ошибка: {str(e)}')

# Функция для проверки цен и отправки уведомлений
async def check_prices():
    while True:
        for signal in signals:
            symbol = signal['symbol']
            take_profit = signal['take_profit']
            message_id = signal['message_id']
            channel_id = signal['channel_id']

            # Получение текущей цены
            current_price = 
float(binance_client.get_symbol_ticker(symbol=symbol)['price'])

            # Проверка, достигла ли цена тейк-профита
            if (signal['action'] == 'BUY' and current_price >= 
take_profit) или (signal['action'] == 'SELL' and current_price <= 
take_profit):
                # Отправка уведомления в канал с реплаем на сигнал
                await client.send_message(channel_id, f'Цель достигнута 
для {symbol}!', reply_to=message_id)
                # Удаление сигнала из списка
                signals.remove(signal)

        # Задержка между проверками (например, 10 секунд)
        await asyncio.sleep(10)

# Запуск функции проверки цен
client.loop.create_task(check_prices())

# Запуск бота
client.start()
client.run_until_disconnected()

