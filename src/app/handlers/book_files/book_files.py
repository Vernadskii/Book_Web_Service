import logging
from io import BytesIO

from aiohttp import web, web_request
from minio import Minio
from minio.error import S3Error


def check_object_exists(minio_client: Minio, bucket_name: str, object_name: str) -> bool:
    try:
        minio_client.stat_object(bucket_name, object_name)
    except S3Error:
        logging.debug(f"Object {object_name} does not exist in bucket {bucket_name}.")
        return False
    logging.debug(f"Object {object_name} already exists in bucket {bucket_name}.")
    return True


async def handle_upload(request: web_request.Request) -> web.Response:  # noqa: WPS210
    # TODO: Add checking that book (id) exists in SQL

    file_id = request.match_info['id']
    field = await (await request.multipart()).next()
    filename = field.filename  # type: ignore[union-attr, arg-type]
    minio_client = request.app["s3"]
    bucket_name = request.app["s3_bucket_name"]
    data_stream = BytesIO(await field.read())  # type: ignore[union-attr]
    data_size = data_stream.getbuffer().nbytes
    try:  # noqa: WPS229
        if check_object_exists(minio_client, bucket_name, file_id):
            return web.Response(text='File already exists!', status=409)

        minio_client.put_object(bucket_name=bucket_name, object_name=file_id, data=data_stream, length=data_size)
        return web.Response(text=f'Uploaded {filename} to {bucket_name}', status=201)
    except S3Error as err:
        return web.Response(text=f'Failed to upload {filename}: {err}')


async def handle_download(request: web_request.Request) -> web.Response:
    """Get book file from S3 storage."""
    file_id = request.match_info['id']
    if not file_id:
        return web.Response(status=400, text='Failed to resolve path. Id is needed')
    # TODO: check id in sql database, if there is no files there, then return 404
    try:
        body = read_file(request.app["s3"], request.app["s3_bucket_name"], file_id)
    except S3Error as err:
        return web.Response(status=404, text=f'Failed to retrieve file with ID {file_id}: {err}')
    response = web.Response(status=200, body=body)
    response.content_type = 'application/octet-stream'
    return response


def read_file(minio_client: Minio, bucket_name: str, object_name: str) -> bytes:
    data = minio_client.get_object(bucket_name, object_name)
    return data.read()
