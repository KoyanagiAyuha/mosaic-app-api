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
def get_list(username):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('TABLE_NAME')

    response = table.query(
        KeyConditionExpression=Key('username').eq(username),
    )
    # 下記のwhile内で取得したレコードを連結するための箱（data）の準備
    data = response['Items']

    # レスポンスに LastEvaluatedKey が含まれなくなるまで無限ループ
    while 'LastEvaluatedKey' in response:
        response = table.query(
            KeyConditionExpression=Key('username').eq(username),
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        # dataにレコードを追加
        data.extend(response['Items'])

    return data


@log_decorator()
def lambda_handler(event, context):

    try:
        username = event["requestContext"]["authorizer"]["claims"]["cognito:username"]
        data = get_list(username)
        data = {
            "status": "OK",
            "payloads": data
        }
    except Exception:
        data = {
            "status": "NG"
        }

    # TODO implement
    return {
        'statusCode': 200,
        'isBase64Encoded': False,
        'body': json.dumps(data)
    }
