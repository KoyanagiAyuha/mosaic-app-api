import boto3
import logging
import sys
import json
import base64

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


EDIT_BUCKET_NAME = 'mosaic-dev-resultimg-597775291172'


@log_decorator()
def get_image(key):

    s3 = boto3.client('s3')

    try:
        body = s3.get_object(Bucket=EDIT_BUCKET_NAME, Key=key)['Body'].read()
    except Exception:
        return False, ''

    encode = base64.b64encode(body).decode()

    return True, encode


@log_decorator()
def lambda_handler(event, context):

    username = event["requestContext"]["authorizer"]["claims"]["cognito:username"]
    eventbody = json.loads(event["body"])

    img_id = eventbody['imgId']

    s3_key = "{}/{}.jpg".format(username, img_id)

    is_get, img = get_image(s3_key)

    if is_get:
        res = {
            "status": "OK",
            "message": "get Registered img successfully",
            "img": img
        }
    else:
        res = {
            "status": "NG",
            "message": "id not found",
            "img": img
        }

    return {
        'statusCode': 200,
        'body': json.dumps(res)
    }
