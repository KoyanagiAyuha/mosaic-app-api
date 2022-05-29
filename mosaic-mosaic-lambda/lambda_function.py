import uuid
import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config
import logging
import sys
import json
from datetime import datetime, timedelta, timezone
import base64
import cv2
import numpy as np

config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)

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

CONTINUE_NUM = 5
MATCH_TH = 0.8


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

    if len(response['Items']) < CONTINUE_NUM:
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
def succeeded_record(username, created_at):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(EDIT_TABLE_NAME)

    table.update_item(
        Key={'username': username, 'created_at': created_at},
        UpdateExpression="set #st=:s",
        ExpressionAttributeNames={
            '#st': 'status',
        },
        ExpressionAttributeValues={
            ':s': 'Succeeded',
        }
    )


@log_decorator()
def failed_record(username, created_at):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(EDIT_TABLE_NAME)

    table.update_item(
        Key={'username': username, 'created_at': created_at},
        UpdateExpression="set #st=:s",
        ExpressionAttributeNames={
            '#st': 'status',
        },
        ExpressionAttributeValues={
            ':s': 'Failed',
        }
    )


@log_decorator()
def create_mosaic_img(img, username):
    cv_img = base64_to_cv2(img)

    # amazon_rekognition に投げる
    client = boto3.client('rekognition', config=config)
    result, buf = cv2.imencode('.jpg', cv_img)

    faces = client.detect_faces(Image={'Bytes': buf.tobytes()}, Attributes=['ALL'])

    h, w, ch = cv_img.shape
    result_im = cv_img.copy()

    subject_img_list = get_subject_img(username)

    match_list = []
    for subject_img in subject_img_list:
        img_name = subject_img['uuid']
        key = '{}/{}.jpg'.format(username, img_name)
        is_get_img, sub_img = get_image(key)
        if not is_get_img:
            continue
        sub_img = base64_to_cv2(sub_img)
        result0, buf0 = cv2.imencode('.jpg', sub_img)
        try:
            cfaces = client.compare_faces(SourceImage={'Bytes': buf0.tobytes()}, TargetImage={'Bytes': buf.tobytes()})
        except Exception:
            continue
        match_list.extend([i['Face']['BoundingBox'] for i in cfaces['FaceMatches'] if i['Similarity'] > MATCH_TH])

    for i in faces['FaceDetails']:
        top = max(int(i['BoundingBox']['Top'] * h), 0)
        left = max(int(i['BoundingBox']['Left'] * w), 0)
        bottom = min(int(top + i['BoundingBox']['Height'] * h), h)
        right = min(int(left + i['BoundingBox']['Width'] * w), w)

        is_match = True
        for j in match_list:
            match_top = max(int(j['Top'] * h), 0)
            match_left = max(int(j['Left'] * w), 0)
            match_bottom = min(int(top + j['Height'] * h), h)
            match_right = min(int(left + j['Width'] * w), w)

            iou_val = iou((left, top, right, bottom), (match_left, match_top, match_right, match_bottom))
            if iou_val > 0.8:
                is_match = False

        if is_match:
            result_im[top:bottom, left:right] = _mosaic(cv_img[top:bottom, left:right])

    for j in match_list:
        match_top = max(int(j['Top'] * h), 0)
        match_left = max(int(j['Left'] * w), 0)
        match_bottom = min(int(top + j['Height'] * h), h)
        match_right = min(int(left + j['Width'] * w), w)

        result_im[match_top:match_bottom, match_left:match_right] = cv_img[match_top:match_bottom, match_left:match_right]

    base64_img = cv2_to_base64(result_im)
    return base64_img


@log_decorator()
def get_subject_img(username):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(SUBJECT_TABLE_NAME)

    response = table.query(KeyConditionExpression=Key('username').eq(username))

    return response['Items']


@log_decorator()
def get_image(key):

    s3 = boto3.client('s3')

    try:
        body = s3.get_object(Bucket=SUBJECT_BUCKET_NAME, Key=key)['Body'].read()
    except Exception:
        return False, ''

    encode = base64.b64encode(body).decode()

    return True, encode


@log_decorator()
def _mosaic(src: any, ratio=0.14) -> any:
    """モザイク変換

    Parameters
    ----------
    src : any
        画像
    ratio : float, optional
        モザイク率, by default 0.14

    Returns
    -------
    any
        モザイク変換画像
    """
    small = cv2.resize(src, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_NEAREST)
    return cv2.resize(small, src.shape[:2][::-1], interpolation=cv2.INTER_NEAREST)


@log_decorator()
def iou(a: tuple, b: tuple) -> float:
    a_x1, a_y1, a_x2, a_y2 = a
    b_x1, b_y1, b_x2, b_y2 = b

    if a == b:
        return 1.0
    elif (
        (a_x1 <= b_x1 and a_x2 > b_x1) or (a_x1 >= b_x1 and b_x2 > a_x1)
    ) and (
        (a_y1 <= b_y1 and a_y2 > b_y1) or (a_y1 >= b_y1 and b_y2 > a_y1)
    ):
        intersection = (min(a_x2, b_x2) - max(a_x1, b_x1)) * (min(a_y2, b_y2) - max(a_y1, b_y1))
        union = (a_x2 - a_x1) * (a_y2 - a_y1) + (b_x2 - b_x1) * (b_y2 - b_y1) - intersection
        return intersection / union
    else:
        return 0.0


def post_image(img, key):

    s3_client = boto3.client('s3')
    data = base64.b64decode(img)

    s3_client.put_object(Bucket=EDIT_BUCKET_NAME, Key=key, Body=data)


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
            data = create_mosaic_img(img, username)

            post_image(data, s3_post_key)

            succeeded_record(username, now_str)

            res = {
                'status': 'OK',
                'message': 'mosaic successfully',
                'img': data
            }
        except Exception as e:
            logger.error(e)
            now_str = now.isoformat()
            failed_record(username, now_str)
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
