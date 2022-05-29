import uuid
import boto3
from boto3.dynamodb.conditions import Key
import logging
import sys
import json
from datetime import datetime, timedelta, timezone
import base64
import cv2
import numpy as np

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


EDIT_TABLE_NAME = "mosaic-dev-editpicture-table"
EDIT_BUCKET_NAME = 'mosaic-dev-resultimg-597775291172'
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
def base64_to_cv2(image_base64):
    """base64 image to cv2"""
    image_bytes = base64.b64decode(image_base64)
    np_array = np.fromstring(image_bytes, np.uint8)
    image_cv2 = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    return image_cv2


@log_decorator()
def cv2_to_base64(image_cv2):
    """cv2 image to base64"""
    image_bytes = cv2.imencode('.jpg', image_cv2)[1].tostring()
    image_base64 = base64.b64encode(image_bytes).decode()
    return image_base64


@log_decorator()
def check_limit(username, now):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(EDIT_TABLE_NAME)

    now_format = format(now, '%Y-%m')

    response = table.query(
        KeyConditionExpression=Key('username').eq(username) & Key('created_at').begins_with(now_format)
    )

    if len(response['Items']) < 5:
        return True
    else:
        return False


@log_decorator()
def create_record(username, created_at, post_id, img_title):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(EDIT_TABLE_NAME)

    table.put_item(
        Item={
            'username': username,
            'created_at': created_at,
            'uuid': post_id,
            'img_title': img_title,
            'is_delete': False,
            'status': "running"
        }
    )


@log_decorator()
def create_mosaic_img(img):
    cv_img = base64_to_cv2(img)
    base64_img = base64_to_cv2(cv_img)
    return base64_img


def post_image(img, key):

    s3_client = boto3.client('s3')
    data = base64.b64decode(img)

    s3_client.put_object(Bucket=SUBJECT_BUCKET_NAME, Key=key, Body=data)


def lambda_handler(event, context):

    logger.info(event)

    username = event["requestContext"]["authorizer"]["claims"]["cognito:username"]
    eventbody = json.loads(event["body"])

    img_title = eventbody["imgTitle"]
    img = eventbody['img']

    # タイムゾーンの生成
    JST = timezone(timedelta(hours=+9), 'JST')

    # GOOD, タイムゾーンを指定している．早い
    now = datetime.now(JST)

    # 5未満ならTrue
    is_continue = check_limit(username, now)

    if is_continue:

        img_id = str(uuid.uuid4())
        s3_post_key = "{}/{}.jpg".format(username, img_id)

        # stringに変更
        now_str = now.isoformat()

        create_record(username, now_str, img_id, img_title)

        try:
            data = create_mosaic_img(img)

            post_image(data, s3_post_key)

            res = {
                'status': 'OK',
                'message': 'mosaic successfully',
                'img': data
            }
        except Exception:
            res = {
                'status': 'Error',
                'message': 'mosaic Failed',
                'img': ''
            }

    else:
        res = {
            'status': 'NG',
            'message': 'Over regulation',
            'img': ''
        }

    return {
        'statusCode': 200,
        'body': json.dumps(res)
    }
