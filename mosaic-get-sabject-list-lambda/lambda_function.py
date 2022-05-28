import os
import boto3
from boto3.dynamodb.conditions import Key
import logging
import sys
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
def get_subject_list(username):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ.get('DB_TABLE'))

    response = table.query(KeyConditionExpression=Key('username').eq(username))

    return response


@log_decorator()
def lambda_handler(event, context):

    logger.info(event)

    username = event["requestContext"]["authorizer"]["claims"]["cognito:username"]

    subject_list = get_subject_list(username)

    res = {
        'status': 'OK',
        'message': 'get Registered img successfully',
        'data': subject_list
    }

    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps(res)
    }
