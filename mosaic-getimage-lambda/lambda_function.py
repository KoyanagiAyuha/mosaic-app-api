import json
import boto3
import os
import base64
from datetime import datetime, timedelta, timezone
from mimetypes import guess_extension
import uuid


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

    # タイムゾーンの生成
    JST = timezone(timedelta(hours=+9), 'JST')

    # GOOD, タイムゾーンを指定している．早い
    created_on = datetime.now(JST)
    timestamp = created_on.timestamp()
    created_on_str = created_on.strftime('%Y-%m-%d %H:%M:%S')
    postimg_name = []
    postid = str(uuid.uuid4())
    for i, img in enumerate(imglist):
        ext = guess_extension(img.split(";")[0].split(":")[1])
        encode = base64.b64decode(img.split(",")[-1].encode("UTF-8"))
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
