import asyncio
from datetime import datetime
import time
import logging
import io
import traceback
import json

from bot import alemiBot

from pyrogram import filters

from util.permission import is_allowed, is_superuser
from util.command import filterCommand
from util.message import edit_or_reply, is_me
from util.user import get_username
from plugins.help import HelpCategory

logger = logging.getLogger(__name__)

HELP = HelpCategory("CORE")

HELP.add_help(["asd", "ping"], "a sunny day!",
                "The ping command.", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["asd", "ping"], list(alemiBot.prefixes)))
async def ping(client, message):
    logger.info("Pong")
    before = time.time()
    msg = await edit_or_reply(message, "` → ` a sunny day")
    after = time.time()
    latency = (after - before) * 1000
    await msg.edit(f"` → ` a sunny day `({latency:.0f}ms)`")

HELP.add_help(["joined", "jd"], "count active chats",
                "get number of all dialogs : groups, supergroups, channels, dms, bots")
@alemiBot.on_message(is_superuser & filterCommand(["joined", "jd"], list(alemiBot.prefixes)))
async def joined_cmd(client, message):
    logger.info("Listing active dialogs")
    msg = await edit_or_reply(message, "` → ` Counting...")
    res = {}
    async for dialog in client.iter_dialogs():
      if dialog.chat.type in res:
        res[dialog.chat.type] += 1
      else:
        res[dialog.chat.type] = 1
    out = "`→ ` --Active chats-- \n"
    for k in res:
        out += f"` → {k} ` {res[k]}\n"
    await msg.edit(out)

HELP.add_help("update", "update and restart",
                "will pull changes from git (`git pull`), install requirements (`pip install -r requirements.txt --upgrade`) " +
                "and then restart process with an `execv` call. If nothing gets pulled from `git`, update will stop unless " +
                "the `-force` flag was given.", args="[-force]")
@alemiBot.on_message(is_superuser & filterCommand("update", list(alemiBot.prefixes), flags=["-force", "-sub"]))
async def update(client, message):
    out = message.text.markdown if is_me(message) else f"`→ ` {get_username(message.from_user)} requested update"
    msg = message if is_me(message) else await message.reply(out)
    try:
        logger.info(f"Updating bot ...")
        uptime = str(datetime.now() - client.start_time)
        out += f"\n`→ ` --runtime-- `{uptime}`"
        await msg.edit(out) 
        out += "\n` → ` Fetching updates"
        await msg.edit(out)
        proc = await asyncio.create_subprocess_exec(
            "git", "pull",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
        stdout, stderr = await proc.communicate()
        sub_proc = await asyncio.create_subprocess_exec(
            "git", "submodule", "update", "--remote",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
        sub_stdout, sub_stderr = await sub_proc.communicate()
        sub_count = sub_stdout.count(b"checked out")
        if b"Aborting" in stdout:
            out += " [`FAIL`]\n"
            if "-force" not in message.command["flags"]:
                return await msg.edit(out)
        elif b"Already up to date" in stdout:
            out += " [`N/A`]\n"
            if sub_count < 1 and "-force" not in message.command["flags"]:
                return await msg.edit(out)
        else:
            out += " [`OK`]\n"
        if sub_count > 0:
            out += f"`  → ` Submodule{'s' if sub_count > 1 else ''} [`{sub_count}`]\n"
        out += "` → ` Checking libraries"
        await msg.edit(out) 
        proc = await asyncio.create_subprocess_exec(
            "pip", "install", "-r", "requirements.txt", "--upgrade",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
        stdout, stderr = await proc.communicate()
        if b"ERROR" in stdout:
            out += " [`WARN`]"
        else:
            out += f" [`{stdout.count(b'Collecting')} new`]"
        out += "\n` → ` Restarting process"
        await msg.edit(out) 
        with open("data/lastmsg.json", "w") as f:
            json.dump({"message_id": msg.message_id,
                        "chat_id": msg.chat.id}, f)
        asyncio.get_event_loop().create_task(client.restart())
    except Exception as e:
        traceback.print_exc()
        out += " [FAIL]\n`[!] → ` " + str(e)
        await msg.edit(out) 

HELP.add_help("where", "get info about chat",
                "Get complete information about a chat and send it as json. If no chat name " +
                "or id is specified, current chat will be used. Add `-no` at the end if you just want the " +
                "id : no file will be attached.", args="[<target>] [-no]", public=True)
@alemiBot.on_message(is_allowed & filterCommand("where", list(alemiBot.prefixes), flags=["-no"]))
async def where_cmd(client, message):
    try:
        tgt = message.chat
        if "cmd" in message.command:
            arg = message.command["cmd"][0]
            if arg.isnumeric():
                tgt = await client.get_chat(int(arg))
            else:
                tgt = await client.get_chat(arg)
        logger.info(f"Getting info of chat")
        await edit_or_reply(message, f"` → ` Getting data of chat `{tgt.id}`")
        if not "-no" in message.command["flags"]:
            out = io.BytesIO((str(tgt)).encode('utf-8'))
            out.name = f"chat-{message.chat.id}.json"
            await client.send_document(message.chat.id, out)
    except Exception as e:
        traceback.print_exc()
        await edit_or_reply(message,"`[!] → ` " + str(e))
    await client.set_offline()

HELP.add_help("who", "get info about user",
                "Get complete information about user and attach as json. If replying to a message, author will be used. " +
                "An id or @ can be specified. If neither is applicable, self will be used. Append `-no` if you just want the id.",
                public=True, args="[<target>] [-no]")
@alemiBot.on_message(is_allowed & filterCommand("who", list(alemiBot.prefixes), flags=["-no"]))
async def who_cmd(client, message):
    try:
        peer = None
        if "cmd" in message.command:
            arg = message.command["cmd"][0]
            if arg.isnumeric():
                peer = await client.get_users(int(arg))
            else:
                peer = await client.get_users(arg)
        elif message.reply_to_message is not None \
        and message.reply_to_message.from_user is not None:
            peer = message.reply_to_message.from_user
        else:
            peer = await client.get_me()
        logger.info("Getting info of user")
        await edit_or_reply(message, f"` → ` Getting data of user `{peer.id}`")
        if not "-no" in message.command["flags"]:
            out = io.BytesIO((str(peer)).encode('utf-8'))
            out.name = f"user-{peer.id}.json"
            await client.send_document(message.chat.id, out)
    except Exception as e:
        traceback.print_exc()
        await edit_or_reply(message, "`[!] → ` " + str(e))
    await client.set_offline()

HELP.add_help("what", "get info about message",
                "Get complete information about a message and attach as json. If replying, replied message will be used. "+
                "id and chat can be passed as arguments. If no chat is specified with `-g`, " +
                "message will be searched in current chat. Append `-no` if you just want the id.",
                args="[<target>] [-g <chatId>] [-no]", public=True)
@alemiBot.on_message(is_allowed & filterCommand("what", list(alemiBot.prefixes), options={
    "group" : ["-g", "-group"]
}, flags=["-no"]))
async def what_cmd(client, message):
    msg = message
    try:
        if message.reply_to_message is not None:
            msg = await client.get_messages(message.chat.id, message.reply_to_message.message_id)
        elif "cmd" in message.command and message.command["cmd"][0].isnumeric():
            chat_id = message.chat.id
            if "group" in message.command:
                if message.command["group"].isnumeric():
                    chat_id = int(message.command["group"])
                else:
                    chat_id = (await client.get_chat(message.command["group"])).id
            msg = await client.get_messages(chat_id, int(message.command["cmd"][0]))
        logger.info("Getting info of msg")
        await edit_or_reply(message, f"` → ` Getting data of msg `{msg.message_id}`")
        if not "-no" in message.command["flags"]:
            out = io.BytesIO((str(msg)).encode('utf-8'))
            out.name = f"msg-{msg.message_id}.json"
            await client.send_document(message.chat.id, out)
    except Exception as e:
        traceback.print_exc()
        await edit_or_reply(message,"`[!] → ` " + str(e))
    await client.set_offline()
