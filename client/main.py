from loguru import logger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from utiles.ehArchiveD import EHentai
from utiles.status import get_status
from config.config import config


def info_filter(record):
    return record["level"].name == "INFO"


logger.add("logs/info.log", rotation="5 MB", filter=info_filter)
logger.add("logs/error.log", rotation="5 MB", level="ERROR")

ehentai = EHentai(config["ehentai"]["cookies"], proxy=config["proxy"])

app = FastAPI()


@app.post("/parse")
async def parse(request: Request):
    try:
        data = await request.json()
        archiver_info = await ehentai.get_archiver_info(data["url"])
        require_gp = await ehentai.get_required_gp(archiver_info)
        if not config["ehentai"]["enable_GP_cost"] and require_gp > 0:
            msg = "Rejected"
            d_url = None
        else:
            d_url = await ehentai.get_download_url(archiver_info)
            msg = "Success"
        logger.info(f"{data['username']} 归档 {data['url']}  需要{require_gp}GP  {msg}")
        return JSONResponse(
            content={
                "msg": msg,
                "d_url": d_url,
                "require_gp": require_gp,
                "status": await get_status(ehentai),
            }
        )
    except Exception as e:
        logger.error(e)
        return JSONResponse(content={"msg": "Failed", "status": -1})


@app.post("/destroy")
async def destroy(request: Request):
    try:
        data = await request.json()
        archiver_info = await ehentai.get_archiver_info(data["url"])
        if await ehentai.remove_download_url(archiver_info):
            logger.info(f"{data['username']} 销毁 {data['url']}")
            return JSONResponse(content={"msg": "Success"})
    except Exception as e:
        logger.error(e)
    return JSONResponse(content={"msg": "Failed"})


@app.get("/status")
async def status():
    return JSONResponse(content={"status": await get_status(ehentai)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=None, port=4655)
