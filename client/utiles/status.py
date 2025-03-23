import re
import httpx
from loguru import logger
from config.config import config


res = httpx.get("https://e-hentai.org/", proxy=config["proxy"])
test_url = re.search(r"https://e-hentai\.org/g/[0-9]+/[0-9a-z]+", res.text).group()


# -1：不可用 0：可用但无免费额度 1：可用且有免费额度
async def get_status(ehentai):
    try:
        archiver_info = await ehentai.get_archiver_info(test_url)
        require_gp = await ehentai.get_required_gp(archiver_info)
        if require_gp == 0:
            return 1
        return 0
    except Exception as e:
        logger.error(e)
        return -1
