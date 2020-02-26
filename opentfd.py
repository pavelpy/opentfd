import asyncio
import getopt
import sys
from contextlib import suppress
from time import time

import mtranslate
from telethon import TelegramClient, events, errors, custom
from telethon.tl.types import UpdateDraftMessage

import secret
from proxy import mediatube_proxy
from supported_langs import supported_langs

default_proxy = None
try:
    opts, args = getopt.getopt(sys.argv[1:], 'p', ['proxy'])
    for opt, arg in opts:
        if opt in ('-p', '--proxy'):
            default_proxy = mediatube_proxy
except getopt.GetoptError:
    sys.exit(2)

client = TelegramClient('opentfd_session', secret.api_id, secret.api_hash, proxy=default_proxy).start()
last_msg = None
break_time = None
last_msg_time = time()
MERGE_TIMEOUT = 30
merge_semaphore = asyncio.Semaphore(value=1)
draft_semaphore = asyncio.Semaphore(value=1)


@client.on(events.Raw(types=UpdateDraftMessage))
async def translator(event: events.NewMessage.Event):
    global draft_semaphore
    await draft_semaphore.acquire()
    try:
        draft_list = await client.get_drafts()
        for draft in draft_list:
            if draft.is_empty:
                continue
            text = draft.text
            for lang_code in supported_langs.values():
                if text.endswith('/{0}'.format(lang_code)):
                    translated = mtranslate.translate(text[:-(len(lang_code) + 1)], lang_code, 'auto')
                    for i in range(3):
                        try:
                            await draft.set_message(text=translated)
                            await asyncio.sleep(7)
                            return
                        except Exception as e:
                            print(e)
    except Exception as e:
        print(e)
    finally:
        draft_semaphore.release()


@client.on(events.NewMessage(pattern=r'^!type->.*', outgoing=True))
async def typing_imitate(message: events.NewMessage.Event):
    text, text_out = str(message.raw_text).split('->')[-1], str()
    word = list(text)
    with suppress(Exception):
        for letter in word:
            text_out += letter
            try:
                if word.index(letter) % 2 == 1:
                    await message.edit(f'`{text_out}`|')
                else:
                    await message.edit(f'`{text_out}`')
                await asyncio.sleep(0.2)
            except errors.MessageNotModifiedError:
                continue


@client.on(events.NewMessage(incoming=True))
async def break_updater(event: events.NewMessage.Event):
    global break_time
    global last_msg
    with suppress(Exception):
        if event.chat:
            if event.chat.bot:
                return
    if last_msg:
        try:
            if (event.message.to_id.user_id == last_msg.from_id and
                    last_msg.to_id.user_id == event.message.sender_id):
                break_time = time()
        except Exception:
            if event.to_id == last_msg.to_id:
                break_time = time()


@client.on(events.NewMessage(outgoing=True))
async def merger(event: custom.Message):
    global last_msg
    global break_time
    global last_msg_time
    global merge_semaphore

    event_time = time()
    with suppress(Exception):
        with suppress(Exception):
            if event.chat:
                if event.chat.bot:
                    return
        if (event.media or event.fwd_from or event.via_bot_id or
                event.reply_to_msg_id or event.reply_markup):
            last_msg = None
        elif last_msg is None:
            last_msg = event
        elif last_msg.to_id == event.to_id:
            if break_time:
                if break_time < event_time:
                    last_msg = event
                    last_msg_time = event_time
                    break_time = 0
            elif event_time - last_msg_time < MERGE_TIMEOUT:
                try:
                    await merge_semaphore.acquire()
                    last_msg = await last_msg.edit('{0} {1}'.format(last_msg.text, event.text))
                    last_msg_time = event_time
                    await event.delete()
                finally:
                    merge_semaphore.release()
            else:
                last_msg = event
                last_msg_time = event_time
        else:
            last_msg = event
            last_msg_time = event_time


final_credits = ["OpenTFD is running", "Do not close this window", "t.me/mediatube_stream",
                 "https://github.com/mediatube/opentfd\n", "Supported languages:", ''
                 ]

print('\n'.join(final_credits))
print('\n'.join([f'{k:<25}/{v}' for k, v in supported_langs.items()]))
client.run_until_disconnected()
