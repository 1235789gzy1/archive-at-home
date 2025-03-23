from pyrogram import Client, filters
from pyrogram.types import Message


@Client.on_message(filters.command("start"))
async def start(_, msg: Message):
    await msg.reply("请发送画廊链接,不支持单图链接,\n归档链接 2 小时后自动销毁，生成后请尽快下载 \n下载请点击按钮,json为画廊元数据 \n速率限制以提示为准")


@Client.on_message(filters.command("help"))
async def help_(_, msg: Message):
    await msg.reply("直接发送画廊链接给我,我会返回画廊元数据(文件)和归档下载链接(按钮) \n<i>(某些情况下可能会发送下载好的压缩包)</i>. \n归档链接受到EH <b>两个IP</b> 限制,下载过程中请 <b>不要切换IP</b> 遇到意外情况可以点击 <u>销毁链接</u> 后重新发送画廊链接<i>(计入当日限额)</i>. \n<b>归档链接任何人都可以销毁，请生成后尽快下载</b> \n<u><i>为防止滥用，存在每日请求限制</i></u>")
