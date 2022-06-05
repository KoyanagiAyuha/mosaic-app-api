import boto3
import logging
from boto3.dynamodb.conditions import Key
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


EDIT_TABLE_NAME = "mosaic-dev-editpicture-table"
EDIT_BUCKET_NAME = 'mosaic-dev-resultimg-597775291172'


@log_decorator()
def update_recode(username, img_id):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(EDIT_TABLE_NAME)

    response = table.query(
        IndexName='uuid-index',
        KeyConditionExpression=Key('uuid').eq(img_id)
    )['Items']

    if len(response) == 1 and not response[0]['is_delete']:
        created_at = response[0]['created_at']

        table.update_item(
            Key={'username': username, 'created_at': created_at},
            UpdateExpression="set #st=:s",
            ExpressionAttributeNames={
                '#st': 'is_delete',
            },
            ExpressionAttributeValues={
                ':s': True,
            }
        )

        return {'status': 'OK',
                'message': 'delete Registered img successfully'}
    return {'status': 'NG',
            'message': 'id not found'}


@log_decorator()
def delete_image(key):
    s3 = boto3.client('s3')

    s3.delete_object(Bucket=EDIT_BUCKET_NAME, Key=key)


@log_decorator()
def lambda_handler(event, context):

    username = event["requestContext"]["authorizer"]["claims"]["cognito:username"]
    eventbody = json.loads(event["body"])

    img_id = eventbody["imgId"]

    s3_key = "{}/{}.jpg".format(username, img_id)
    delete_image(s3_key)
    res = update_recode(username, img_id)

    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        'body': json.dumps(res)
    }
