import uuid
import boto3
from boto3.dynamodb.conditions import Key
import logging
import sys
import json
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
def check_limit(username):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(EDIT_TABLE_NAME)

    response = table.query(KeyConditionExpression=Key('username').eq(username))

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
