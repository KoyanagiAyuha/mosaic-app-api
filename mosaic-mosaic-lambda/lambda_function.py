import os
import boto3
from boto3.dynamodb.conditions import Key
import logging
import sys
from typing import Union
import traceback
import json

# 既存ロガーハンドラーの削除
default_logger = logging.getLogger()
for h in default_logger.handlers:
    default_logger.removeHandler(h)
logger = logging.getLogger(__name__)
# ルートロガー設定
logger.setLevel(logging.DEBUG)
# コンソール出力用のハンドラー
to_stream = logging.StreamHandler(stream=sys.stdout)
# ハンドラーごとの出力レベル定義
to_stream.setLevel(logging.DEBUG)
# 引数:fmtにformatterを渡す＆時刻の書式を好みの形になるように引数:datefmtへ
log_format = logging.Formatter("%(levelname)s - %(filename)s - %(funcName)s - %(message)s")
# それぞれのハンドラへformatterをセットしてやる
to_stream.setFormatter(log_format)
# ロガーへハンドラーを追加する
logger.addHandler(to_stream)


def log_decorator():
    def _log_decorator(func):
        def wrapper(*args, **kwargs):
            try:
                logger.info('{}関数の処理を開始します'.format(func.__name__))
                return func(*args, **kwargs)

            except Exception as e:
                raise e

            finally:
                logger.info('{}関数の処理を終了します'.format(func.__name__))

        return wrapper

    return _log_decorator


def put_posts(title, username, imglist, created_on, postid):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ.get('DB_TABLE'))

    table.put_item(
        Item={
            'userPost': username,
            'title': title,
            'img': imglist,
            'created_on': created_on,
            'id': postid,
            'timestamp': ""
        }
    )


def post_image(img, key):

    s3 = boto3.resource('s3')
    bucket = s3.Bucket(os.environ.get('DB_TABLE'))

    bucket.upload_file(img, key)


def lambda_handler(event, context):

    username = event["requestContext"]["authorizer"]["claims"]["cognito:username"]
    eventbody = json.loads(event["body"])

    title = eventbody["title"]
    imglist = eventbody['img']

    # GOOD, タイムゾーンを指定している．早い
    timestamp = created_on.timestamp()
    created_on_str = created_on.strftime('%Y-%m-%d %H:%M:%S')
    postimg_name = []
    postid = str(uuid.uuid4())
    for i, img in enumerate(imglist):
        encode_file = '/tmp/tmp' + ext
        with open(encode_file, "wb") as f:
            f.write(encode)
        key = postid + '/' + str(i) + ext
        postimg_name.append(key)
        post_image(encode_file, key)

    put_posts(title, username, postimg_name, created_on_str, postid, timestamp)

    # TODO implement
    return {
        'statusCode': 200,
        'body': "OK"
    }
