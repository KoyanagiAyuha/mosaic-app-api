
import boto3
import logging
import sys
import uuid
import json
import base64
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta, timezone

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

SUBJECT_BUCKET_NAME = 'mosaic-dev-registerimg-597775291172'
SUBJECT_TABLE_NAME = 'mosaic-dev-registerpic-table'


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


@log_decorator()
def put_posts(username, created_at, postid, img_title):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(SUBJECT_TABLE_NAME)

    table.put_item(
        Item={
            'username': username,
            'created_at': created_at,
            'uuid': postid,
            'img_title': img_title
        }
    )


@log_decorator()
def post_image(img, key):

    s3_client = boto3.client('s3')
    data = base64.b64decode(img)

    s3_client.put_object(Bucket=SUBJECT_BUCKET_NAME, Key=key, Body=data)


@log_decorator()
def check_limit(username):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(SUBJECT_TABLE_NAME)

    response = table.query(KeyConditionExpression=Key('username').eq(username))

    if len(response['Items']) < 5:
        return True
    else:
        return False


def lambda_handler(event, context):

    username = event["requestContext"]["authorizer"]["claims"]["cognito:username"]
    eventbody = event["body"]

    img_title = eventbody["imgTitle"]
    img = eventbody['img']

    # 5未満ならTrue
    is_continue = check_limit(username)

    if is_continue:

        img_id = str(uuid.uuid4())
        s3_post_key = "{}/{}.jpg".format(username, img_id)

        # タイムゾーンの生成
        JST = timezone(timedelta(hours=+9), 'JST')

        # GOOD, タイムゾーンを指定している．早い
        now = datetime.now(JST)
        # エポックミリ秒に変換
        created_at = int(now.timestamp() * 1000)

        post_image(img, s3_post_key)

        put_posts(username, created_at, img_id, img_title)

        res = {
            'status': 'OK',
            'message': 'Registered successfully'
        }

    else:
        res = {
            'status': 'NG',
            'message': 'Over regulation'
        }

    return {
        'statusCode': 200,
        'body': json.dumps(res)
    }
