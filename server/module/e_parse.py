import os
import httpx
import asyncio
import random
from urllib.parse import urljoin
from datetime import datetime
from limits import user_limiters, global_limiter, user_locks

from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup as Ikm,
    InlineKeyboardButton as Ikb,
    CallbackQuery,
)
from config.config import e_cfg, get_server_list
from utiles.filter import is_admin
from utiles.parse_count import parse_count
from utiles.utile import is_admin_, rate_limit
from apscheduler.schedulers.asyncio import AsyncIOScheduler


client = httpx.AsyncClient()

servers = get_server_list()


async def fetch_status(server):
    try:
        response = await client.get(urljoin(server["url"], "/status"), timeout=30)
        server["status"] = response.json()["status"]
    except Exception as e:
        logger.error(e)
        server["status"] = -1
    logger.info(server)


async def scheduled_task():
    tasks = [fetch_status(server) for server in servers]
    await asyncio.gather(*tasks)


scheduler = AsyncIOScheduler()
scheduler.add_job(scheduled_task, "interval", hours=1, next_run_time=datetime.now())
scheduler.start()


@Client.on_message(
    filters.regex(r"https://(?:e-|ex)hentai.org/g/(\d+)/([a-f0-9]+)") & filters.private
)
@rate_limit(
    request_limit=e_cfg.request_limit,
    time_limit=e_cfg.time_limit,
    total_request_limit=e_cfg.total_request_limit,
)
@logger.catch
async def ep(_, msg: Message):
    user_id = msg.from_user.id

    # 检查功能禁用状态
    if e_cfg.disable and not is_admin_(user_id):
        return await msg.reply("解析功能暂未开放")

    user_limiter = user_limiters[user_id]

    # 全局与用户限流检查
    if not global_limiter.has_capacity():
        return await msg.reply("当前请求人数过多，请稍后再试。")

    if not user_limiter.has_capacity():
        return await msg.reply(f"你已达到每分钟请求上限，请稍后再试。")

    async with global_limiter, user_limiter:
        lock = user_locks[user_id]

        if lock.locked():
            return await msg.reply("你有一个任务正在处理中，请完成后再试。")

        async with lock:
            m = await msg.reply("解析中...")
            try:
                erp = await ehentai_parse(msg.from_user.full_name, msg.text)
            except Exception as e:
                await m.edit(f"解析失败：{type(e).__name__}, 错误信息：{e}")
                raise e

            btn = Ikm(
                [
                    [
                        Ikb("下载", url=erp[0]),
                        Ikb("销毁下载", callback_data=f"cancel_{msg.text}_{erp[2]}"),
                    ]
                ]
            )

            if e_cfg.destroy_regularly:
                await destroy_regularly(erp[2], msg.from_user.full_name, msg.text)

            await msg.reply(
                f"解析成功，服务提供者{erp[2]}", quote=True, reply_markup=btn
            )
            await m.delete()

            uc = parse_count.get_counter(user_id)
            uc.add_count(erp[1])
            logger.info(
                f"{msg.from_user.full_name} 归档 {msg.text} "
                f"(今日 {uc.day_count} 个) "
                f"(消耗 {f'{erp[1]} GP' if erp[1] else '免费'})"
            )


def get_avaliable_servers():
    servers_1 = [s for s in servers if s["status"] == 1]
    servers_0 = [s for s in servers if s["status"] == 0]
    random.shuffle(servers_1)
    random.shuffle(servers_0)
    return servers_1 + servers_0


def get_server_by_provider(provider):
    return next((s for s in servers if s["provider"] == provider))


def update_server(provider, new_values):
    server = get_server_by_provider(provider)
    server.update(new_values)


async def ehentai_parse(username: str, url: str):
    for s in get_avaliable_servers():
        try:
            res = await client.post(
                urljoin(s["url"], "/parse"),
                json={"username": username, "url": url},
                timeout=300,
            )
            res_json = res.json()
            update_server(s["provider"], {"status": res_json["status"]})
            if res_json["msg"] == "Success":
                return res_json["d_url"], res_json["require_gp"], s["provider"]
        except Exception as e:
            update_server(s["provider"], {"status": -1})
    raise NoAvailableServerError


async def cancel_download(provider: str, username: str, url: str) -> bool:
    server = get_server_by_provider(provider)
    try:
        res = await client.post(
            urljoin(server["url"], "/destroy"),
            json={"username": username, "url": url},
            timeout=30,
        )
        res_json = res.json()
        if res_json["msg"] == "Success":
            return True
    except:
        pass
    return False


@Client.on_callback_query(filters.regex(r"^cancel_"))
async def cancel_dl(_, cq: CallbackQuery):
    url, provider = cq.data.split("_")[1:3]
    logger.info(f"{cq.from_user.full_name} 销毁 {url}")
    if not (await cancel_download(provider, cq.from_user.full_name, url)):
        await cq.answer("销毁下载失败")
        s = "失败"
    else:
        await cq.message.edit_reply_markup()
        await cq.answer("已销毁下载")
        s = "成功"
    logger.info(f"{cq.from_user.full_name} 创建的 {url} 销毁{s}")


@Client.on_message(filters.command("count") & is_admin)
async def count(_, msg: Message):
    await msg.reply(
        f"今日解析次数: __{parse_count.get_all_count()}__\n今日消耗GP: __{parse_count.get_all_gp()}__"
    )


@Client.on_message(filters.command("refresh_client") & is_admin)
async def count(_, msg: Message):
    global servers
    servers = get_server_list()
    await scheduled_task()
    await msg.reply(str(servers))


async def destroy_regularly(provider: str, username: str, url: str):
    """定时销毁下载"""
    scheduler.add_job(
        cancel_download,
        "interval",
        args=[provider, username, url],
        seconds=e_cfg.destroy_regularly,
    )


class NoAvailableServerError(Exception):
    def __init__(self):
        self.message = "无可用服务器，请稍后再试"
        super().__init__(self.message)
