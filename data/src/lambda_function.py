import csv
import io
import os
import urllib.parse
from decimal import Decimal, InvalidOperation

import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def validate(row):
    """Return (item, None) if the row is valid, or (None, reason) if not."""
    row_id = (row.get("id") or "").strip()
    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip()
    amount_raw = (row.get("amount") or "").strip()

    if not row_id:
        return None, "missing id"
    if not email or "@" not in email:
        return None, "missing or invalid email"
    try:
        amount = Decimal(amount_raw)
        if not amount.is_finite():
            raise InvalidOperation
    except InvalidOperation:
        return None, "amount is not a number"

    return {"id": row_id, "name": name, "email": email, "amount": amount}, None


def lambda_handler(event, context):
    loaded = 0
    skipped = 0

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        print(f"Processing s3://{bucket}/{key}")

        obj = s3.get_object(Bucket=bucket, Key=key)
        text = obj["Body"].read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        for row_num, row in enumerate(reader, start=2):
            item, error = validate(row)
            if error:
                print(f"INVALID row {row_num}: {error} -> {dict(row)}")
                skipped += 1
                continue
            table.put_item(Item=item)
            loaded += 1

    print(f"Done. loaded={loaded}, skipped={skipped}")
    return {"loaded": loaded, "skipped": skipped}